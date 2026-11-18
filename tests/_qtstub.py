"""Minimal stand-in for PySide6 so GUI *logic* can be tested without Qt (no rendering is tested).

install() puts fake PySide6 modules in sys.modules; uninstall() restores whatever was there before and drops the
fake-imported `cvstudio.gui`, so other tests are unaffected."""
import sys
import types


class _Meta(type):
    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Stub()


class Stub(metaclass=_Meta):
    def __init__(self, *a, **k): pass
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Stub()
    def __call__(self, *a, **k): return Stub()
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __mul__(self, o): return 1.0
    __rmul__ = __truediv__ = __rtruediv__ = __mul__
    def __sub__(self, o): return 0
    __add__ = __radd__ = __rsub__ = __sub__
    def __float__(self): return 1.0
    def __int__(self): return 1
    def __index__(self): return 0
    def __or__(self, o): return self
    __ror__ = __or__
    def __eq__(self, o): return False
    def __hash__(self): return 1
    __gt__ = __lt__ = __ge__ = __le__ = lambda s, o: False
    def __getitem__(self, i): return Stub()


_NAMES = ["PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtPdf"]
_saved = {}


def _module(name):
    m = types.ModuleType(name)
    def getattr_(n):
        if n.startswith("__"):
            raise AttributeError(n)
        return type(n, (Stub,), {})
    m.__getattr__ = getattr_
    return m


def install():
    for n in _NAMES + ["cvstudio.gui"]:
        _saved[n] = sys.modules.pop(n, None)
    for n in _NAMES:
        sys.modules[n] = _module(n)


def uninstall():
    for n in _NAMES + ["cvstudio.gui"]:
        sys.modules.pop(n, None)
        if _saved.get(n) is not None:
            sys.modules[n] = _saved[n]
    _saved.clear()
