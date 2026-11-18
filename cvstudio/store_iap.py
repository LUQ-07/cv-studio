"""Microsoft Store in-app purchase (durable add-on) for the Premium templates.

Design rules (verified against Microsoft's StoreContext docs):
  * Ownership checks run on a private asyncio loop in a worker thread -> the Qt UI never blocks.
  * RequestPurchaseAsync MUST be started from the UI thread, on a StoreContext associated with the
    window handle (IInitializeWithWindow), else it fails with 0x80070578. We start it on the UI thread
    (it returns immediately) and await completion on the worker loop.
  * RequestPurchaseAsync takes the add-on's **Store ID** (e.g. 9XXXXXXXXXXX), not the Product ID. The Product ID
    "cv_studio_premium_templates" is the add-on's InAppOfferToken, which we use to find the Store ID.
  * Store APIs only work when the app has package identity (installed from the Store / an MSIX). A bare
    PyInstaller .exe cannot check or sell add-ons: the state is then UNAVAILABLE and nothing is unlocked.
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from enum import Enum

PRODUCT_ID = "cv_studio_premium_templates"       # add-on Product ID in Partner Center (= InAppOfferToken)
CHECK_TIMEOUT = 25.0                              # seconds; a hung Store call must not leave the app "busy" forever


class State(str, Enum):
    OWNED = "owned"
    NOT_OWNED = "not_owned"
    UNAVAILABLE = "unavailable"      # no package identity / winrt missing / Store unreachable
    UNKNOWN = "unknown"


class Purchase(str, Enum):
    SUCCEEDED = "succeeded"
    ALREADY_OWNED = "already_owned"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class CheckResult:
    state: State
    detail: str = ""
    store_id: str = ""      # add-on Store ID (needed for purchase)
    price: str = ""         # localised price string for display


def dev_unlock_enabled() -> bool:
    """Developer shortcut for running from source. Never honoured in a packaged (frozen) build."""
    return os.environ.get("CVSTUDIO_DEV_UNLOCK") == "1" and not getattr(sys, "frozen", False)


def _load_store():
    from winrt.windows.services.store import StoreContext  # imported lazily: only exists on Windows with winrt installed
    return StoreContext


class StoreCore:
    """Qt-free service. All public methods return immediately; results arrive on `concurrent.futures.Future`s."""

    def __init__(self, product_id: str = PRODUCT_ID, loader=_load_store, timeout: float = CHECK_TIMEOUT):
        self.product_id, self._loader, self.timeout = product_id, loader, timeout
        self.state, self.store_id, self.price = State.UNKNOWN, "", ""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="store-iap", daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        self._loop.close()

    def shutdown(self):
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _submit(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    # ---- ownership (worker thread) --------------------------------------------------------------
    def check(self) -> Future:
        if dev_unlock_enabled():
            self.state = State.OWNED
            f: Future = Future(); f.set_result(CheckResult(State.OWNED, "developer unlock")); return f
        return self._submit(self._check())

    async def _check(self) -> CheckResult:
        try:
            StoreContext = self._loader()
            ctx = StoreContext.get_default()
            lic = await asyncio.wait_for(ctx.get_app_license_async(), self.timeout)
            owned = any(getattr(a, "in_app_offer_token", "") == self.product_id and getattr(a, "is_active", False)
                        for a in lic.add_on_licenses.values())
            store_id, price = self.store_id, self.price
            if not owned and not store_id:                      # look up the Store ID + price for the purchase button
                res = await asyncio.wait_for(ctx.get_associated_store_products_async(["Durable"]), self.timeout)
                for prod in res.products.values():
                    if getattr(prod, "in_app_offer_token", "") == self.product_id:
                        store_id = prod.store_id
                        price = getattr(getattr(prod, "price", None), "formatted_price", "") or ""
                        break
            self.store_id, self.price = store_id, price
            self.state = State.OWNED if owned else State.NOT_OWNED
            return CheckResult(self.state, "", store_id, price)
        except asyncio.TimeoutError:
            self.state = State.UNAVAILABLE
            return CheckResult(State.UNAVAILABLE, "The Microsoft Store did not answer in time")
        except ImportError as exc:
            self.state = State.UNAVAILABLE
            return CheckResult(State.UNAVAILABLE, f"winrt not installed: {exc}")
        except Exception as exc:    # OSError/COMError: no package identity, offline with no cached licence, etc.
            self.state = State.UNAVAILABLE
            return CheckResult(State.UNAVAILABLE, f"{type(exc).__name__}: {exc}")

    # ---- purchase (start on UI thread, await on worker) -----------------------------------------
    def start_purchase(self, hwnd: int) -> Future:
        """Call from the Qt UI thread. Returns immediately; the Future resolves to a Purchase value."""
        out: Future = Future()
        try:
            StoreContext = self._loader()
            ctx = StoreContext.get_default()
            associate_window(ctx, hwnd)
            op = ctx.request_purchase_async(self.store_id or self.product_id)   # shows Microsoft's payment window
        except Exception as exc:
            out.set_result((Purchase.FAILED, f"{type(exc).__name__}: {exc}"))
            return out

        async def finish():
            try:
                res = await op
                status = int(getattr(res, "status", -1))      # StorePurchaseStatus enum
                # 0 Succeeded, 1 AlreadyPurchased, 2 NotPurchased (user cancelled), 3 NetworkError, 4 ServerError
                if status == 0: return (Purchase.SUCCEEDED, "")
                if status == 1: return (Purchase.ALREADY_OWNED, "")
                if status == 2: return (Purchase.CANCELLED, "")
                ext = getattr(res, "extended_error", None)
                return (Purchase.FAILED, f"status {status} {ext or ''}".strip())
            except Exception as exc:
                return (Purchase.FAILED, f"{type(exc).__name__}: {exc}")

        fut = self._submit(finish())
        fut.add_done_callback(lambda f: out.set_result(f.result()) if not out.done() else None)
        return out


def associate_window(ctx, hwnd: int) -> bool:
    """IInitializeWithWindow::Initialize(hwnd) on a WinRT StoreContext.

    Needed for desktop (non-UWP) apps. Uses pywinrt's COM pointer + ctypes. If the installed pywinrt does not
    expose the raw interface pointer this returns False and the caller falls back to the Store product page.
    """
    try:
        import ctypes
        from ctypes import wintypes
        IID = (ctypes.c_ubyte * 16).from_buffer_copy(bytes.fromhex("bdd4683e35710d4a80189fb6d9f33fa1"))  # 3E68D4BD-7135-4D10-8018-9FB6D9F33FA1
        ptr = getattr(ctx, "_ptr", None) or getattr(ctx, "_abi", None)
        if not ptr:
            return False
        unk = ctypes.c_void_p(int(ptr))
        vtbl = ctypes.cast(ctypes.cast(unk, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        qi = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(vtbl[0])
        iw = ctypes.c_void_p()
        qi(unk, ctypes.addressof(IID), ctypes.byref(iw))
        vt2 = ctypes.cast(ctypes.cast(iw, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        init = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, wintypes.HWND)(vt2[3])   # slot 3 = Initialize
        init(iw, hwnd)
        return True
    except Exception:
        return False


def store_page_url(store_id: str) -> str:
    """Fallback: open the add-on's page in the Microsoft Store app (user buys there, then we re-check)."""
    safe = "".join(ch for ch in (store_id or "") if ch.isalnum())      # Store IDs are alphanumeric; never pass other characters on
    return f"ms-windows-store://pdp/?productid={safe}" if safe else "ms-windows-store://home"


def template_allowed(template, state: State) -> bool:
    """Free templates always; Premium only when the add-on is owned."""
    return template.free or state == State.OWNED
