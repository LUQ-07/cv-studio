# Template selection workflow correction (version stays 1.0.0)

**Workflow:** complete CV information → **Preview & export** → existing **Templates** button → gallery → select a template → **Use this template** → template applied, saved, preview refreshed.

## Removed (incorrectly added interface)
* The extra **"Choose template"** button in the CV-editor header (`gui.py`, `_make_editor`) and its method `open_template_gallery()`. The gallery is reached only through the existing Templates entry points (the Templates button inside Preview & export, and the original sidebar page).

## Corrected / kept
* **Use this template** (`choose_template`): collects the current form data, sets `profile.template_id` and the template's own accent colour, saves through `save_profile` (existing SQLite store), then `open_preview()` re-renders the real PDF preview. No other CV field is touched. The button is now shown only while a template is selected (`self.use_btn`).
* Selecting a template still renders its preview with the user's own data. The preview now fits its pane (`page_width()`, resize-aware); before, the page was fixed at 820 px and cut off on the right in the narrow gallery pane (see the screenshot that motivated this).
* New translation of the message "Select a template first" (FR/ES/AR).

## Not changed
Premium restrictions, purchase code, Store code (Premium edition); no Premium UI in Standard; storage; exporters; templates; version (1.0.0).

## Tests
`tests/test_template_workflow.py` (+ `tests/_qtstub.py`, a Qt stand-in) covers: no duplicate "Choose template", exactly one Templates button that opens the gallery, Use-button visibility, data preserved + saved + reloaded + preview refreshed for free/banner/premium templates, nothing selected changes nothing, PDF/DOCX use the chosen template's fonts, preview width rule. The old `test_release` assertion that required the wrong button was replaced by assertions for the corrected workflow.
Not covered: pixel rendering of real Qt widgets, real click events, Windows.
