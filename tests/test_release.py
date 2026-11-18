"""Release-readiness checks for CV Studio 1.0.0 (added; existing tests are untouched)."""
import ast
import asyncio
import json
import os
import re
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace as NS

import cvstudio
from cvstudio import i18n, store_iap
from cvstudio.models import CVProfile, sample_profile
from cvstudio.settings import Settings
from cvstudio.storage import ProfileStore
from cvstudio.store_iap import State, StoreCore, store_page_url, template_allowed
from cvstudio.templates import TEMPLATES, get_template

ROOT = Path(__file__).resolve().parent.parent


class VersionAndText(unittest.TestCase):
    def test_version_is_1_0_0_everywhere(self):
        self.assertEqual("1.0.0", cvstudio.__version__)
        self.assertIn('version = "1.0.0"', (ROOT / "pyproject.toml").read_text())
        self.assertIn("Version 1.0.0", (ROOT / "README.md").read_text())

    def test_about_and_homepage_text(self):
        gui = (ROOT / "cvstudio/gui.py").read_text(encoding="utf-8")
        self.assertIn('QLabel(f"Version {__version__}")', gui)                      # About page
        self.assertIn("Professional designs · PDF & editable Word · 100% private", gui)
        self.assertNotIn("30 professional designs", gui)

    def test_thirty_templates_still_exist(self):
        self.assertEqual(30, len(TEMPLATES)); self.assertEqual(5, sum(t.free for t in TEMPLATES))


class PackagingPathsAndThemes(unittest.TestCase):
    def test_every_path_used_by_build_scripts_exists(self):
        for rel in ("run_app.py", "CV Studio.spec", "requirements.txt", "requirements-build.txt", "tools/clean.py",
                    "cvstudio/assets/cv-studio.ico", "cvstudio/assets/cv-studio.svg", "build_exe.ps1", "LICENSE", "NOTICE.md",
                    ".github/workflows/tests.yml", ".github/workflows/release.yml"):
            self.assertTrue((ROOT / rel).exists(), rel)
        for t in ("sans", "serif", "mono"):                                        # bundled fonts load (no fallback to built-in fonts)
            from cvstudio.design import FONT_FILES, FONT_DIR
            for f in FONT_FILES[t][1]:
                self.assertTrue((FONT_DIR / f).is_file(), f)

    def test_light_and_dark_stylesheets_build(self):
        from cvstudio import theme
        for mode in ("light", "dark"):
            css = theme.qss(mode)
            self.assertIn(theme.PALETTES[mode]["accent"], css); self.assertEqual(css.count("{"), css.count("}"))


class NoUpdaterNoNetwork(unittest.TestCase):
    BANNED = {"urllib.request", "http.client", "http.server", "socket", "ssl", "requests", "ftplib", "smtplib", "xmlrpc", "aiohttp", "httpx", "telnetlib"}

    def test_no_network_modules_imported_by_application(self):
        for path in (ROOT / "cvstudio").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                for m in mods:
                    self.assertNotIn(m, self.BANNED, f"{path.name} imports {m}")

    def test_no_updater_in_source(self):
        text = "\n".join(p.read_text(encoding="utf-8").lower() for p in (ROOT / "cvstudio").glob("*.py"))
        for word in ("check_for_update", "checkforupdate", "autoupdate", "auto_update", "self_update", "download_update", "updater"):
            self.assertNotIn(word, text)


def fake_ctx(license_delay=0.0, owned=True):
    class Ctx:
        async def get_app_license_async(self):
            await asyncio.sleep(license_delay)
            return NS(add_on_licenses={"x": NS(in_app_offer_token=store_iap.PRODUCT_ID, is_active=owned)})

        async def get_associated_store_products_async(self, kinds):
            return NS(products={"9ABCDEF12345": NS(in_app_offer_token=store_iap.PRODUCT_ID, store_id="9ABCDEF12345", price=NS(formatted_price="$1"))})
    class SC:
        @staticmethod
        def get_default(): return Ctx()
    return lambda: SC


class PurchaseOwnership(unittest.TestCase):
    def test_premium_locked_until_ownership_is_proven(self):
        core = StoreCore(loader=fake_ctx())
        premium = next(t for t in TEMPLATES if t.premium)
        self.assertEqual(State.UNKNOWN, core.state)                      # fresh start: nothing unlocked
        self.assertFalse(template_allowed(premium, core.state))
        self.assertEqual(State.OWNED, core.check().result(5).state)
        self.assertTrue(template_allowed(premium, core.state)); core.shutdown()

    def test_restart_and_update_restore_premium_from_store_licence(self):
        for _ in range(2):                                                # "restart": brand-new service each time
            core = StoreCore(loader=fake_ctx()); self.assertEqual(State.OWNED, core.check().result(5).state); core.shutdown()

    def test_inactive_licence_does_not_unlock(self):
        core = StoreCore(loader=fake_ctx(owned=False)); self.assertEqual(State.NOT_OWNED, core.check().result(5).state); core.shutdown()

    def test_hung_store_times_out_instead_of_blocking_forever(self):
        core = StoreCore(loader=fake_ctx(license_delay=5), timeout=0.2); r = core.check().result(3)
        self.assertEqual(State.UNAVAILABLE, r.state); self.assertIn("in time", r.detail); core.shutdown()

    def test_store_page_url_is_sanitised(self):
        self.assertEqual("ms-windows-store://pdp/?productid=9ABCDEF12345", store_page_url("9ABCDEF12345"))
        hostile = store_page_url("9ABC&evil=1/../?x#y")
        self.assertRegex(hostile, r"^ms-windows-store://pdp/\?productid=[A-Za-z0-9]+$")     # no separators survive
        self.assertEqual("ms-windows-store://home", store_page_url(""))

    def test_no_payment_data_or_fake_success_in_source(self):
        src = (ROOT / "cvstudio/store_iap.py").read_text().lower()
        for word in ("card", "cvv", "iban", "simulate_success", "fake_purchase"):
            self.assertNotIn(word, src)


