"""Template upgrade checks: five categories, distinct designs, robust rendering for short / long / empty CVs."""
import io
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from collections import Counter

from cvstudio.design import monogram_png
from cvstudio.docx_export import export_docx
from cvstudio.exporter import export_pdf
from cvstudio.models import CVProfile, sample_profile
from cvstudio.templates import CATEGORIES, TEMPLATES

ORIGINAL_IDS = {
    "modern_summit", "modern_atlas", "modern_horizon", "modern_pulse", "minimal_still", "minimal_paper", "minimal_line", "minimal_clear",
    "corporate_meridian", "corporate_keystone", "corporate_north", "corporate_civic", "creative_canvas", "creative_form", "creative_mosaic",
    "creative_studio", "technical_signal", "technical_stack", "technical_grid", "technical_terminal", "academic_scholar", "academic_field",
    "academic_lecture", "academic_archive", "entry_spark", "entry_launch", "entry_path", "entry_firstlight", "senior_pinnacle", "senior_legacy"}


def long_profile():
    p = sample_profile()
    p.full_name = "Hélène Ben Aïssa-Müller"
    p.experience = [{"role": f"Role {i} Ingénieure Senior", "company": f"Société {i} — Casablanca", "location": "Maroc", "dates": f"20{10 + i} — 20{11 + i}",
                     "description": "\n".join(f"- Résultat n°{j} : a piloté un projet complexe avec de nombreuses équipes et des résultats mesurables (œuvre {i}-{j})" for j in range(4))}
                    for i in range(9)]
    p.skills = [{"name": f"Compétence {i}", "level": ["Beginner", "Intermediate", "Advanced", "Expert"][i % 4]} for i in range(18)]
    p.languages = [{"name": "Arabic", "level": "Native"}, {"name": "Français", "level": "Fluent"}, {"name": "English", "level": "B2"}]
    p.education = [{"degree": f"Master {i}", "school": f"École {i}", "dates": f"200{i}", "description": "Mention très bien."} for i in range(4)]
    return p


class Categories(unittest.TestCase):
    def test_exactly_five_categories_including_others(self):
        cats = {t.category for t in TEMPLATES}
        self.assertEqual(5, len(cats)); self.assertEqual(set(CATEGORIES), cats); self.assertIn("Others", cats)
        self.assertEqual(5, len(CATEGORIES))

    def test_no_template_removed_and_ids_unchanged(self):
        self.assertEqual(ORIGINAL_IDS, {t.id for t in TEMPLATES}); self.assertEqual(30, len(TEMPLATES))

    def test_every_template_has_a_distinct_design(self):
        sig = Counter((t.layout, t.font, tuple(sorted((k, v) for k, v in t.opts.items() if k != "order"))) for t in TEMPLATES)
        self.assertEqual([], [k for k, v in sig.items() if v > 1])
        self.assertGreaterEqual(len({t.color for t in TEMPLATES}), 29)      # (one colour is intentionally shared by two designs)


class Robustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.dir = pathlib.Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _text(self, pdf):
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not available")
        return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout

    def test_all_templates_render_long_cv_completely_in_pdf_and_docx(self):
        p = long_profile()
        for t in TEMPLATES:
            p.template_id = t.id
            pdf = export_pdf(p, self.dir / f"{t.id}-long.pdf")
            txt = self._text(pdf)
            for needle in ("Role 0", "Role 8", "Compétence 17", "Master 3", "Résultat n°3"):
                self.assertIn(needle, txt, f"{t.id} lost '{needle}' in PDF")
            xml = zipfile.ZipFile(export_docx(p, self.dir / f"{t.id}-long.docx")).read("word/document.xml").decode("utf-8")
            for needle in ("Role 0", "Role 8", "Master 3", "Hélène"):
                self.assertIn(needle.lower(), xml.lower(), f"{t.id} lost '{needle}' in DOCX")      # (CAPS name styles upper-case the name)

    def test_empty_and_minimal_cvs_have_no_empty_section_headings(self):
        for t in TEMPLATES:
            p = CVProfile(full_name="Only Name", template_id=t.id)
            txt = self._text(export_pdf(p, self.dir / f"{t.id}-min.pdf")).upper()
            for heading in ("EXPERIENCE", "EDUCATION", "SKILLS", "PROJECTS", "PROFILE"):
                self.assertNotIn(heading, txt, f"{t.id} shows an empty {heading} section")
            self.assertIn("ONLY NAME", txt)
            export_docx(p, self.dir / f"{t.id}-min.docx")                # must not raise either

    def test_old_profile_data_still_loads_and_exports(self):
        old = json.loads(json.dumps({k: v for k, v in sample_profile().to_dict().items() if k != "template_chosen"}))
        p = CVProfile.from_dict(old)
        self.assertFalse(p.template_chosen)
        for tid in ("modern_summit", "senior_pinnacle", "technical_terminal"):
            p.template_id = tid; export_pdf(p, self.dir / f"o-{tid}.pdf"); export_docx(p, self.dir / f"o-{tid}.docx")

    def test_monogram_replaces_empty_photo_space_only_when_photos_are_on(self):
        self.assertGreater(len(monogram_png("Alex Morgan", "#336699", "#FFFFFF").getvalue()), 500)
        p = sample_profile(); p.template_id = "modern_summit"
        p.show_photo = True; with_img = export_pdf(p, self.dir / "m1.pdf").read_bytes()
        p.show_photo = False; without = export_pdf(p, self.dir / "m2.pdf").read_bytes()
        self.assertIn(b"/Subtype /Image", with_img); self.assertNotIn(b"/Subtype /Image", without)

    def test_word_export_is_editable_with_named_styles_and_real_bullets(self):
        import re
        from docx import Document
        p = long_profile()
        for tid in ("modern_summit", "minimal_paper", "modern_horizon", "technical_terminal", "creative_studio", "senior_legacy"):
            p.template_id = tid
            path = export_docx(p, self.dir / f"edit-{tid}.docx")
            with zipfile.ZipFile(path) as z:
                styles, doc = z.read("word/styles.xml").decode(), z.read("word/document.xml").decode()
                self.assertIn("word/numbering.xml", z.namelist())
            for sid in ("CVName", "CVHeadline", "CVSectionHeading", "CVJobTitle", "CVDetails", "CVBody", "CVBullet"):
                self.assertIn(f'w:styleId="{sid}"', styles, f"{tid}: style {sid} missing")
            self.assertGreater(doc.count('w:val="CVBullet"'), 20)               # bullets are real list items
            self.assertNotIn("•", doc)                                          # ...not typed characters
            d = Document(str(path))                                            # a user can open, add text in the template style, save
            d.add_paragraph("Added by the user", style="CV Body"); d.save(str(self.dir / f"edited-{tid}.docx"))
            self.assertIn("Added by the user", "\n".join(x.text for x in Document(str(self.dir / f"edited-{tid}.docx")).paragraphs))

    def test_pdf_has_real_text_embedded_fonts_and_no_restrictions(self):
        p = long_profile()
        for tid in ("modern_summit", "minimal_paper", "technical_terminal"):
            p.template_id = tid
            raw = export_pdf(p, self.dir / f"pdf-{tid}.pdf").read_bytes()
            self.assertNotIn(b"/Encrypt", raw)                                  # no password / permission restrictions
            self.assertIn(b"/FontFile2", raw)                                   # fonts are embedded
            self.assertIn("Role 0", self._text(self.dir / f"pdf-{tid}.pdf"))   # selectable text, not an image of text

    def test_docx_files_are_valid_zip_packages_for_every_template(self):
        p = sample_profile()
        for t in TEMPLATES:
            p.template_id = t.id
            with zipfile.ZipFile(export_docx(p, self.dir / f"{t.id}.docx")) as z:
                self.assertIsNone(z.testzip()); self.assertIn("word/document.xml", z.namelist())


if __name__ == "__main__":
    unittest.main()
