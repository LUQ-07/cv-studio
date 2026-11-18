"""Template gallery workflow (cards with USE THIS TEMPLATE / ADD TO FAVORITES, sidebar toggle).

GUI *logic* is exercised with a Qt stand-in (tests/_qtstub.py): button wiring, data preservation, saving, favourites,
highlight and animation parameters. Pixel rendering of the real Qt widgets is NOT covered here."""
import dataclasses
import json
import pathlib
import tempfile
import unittest
import zipfile

import _qtstub


class _Sig:
    def __init__(self): self.callbacks = []
    def connect(self, fn): self.callbacks.append(fn)


class RecBtn:
    """Records every QPushButton the window creates (text, visibility, click handlers)."""
    created = []

    def __init__(self, text="", *a, **k):
        self.text, self.visible, self.callbacks = text, True, []
        self.clicked = type("S", (), {"connect": lambda s, fn, b=self: b.callbacks.append(fn)})()
        RecBtn.created.append(self)
    def setText(self, t): self.text = t
    def setVisible(self, v): self.visible = bool(v)
    def hide(self): self.visible = False
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _qtstub.Stub()


class RecLabel:
    texts = []

    def __init__(self, text="", *a, **k):
        self.text = text; RecLabel.texts.append(text)
    def setText(self, t): self.text = t; RecLabel.texts.append(t)
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _qtstub.Stub()


class RecAnim:
    last = None

    def __init__(self, *a, **k):
        self.valueChanged, self.finished = _Sig(), _Sig(); self.started = False; RecAnim.last = self
    def setStartValue(self, v): self.start_value = v
    def setEndValue(self, v): self.end_value = v
    def setDuration(self, v): self.duration = v
    def start(self): self.started = True
    def stop(self): self.started = False
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _qtstub.Stub()


class RecSidebar:
    def __init__(self): self.w, self.visible, self.calls = 230, True, []
    def width(self): return self.w
    def setFixedWidth(self, w): self.w = w
    def setVisible(self, v): self.visible = bool(v); self.calls.append(("visible", bool(v)))


class RecStack:
    def __init__(self, i=1): self.i = i
    def count(self): return 6
    def currentIndex(self): return self.i
    def setCurrentIndex(self, i): self.i = i