class DataProtection(unittest.TestCase):
    def test_profiles_and_settings_survive_restart(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); s1 = ProfileStore(d / "a.db"); p = sample_profile(); s1.save(p)
            st = Settings(d / "s.json"); st.set("language", "ar"); st.set("theme", "dark")
            s2 = ProfileStore(d / "a.db"); st2 = Settings(d / "s.json")                  # "restart"
            self.assertEqual(p.full_name, s2.load(p.id).full_name)
            self.assertEqual(("ar", "dark"), (st2.get("language"), st2.get("theme")))

    @unittest.skipUnless(os.path.isdir("/proc/self/fd"), "Linux-only handle check")
    def test_no_database_handles_left_open(self):
        with tempfile.TemporaryDirectory() as d:
            s = ProfileStore(Path(d) / "a.db"); p = sample_profile(); s.save(p); s.load(p.id); s.list_profiles(); s.backup(); s.backup_to(Path(d) / "x.cvbackup"); s.delete(p.id)
            open_files = [os.path.realpath(f"/proc/self/fd/{fd}") for fd in os.listdir("/proc/self/fd")]
            self.assertFalse([f for f in open_files if f.startswith(d)])

    def test_damaged_row_does_not_crash_and_restore_skips_bad_rows(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); s = ProfileStore(d / "a.db"); keep = sample_profile(); s.save(keep)
            with closing(sqlite3.connect(d / "a.db")) as db:      # closed explicitly: Windows cannot delete an open file
                db.execute("INSERT INTO profiles(id,title,data) VALUES('bad','Bad','{not json')")
                db.commit()
            with closing(sqlite3.connect(d / "a.db")) as chk:
                self.assertEqual(1, chk.execute("SELECT COUNT(*) FROM profiles WHERE id='bad'").fetchone()[0])   # the damaged row exists
            self.assertIsNone(s.load("bad"))
            src = ProfileStore(d / "src.db"); good = CVProfile(full_name="Restored"); src.save(good)
            with closing(sqlite3.connect(d / "src.db")) as db:
                db.execute("INSERT INTO profiles(id,title,data) VALUES('bad2','Bad','[1,2')")
                db.commit()
            self.assertEqual(1, s.restore_from(d / "src.db"))
            self.assertEqual("Restored", s.load(good.id).full_name)
            self.assertTrue(list((d / "backups").glob("profiles-*.sqlite3")))     # safety backup taken before merging
            self.assertEqual("Alex Morgan", s.load(keep.id).full_name)             # nothing existing was lost


class Languages(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_translation_tables_are_complete(self):
        base = set(i18n._T["fr"])
        for code in ("es", "ar"):
            self.assertEqual(base, set(i18n._T[code]), code)

    def test_english_default_french_arabic_rtl(self):
        self.assertEqual("en", i18n.current()); self.assertEqual("Export PDF", i18n.tr("Export PDF"))
        i18n.set_language("fr"); self.assertEqual("Exporter en PDF", i18n.tr("Export PDF")); self.assertFalse(i18n.is_rtl())
        i18n.set_language("ar"); self.assertTrue(i18n.is_rtl()); self.assertEqual("تصدير PDF", i18n.tr("Export PDF"))


class TemplateSelectionWorkflow(unittest.TestCase):
    def test_existing_templates_section_applies_selected_template(self):
        gui = (ROOT / "cvstudio/gui.py").read_text(encoding="utf-8")
        # corrected workflow: no extra "Choose template" button/page; the existing Templates button in Preview & export opens the gallery
        self.assertNotIn('Choose template', gui)
        self.assertNotIn('open_template_gallery', gui)
        self.assertIn('change = QPushButton(tr("Templates")); change.clicked.connect(lambda: self.navigate(2))', gui)
        self.assertIn('self._preview_template, self.choose_template, self.toggle_favorite', gui)     # every card gets USE THIS TEMPLATE / ADD TO FAVORITES
        self.assertIn('self.profile.template_id = t.id', gui)
        self.assertIn('self.open_preview()', gui)


    def test_standard_edition_has_no_visible_premium_controls(self):
        gui = (ROOT / "cvstudio/gui.py").read_text(encoding="utf-8")
        self.assertIn("PREMIUM_FEATURES = False", gui)
        self.assertIn("if not PREMIUM_FEATURES or t.free", gui)
        self.assertIn('if not PREMIUM_FEATURES or not t or not hasattr(self, "unlock_btn")', gui)


if __name__ == "__main__":
    unittest.main()
