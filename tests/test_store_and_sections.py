import asyncio
import os
import sys
import time
import unittest
from types import SimpleNamespace as NS
from unittest import mock

from cvstudio import store_iap
from cvstudio.models import sample_profile
from cvstudio.sections import ORDER, SPECS, SectionModel
from cvstudio.store_iap import Purchase, State, StoreCore, template_allowed
from cvstudio.templates import TEMPLATES, get_template


def fake_store(owned=False, delay=0.0, purchase_status=0, boom=None, offer="cv_studio_premium_templates"):
    """Build a fake `StoreContext` class that mimics the winrt async API."""
    class Ctx:
        async def get_app_license_async(self):
            await asyncio.sleep(delay)
            if boom: raise boom
            addons = {"9ABC/0010": NS(in_app_offer_token=offer, is_active=True)} if owned else {}
            return NS(add_on_licenses=addons)

        async def get_associated_store_products_async(self, kinds):
            assert kinds == ["Durable"]
            return NS(products={"9ABCDEF12345": NS(in_app_offer_token=offer, store_id="9ABCDEF12345", price=NS(formatted_price="€9.99"))})

        def request_purchase_async(self, store_id):
            self.asked = store_id
            async def run():
                await asyncio.sleep(delay)
                return NS(status=purchase_status, extended_error=None)
            return asyncio.ensure_future(run(), loop=core_loop[0])
    class StoreContext:
        @staticmethod
        def get_default(): return Ctx()
    return lambda: StoreContext


core_loop = [None]


def make_core(**kw):
    core = StoreCore(loader=fake_store(**kw))
    core_loop[0] = core._loop
    return core


class StoreTests(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("CVSTUDIO_DEV_UNLOCK", None)

    def test_five_free_twenty_five_premium(self):
        self.assertEqual(5, sum(t.free for t in TEMPLATES)); self.assertEqual(25, sum(t.premium for t in TEMPLATES))

    def test_owned(self):
        core = make_core(owned=True); r = core.check().result(5)
        self.assertEqual(State.OWNED, r.state); core.shutdown()

    def test_not_owned_finds_store_id_and_price(self):
        core = make_core(owned=False); r = core.check().result(5)
        self.assertEqual((State.NOT_OWNED, "9ABCDEF12345", "€9.99"), (r.state, r.store_id, r.price)); core.shutdown()

    def test_check_never_blocks_caller(self):
        core = make_core(owned=True, delay=0.4); t = time.time(); fut = core.check()
        self.assertLess(time.time() - t, 0.1)          # returns immediately; work happens on the worker thread
        self.assertEqual(State.OWNED, fut.result(5).state); core.shutdown()

    def test_other_addon_does_not_unlock(self):
        core = make_core(owned=True, offer="something_else"); self.assertEqual(State.NOT_OWNED, core.check().result(5).state); core.shutdown()

    def test_unavailable_when_not_packaged_or_offline(self):
        core = make_core(boom=OSError("0x80073D54 no package identity")); r = core.check().result(5)
        self.assertEqual(State.UNAVAILABLE, r.state); self.assertIn("OSError", r.detail); core.shutdown()

    def test_unavailable_when_winrt_missing(self):
        def loader(): raise ImportError("No module named winrt")
        core = StoreCore(loader=loader); self.assertEqual(State.UNAVAILABLE, core.check().result(5).state); core.shutdown()

    def test_purchase_statuses(self):
        for status, expected in ((0, Purchase.SUCCEEDED), (1, Purchase.ALREADY_OWNED), (2, Purchase.CANCELLED), (3, Purchase.FAILED), (4, Purchase.FAILED)):
            core = make_core(owned=False, purchase_status=status); core.check().result(5)
            with mock.patch.object(store_iap, "associate_window", return_value=True):
                got, _ = core.start_purchase(1234).result(5)
            self.assertEqual(expected, got, status); core.shutdown()

    def test_dev_unlock_only_when_not_frozen(self):
        os.environ["CVSTUDIO_DEV_UNLOCK"] = "1"
        core = make_core(owned=False); self.assertEqual(State.OWNED, core.check().result(5).state)
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertFalse(store_iap.dev_unlock_enabled())
        core.shutdown()

    def test_gate_logic(self):
        free, prem = get_template("modern_summit"), get_template("modern_atlas")
        for s in State:
            self.assertTrue(template_allowed(free, s))
        self.assertTrue(template_allowed(prem, State.OWNED))
        for s in (State.NOT_OWNED, State.UNAVAILABLE, State.UNKNOWN):
            self.assertFalse(template_allowed(prem, s))


class SectionTests(unittest.TestCase):
    def test_every_section_has_spec_and_required_primary(self):
        self.assertEqual(16, len(ORDER))
        for spec in SPECS.values():
            self.assertIn(spec.primary, [f.key for f in spec.fields]); self.assertTrue(any(f.required for f in spec.fields))

    def test_requested_forms(self):
        self.assertEqual(["Language name", "Proficiency level"], [f.label for f in SPECS["languages"].fields])
        self.assertIn("Native", SPECS["languages"].fields[1].options); self.assertIn("Fluent", SPECS["languages"].fields[1].options)
        self.assertEqual(["Project title", "Your role", "Technologies used"], [f.label for f in SPECS["projects"].fields][:3])

    def test_crud_and_central_list_identity(self):
        central = {"projects": []}
        m = SectionModel(SPECS["projects"], central["projects"])
        i = m.add({"title": " A ", "role": "Lead", "technologies": "Py"}); m.add({"title": "B"})
        self.assertEqual("A", central["projects"][0]["title"])                 # mutated in place
        m.update(i, {"title": "A2", "role": "Dev"}); self.assertEqual("A2", central["projects"][0]["title"])
        self.assertEqual(1, m.move(0, 1)); self.assertEqual("B", central["projects"][0]["title"])
        m.delete(0); self.assertEqual(["A2  —  Dev"], m.labels())
        with self.assertRaises(ValueError): m.add({"title": "  "})
        with self.assertRaises(IndexError): m.update(9, {"title": "x"})

    def test_replace_all_keeps_old_data_shape(self):
        m = SectionModel(SPECS["projects"]); m.replace_all([{"name": "Legacy", "description": "d"}, "str"])
        self.assertEqual("Legacy", m.rows[0]["name"]); self.assertIn("title", m.rows[0])


if __name__ == "__main__":
    unittest.main()
