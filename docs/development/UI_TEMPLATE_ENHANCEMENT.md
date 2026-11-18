# UI & template enhancement report (version stays 1.0.0)

## Modified / added files
| File | Change |
|---|---|
| `cvstudio/gui.py` | ☰ sidebar toggle + animation (`toggle_sidebar`); gallery rebuilt as template cards (`TemplateCard`, `CardScroll`, `ClickableLabel`); `choose_template(tid)`, `toggle_favorite(tid)`, `_preview_template`; filter by category fixed; thumbnails cache keyed by design revision; `PdfPane.clear()` |
| `cvstudio/templates.py` | 5 categories (`CATEGORIES`), per-template `style` options (`Template.opts`), `DESIGN_REV`, refined descriptions |
| `cvstudio/design.py` | section order from template option, `monogram_png`, `on_color`, `initials` |
| `cvstudio/exporter.py` | PDF: heading variants, skill variants (bars/dots/plain/columns), date placement, name styles, density, monogram |
| `cvstudio/docx_export.py` | DOCX parity with the PDF (same variants; banner header rebuilt so name and picture sit side by side) |
| `cvstudio/models.py` | `template_chosen: bool = False` (old data loads unchanged) |
| `cvstudio/settings.py` | favourites de-duplicated on load |
| `cvstudio/theme.py`, `cvstudio/i18n.py` | card/burger styles; EN/FR/ES/AR strings |
| `tests/test_template_workflow.py` (rewritten), `tests/test_template_design.py` (new), `tests/test_release.py` (1 assertion) | see below |
| README / CHANGELOG / EDITION_NOTES / TEST_REPORT / this file | documentation |

## Notes
* Tests that required the old single "Use this template" button in the detail pane were rewritten, because the requirement changed to one button per card and no automatic selection.
* USE THIS TEMPLATE still opens the Preview afterwards (existing behaviour); the highlight is visible when you return to the gallery and on the card of the applied template.
* The detail pane on the right keeps the large preview (with the user's own data) of the clicked card; it contains no duplicate buttons.
* Favourite button text: **ADD TO FAVORITES**; when favourited: **★ REMOVE FAVORITE** (plus ★ in the name and highlighted button).
* The existing "Free" filter entry of the Standard edition was left as it was.

## Follow-up: Go back, filter, editable exports
* `gui.py`: `go_back()`, `_update_back()`, history recorded in `navigate()`; `back_btn` in the top bar. `theme.py`: `QPushButton#Back`. `i18n.py`: "Go back" (EN/FR/ES/AR).
* `gui.py`: filter keys no longer contain "free" unless the Premium flag is on.
* `docx_export.py`: `_apply_style()` (named styles), `_bullet()` now creates real list items (falls back to the typed bullet if the "List Bullet" style is unavailable). No other DOCX code changed.
* PDF export untouched. PDF is a final-layout format: text is real and selectable (editable in PDF editors that can edit text), but for comfortable editing use the Word export or change the data in the app and export again.
