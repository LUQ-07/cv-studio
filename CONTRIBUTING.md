# Contributing

Thanks for helping! Keep changes small and focused.

## Set up
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m cvstudio                      # run the app
python -m unittest discover -s tests -v # run the tests
```
The engine tests (templates, PDF, Word, storage) do not need Qt. Some tests use `pdftotext` (poppler) and skip themselves if it is missing.

## Where things are
| Path | What |
|---|---|
| `cvstudio/templates.py` | the 30 templates: id, category (exactly five), layout, colours, font and style options |
| `cvstudio/design.py` | palette and the content model every exporter uses |
| `cvstudio/exporter.py` / `docx_export.py` | PDF (ReportLab) and Word (python-docx) renderers |
| `cvstudio/gui.py`, `theme.py`, `i18n.py` | the PySide6 interface, styles, translations (EN/FR/ES/AR) |
| `cvstudio/storage.py`, `settings.py` | local SQLite store and JSON settings |
| `tests/` | unit tests (`_qtstub.py` lets GUI *logic* run without Qt) |

## Guidelines
* **Templates:** keep the five categories (Modern, Minimal, Professional, Creative, Others) and keep existing ids (saved CVs refer to them). When you change how templates look, bump `DESIGN_REV` in `templates.py` so cached thumbnails refresh. Check both the PDF and the Word export, with a short, a long and an almost empty CV.
* **Translations:** add every new interface string to all of fr/es/ar in `i18n.py` (a test checks they have the same keys).
* **Privacy:** no network code, no telemetry, no analytics. A test enforces that no network modules are imported.
* **Data compatibility:** saved CVs must keep loading (see `models.py`: unknown fields are ignored, new fields need defaults).
* Fonts and assets must be redistributable; add their licence to `NOTICE.md`.

## Pull requests
Describe what changed and why, and make sure the tests pass.
