# Known limitations (1.0.0)

- **Arabic text inside a CV is not supported yet**: the bundled fonts have no Arabic glyphs and the PDF engine does not shape right-to-left text. The *interface* is available in Arabic (right-to-left); CV content in French, Spanish, English and other Latin scripts works.
- Some secondary interface texts (hints, job-tool report text) are still English-only.
- The Word export is a close approximation of the PDF, not identical (different layout engines). Sidebar shading extends over at most about two pages (Word's row-height limit). Skill levels in Word use Unicode symbols (Segoe UI Symbol).
- Profile photos are always cropped to a circle.
- Automated tests cover the engine and data layer (and GUI *logic* with a Qt stand-in). Real window rendering is checked by hand; there are no automated GUI tests.
- Only Windows builds are provided. Running from source on macOS/Linux should work with PySide6 but is untested.
- There is no auto-update: download new versions from the GitHub Releases page.
- `cvstudio/store_iap.py` and the `PREMIUM_FEATURES` switch are dormant leftovers from a Store edition that was never published; they are off and make no network or Store calls.