class Gallery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _qtstub.install()
        from cvstudio import gui
        cls.gui = gui
        gui.QPushButton, gui.QLabel, gui.QVariantAnimation = RecBtn, RecLabel, RecAnim

    @classmethod
    def tearDownClass(cls):
        _qtstub.uninstall()

    def setUp(self):
        from cvstudio.models import sample_profile
        from cvstudio.settings import Settings
        from cvstudio.storage import ProfileStore
        self.tmp = tempfile.TemporaryDirectory(); d = self.dir = pathlib.Path(self.tmp.name)
        self.gui.app_data_dir = lambda: d / "appdata"                  # never touch the real user-data folder
        stale = d / "appdata" / "cache" / "thumbs-0.0.1"; stale.mkdir(parents=True); (stale / "old.png").write_bytes(b"x")
        RecBtn.created.clear(); RecLabel.texts.clear()
        self.db, self.settings_path = d / "db.sqlite3", d / "s.json"
        self.w = self.gui.MainWindow(Settings(self.settings_path), ProfileStore(self.db))
        self.buttons = list(RecBtn.created)
        self.w.profile = sample_profile()
        self.w._collect = lambda: self.w.profile                       # widgets are stand-ins; the profile object is the data
        self.previews = []
        self.w.open_preview = lambda: self.previews.append(1)
        self.w._require_premium = lambda f: None

    def tearDown(self):
        self.w.iap.shutdown(); self.tmp.cleanup()

    def use_buttons(self): return [b for b in RecBtn.created[-400:] if b.text == "USE THIS TEMPLATE"][-30:]
    def fav_buttons(self): return [b for b in RecBtn.created[-400:] if b.text in ("ADD TO FAVORITES", "★ REMOVE FAVORITE")][-30:]

    # ---- cards: both buttons on every template, nothing selected automatically
    def test_every_card_has_both_buttons_and_nothing_is_preselected(self):
        from cvstudio.templates import TEMPLATES
        texts = [b.text for b in self.buttons]
        self.assertEqual(len(TEMPLATES), texts.count("USE THIS TEMPLATE"))
        self.assertEqual(len(TEMPLATES), texts.count("ADD TO FAVORITES"))
        self.assertNotIn("Use this template", texts); self.assertNotIn("Choose template", texts)
        self.assertNotIn("✓ SELECTED", RecLabel.texts)                    # no highlighted card when the page opens
        self.assertIsNone(self.w._preview_id); self.assertIsNone(self.w._current_template())
        self.w.refresh_template_list()
        self.assertNotIn("✓ SELECTED", RecLabel.texts)

    def test_one_templates_entry_point_in_preview_and_export_remains(self):
        calls = []
        self.w.navigate = lambda i: calls.append(i)
        next(b for b in self.buttons if b.text == "Templates").callbacks[0]()
        self.assertEqual([2], calls)
        self.assertEqual(1, [b.text for b in self.buttons].count("Templates"))

    def test_exactly_five_categories_in_the_filter_including_others(self):
        cats = [k[4:] for k in self.w._filter_keys if k.startswith("cat:")]
        self.assertEqual(["Modern", "Minimal", "Professional", "Creative", "Others"], cats)

    # ---- USE THIS TEMPLATE
    def test_use_this_template_applies_preserves_saves_highlights_and_refreshes(self):
        from cvstudio.storage import ProfileStore
        from cvstudio.templates import TEMPLATES
        idx = [TEMPLATES.index(next(t for t in TEMPLATES if t.free)), TEMPLATES.index(next(t for t in TEMPLATES if t.layout == "banner")), TEMPLATES.index(next(t for t in TEMPLATES if t.premium))]
        for i in idx:
            t = TEMPLATES[i]
            before = dataclasses.asdict(self.w.profile)
            RecLabel.texts.clear()
            self.use_buttons()[i].callbacks[0]()                        # click USE THIS TEMPLATE on that card
            after = dataclasses.asdict(self.w.profile)
            for key in ("template_id", "accent_color", "template_chosen"):
                before.pop(key); after.pop(key)
            self.assertEqual(before, after, t.id)                       # no CV information changed
            self.assertEqual((t.id, t.color, True), (self.w.profile.template_id, self.w.profile.accent_color, self.w.profile.template_chosen))
            reopened = ProfileStore(self.db).load(self.w.profile.id)    # saved: survives reopening
            self.assertEqual((t.id, True), (reopened.template_id, reopened.template_chosen))
            self.assertEqual(1, RecLabel.texts.count("✓ SELECTED"))     # exactly one highlighted card
        self.assertEqual(len(idx), len(self.previews))

    def test_nothing_selected_changes_nothing(self):
        before = self.w.profile.template_id
        self.w.choose_template()
        self.assertEqual(before, self.w.profile.template_id); self.assertEqual([], self.previews)

    def test_clicking_a_card_previews_without_applying(self):
        from cvstudio.templates import TEMPLATES
        shown = []
        self.w.detail = type("D", (), {"show_pdf": lambda s, p: shown.append(p), "clear": lambda s: None, "info": _qtstub.Stub()})()
        tid = TEMPLATES[7].id
        before = self.w.profile.template_id
        self.w._preview_template(tid); self.w._render_template_detail()
        self.assertEqual(tid, self.w._current_template().id)
        self.assertEqual(before, self.w.profile.template_id)           # previewing is not applying
        self.assertTrue(shown and pathlib.Path(shown[-1]).stat().st_size > 1000)

    # ---- ADD TO FAVORITES
    def test_favorites_toggle_persist_and_never_duplicate(self):
        from cvstudio.settings import Settings
        from cvstudio.templates import TEMPLATES
        tid = TEMPLATES[3].id
        self.fav_buttons()[3].callbacks[0]()
        self.assertEqual([tid], Settings(self.settings_path).get("favorites"))     # persisted: a new Settings = a restart
        self.assertIn("★ REMOVE FAVORITE", [b.text for b in RecBtn.created[-60:]])  # clear visual state on the rebuilt card
        self.fav_buttons()[3].callbacks[0]()
        self.assertEqual([], Settings(self.settings_path).get("favorites"))
        for _ in range(3):
            self.fav_buttons()[3].callbacks[0]()
        self.assertEqual([tid], Settings(self.settings_path).get("favorites"))

    def test_duplicate_favorites_in_an_existing_settings_file_are_cleaned(self):
        from cvstudio.settings import Settings
        self.settings_path.write_text(json.dumps({"favorites": ["a", "b", "a", 7, "b"]}), encoding="utf-8")
        self.assertEqual(["a", "b"], Settings(self.settings_path).get("favorites"))

    # ---- Go back
    def test_go_back_returns_to_previous_page_and_editor_tab_without_touching_data(self):
        w = self.w
        w.stack, w.editor_tabs = RecStack(1), RecStack(4)          # CV editor page, "Preview & export"-style tab 4
        back = next(b for b in self.buttons if b.text == "←  Go back")
        self.assertFalse(back.visible)                              # nothing to go back to yet
        snapshot, profile = dataclasses.asdict(w.profile), w.profile
        w.navigate(2)                                               # open Templates
        self.assertEqual(2, w.stack.i); self.assertTrue(back.visible)
        back.callbacks[0]()
        self.assertEqual((1, 4), (w.stack.i, w.editor_tabs.i)); self.assertFalse(back.visible)   # same page, same tab
        w.navigate(2); w.navigate(3)                                # chain of pages
        back.callbacks[0](); self.assertEqual(2, w.stack.i)
        back.callbacks[0](); self.assertEqual(1, w.stack.i)
        back.callbacks[0](); self.assertEqual(1, w.stack.i)         # empty history: nothing happens
        self.assertIs(profile, w.profile); self.assertEqual(snapshot, dataclasses.asdict(w.profile))
        self.assertIn('setShortcut("Alt+Left")', pathlib.Path(self.gui.__file__).read_text(encoding="utf-8"))      # keyboard shortcut wired

    def test_standard_filter_has_no_free_entry_and_only_five_categories(self):
        keys = self.w._filter_keys
        self.assertEqual(["all", "fav", "ats"], [k for k in keys if not k.startswith("cat:")])   # everything is free: no "Free" entry
        self.assertEqual(5, len([k for k in keys if k.startswith("cat:")]))

    # ---- collapsible sidebar
    def test_sidebar_toggle_hides_and_restores_without_touching_page_or_data(self):
        self.w.sidebar = RecSidebar()
        nav, snapshot, profile = [], dataclasses.asdict(self.w.profile), self.w.profile
        self.w.navigate = lambda i: nav.append(i)
        burger = next(b for b in self.buttons if b.text == "☰")
        burger.callbacks[0]()                                          # hide
        a = RecAnim.last
        self.assertFalse(self.w._sidebar_open); self.assertEqual((230, 0), (a.start_value, a.end_value)); self.assertTrue(a.started)
        a.valueChanged.callbacks[0](120); self.assertEqual(120, self.w.sidebar.w)
        a.finished.callbacks[0](); self.assertFalse(self.w.sidebar.visible)
        self.w.sidebar.w = 0
        burger.callbacks[0]()                                          # show again (button is still reachable while hidden)
        a = RecAnim.last
        self.assertTrue(self.w._sidebar_open); self.assertEqual((0, 230), (a.start_value, a.end_value))
        self.assertEqual(("visible", True), self.w.sidebar.calls[-1])  # made visible before it slides in
        a.finished.callbacks[0](); self.assertTrue(self.w.sidebar.visible)
        self.assertEqual([], nav); self.assertIs(profile, self.w.profile); self.assertEqual(snapshot, dataclasses.asdict(self.w.profile))

    # ---- thumbnails of older designs are dropped
    def test_old_thumbnail_cache_is_removed_and_new_one_keyed_by_design_revision(self):
        from cvstudio.templates import DESIGN_REV
        cache = self.dir / "appdata" / "cache"
        self.assertFalse((cache / "thumbs-0.0.1").exists())
        self.assertTrue(any(p.name.endswith(f"-d{DESIGN_REV}") for p in cache.iterdir()))

    # ---- exports follow the applied template
    def test_exports_use_the_selected_template(self):
        from cvstudio.docx_export import export_docx
        from cvstudio.exporter import export_pdf
        from cvstudio.templates import TEMPLATES
        ids = [t.id for t in TEMPLATES]
        for tid, pdf_font, other_font, word_font in (("minimal_paper", b"Caladea", b"Carlito", "Cambria"), ("modern_summit", b"Carlito", b"Caladea", "Calibri")):
            self.use_buttons()[ids.index(tid)].callbacks[0]()
            pdf = export_pdf(self.w.profile, self.dir / f"{tid}.pdf").read_bytes()
            self.assertTrue(pdf_font in pdf, tid); self.assertFalse(other_font in pdf, tid)
            xml = zipfile.ZipFile(export_docx(self.w.profile, self.dir / f"{tid}.docx")).read("word/document.xml").decode("utf-8")
            self.assertIn(word_font, xml)

    def test_page_width_fits_pane(self):
        pw = self.gui.page_width
        self.assertEqual(300, pw(300)); self.assertEqual(480, pw(520)); self.assertEqual(820, pw(2000)); self.assertEqual(720, pw(520, 150))


if __name__ == "__main__":
    unittest.main()
