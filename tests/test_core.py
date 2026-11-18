import tempfile
import unittest
from pathlib import Path

from cvstudio.models import CVProfile, sample_profile
from cvstudio.storage import ProfileStore
from cvstudio.templates import TEMPLATES, get_template
from cvstudio.validation import validate_profile
from cvstudio.exporter import export_pdf
from cvstudio.docx_export import export_docx
from cvstudio.preview import render_html
from cvstudio.job_tools import analyze_job_match, draft_cover_letter
from cvstudio.exporter import export_cover_letter_pdf
from cvstudio.docx_export import export_cover_letter_docx


class CoreTests(unittest.TestCase):
    def test_thirty_distinct_named_templates(self):
        self.assertEqual(30, len(TEMPLATES))
        self.assertEqual(30, len({t.id for t in TEMPLATES}))
        self.assertEqual(8, len({t.layout for t in TEMPLATES}))
        self.assertGreaterEqual(len({t.color for t in TEMPLATES}), 28)
        self.assertIs(get_template("missing"), TEMPLATES[0])

    def test_profile_round_trip_and_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ProfileStore(Path(tmp)/"data.sqlite3")
            profile=sample_profile();store.save(profile)
            loaded=store.load(profile.id)
            self.assertEqual(profile.to_dict(),loaded.to_dict())
            self.assertEqual(profile.id,store.list_profiles()[0]["id"])
            store.delete(profile.id)
            self.assertIsNone(store.load(profile.id))

    def test_validation_does_not_require_optional_fields(self):
        profile=CVProfile()
        self.assertEqual([],validate_profile(profile))
        profile.email="bad-address"
        profile.links=[{"label":"Portfolio","url":"portfolio.test"}]
        self.assertEqual(2,len(validate_profile(profile)))

    def test_pdf_and_docx_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=sample_profile()
            pdf=export_pdf(profile,Path(tmp)/"cv.pdf")
            self.assertGreater(pdf.stat().st_size,500)
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
            self.assertIn(b"%%EOF",pdf.read_bytes()[-1024:])
            docx=export_docx(profile,Path(tmp)/"cv.docx")
            self.assertGreater(docx.stat().st_size,500)
            self.assertEqual(b"PK",docx.read_bytes()[:2])

    def test_every_layout_renders_and_long_cv_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=sample_profile()
            profile.experience *= 5
            profile.experience[0]["description"] = "A detailed achievement. " * 100
            for template in TEMPLATES:
                profile.template_id=template.id
                self.assertIn(template.layout,render_html(profile))
                output=export_pdf(profile,Path(tmp)/(template.id+".pdf"))
                self.assertGreater(output.stat().st_size,1000)
                docx=export_docx(profile,Path(tmp)/(template.id+".docx"))
                self.assertGreater(docx.stat().st_size,1500)

    def test_unicode_french_and_photo(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            img=Path(tmp)/"p.png";Image.new("RGB",(300,200),"#336699").save(img)
            profile=sample_profile();profile.full_name="Hélène Ben Aïssa";profile.photo_path=str(img)
            profile.summary="Ingénieure passionnée — œuvres, café, à Casablanca, Maroc."
            for tid in ("modern_summit","modern_horizon","minimal_paper"):
                profile.template_id=tid
                self.assertGreater(export_pdf(profile,Path(tmp)/(tid+".pdf")).stat().st_size,1000)
                self.assertGreater(export_docx(profile,Path(tmp)/(tid+".docx")).stat().st_size,1500)

    def test_job_description_review_and_cover_letter(self):
        profile=sample_profile()
        result=analyze_job_match(profile,"Product designer. Figma. Python. Accessibility. Communication.")
        self.assertIn("figma",result["matched"])
        self.assertIn("python",result["missing"])
        self.assertEqual(67,result["coverage"])
        letter=draft_cover_letter(profile,"Product Designer","Acme","Hiring Manager","I value the team's accessibility work.","I led onboarding improvements.")
        self.assertIn("Acme",letter);self.assertIn("led onboarding",letter)
        self.assertNotIn("[Add a specific reason",letter)
        with tempfile.TemporaryDirectory() as tmp:
            pdf=export_cover_letter_pdf(profile,letter,Path(tmp)/"letter.pdf")
            docx=export_cover_letter_docx(profile,letter,Path(tmp)/"letter.docx")
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"));self.assertEqual(b"PK",docx.read_bytes()[:2])


if __name__ == "__main__": unittest.main()
