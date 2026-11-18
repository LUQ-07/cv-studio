# Changelog

## 1.0.0 – prepared for public release on GitHub (version unchanged)
- Project is published as open source (MIT). Microsoft Store packaging (MSIX), Store listing documents and the Store-only build dependencies were removed from the repository; releases are Windows zips built by GitHub Actions.
- Added README, CONTRIBUTING, SECURITY, issue / pull-request templates, test and release workflows, `.gitattributes`.
- Developer reports moved to `docs/development/`. The app itself is unchanged. (The optional Store purchase code in `cvstudio/store_iap.py` is dormant and never runs in this edition.)

## 1.0.0 – Go back, filter clean-up, editable exports (version unchanged)
- **Go back** button (← Go back, rounded accent style, shortcut Alt+Left) next to ☰: returns to the previous page, and for the CV editor to the tab you were on. It appears only when there is a page to go back to; no data is touched.
- Template filter: the "Free" entry is gone (everything is free in this edition). Categories stay exactly five (Modern, Minimal, Professional, Creative, Others); the remaining technical / academic / entry-level styles are in Others. Favorites and ATS-friendly remain as filters, not categories.
- **Word export is easier to modify**: real bullet lists (Enter adds the next bullet) and named styles (CV Name, CV Headline, CV Section Heading, CV Job Title, CV Details, CV Body, CV Bullet) that appear in Word's Styles gallery, so text you add matches the template. Appearance unchanged.
- **PDF**: unchanged; verified to contain real selectable text, embedded fonts and no restrictions.

## 1.0.0 – UI & template enhancement (version unchanged)
- **Collapsible sidebar**: ☰ button (always visible) slides the sidebar away/back with a 220 ms animation; current page and data untouched.
- **Templates upgraded** (same 30 ids, none removed): new typography/spacing/heading styles (rule, short rule, band, dot, bar, centred, plain), name styles, date placement, skill displays (bars, dots, plain, tidy columns), density levels, monogram circle instead of an empty photo gap, refined palettes. Every template is now distinct by more than colour. PDF and DOCX follow the same design.
- **Exactly five categories**: Modern, Minimal, Professional, Creative, Others. Section order for entry-level / academic / technical CVs is now a per-template style option instead of depending on the old category names.
- **Gallery cards**: each template card has **USE THIS TEMPLATE** and **ADD TO FAVORITES** (visual favourite state, no duplicates, persisted in settings). Selected template is highlighted (`template_chosen` flag in the CV); opening the page selects nothing. Click a card to see a large preview with your own data. Sharper thumbnails (rendered from the real PDF); the thumbnail cache is keyed by design revision so old thumbnails are dropped.
- Fixed: the category filter used wrong indexes in the Standard edition (it could hide templates).
- See `docs/UI_TEMPLATE_ENHANCEMENT.md`.

## 1.0.0 – template selection workflow correction (version unchanged)
- Removed the extra "Choose template" button from the editor header; the existing Templates section in Preview & export is the single entry point. "Use this template" applies, saves and refreshes the preview. Template preview fits its pane. See `docs/TEMPLATE_WORKFLOW_FIX.md`.

## 1.0.0 – first public (Microsoft Store) release
Versions 1.1 – 2.1 below were internal development builds and were never published; the first public release is numbered **1.0.0** (MSIX 1.0.0.0). History is kept unchanged below.
- Version references unified to 1.0.0 (`__init__`, `pyproject`, `build_msix.ps1`, README, Store docs).
- Homepage tagline now reads "Professional designs · PDF & editable Word · 100% private" (templates unchanged: 30).
- Store IAP: licence checks now time out after 25 s instead of waiting forever; Store ID is sanitised in the fallback Store URL.
- Storage: database connections are now closed after use (no Windows file locks); a damaged CV row no longer crashes *open*; *Restore from backup* skips invalid rows and takes a safety backup before merging.
- Project cleaned (`__pycache__`, bundled old backup zip). No updater exists or was added. See `docs/CLEANUP_REPORT.md`, `docs/CHANGE_REPORT.md`.

## 2.1.0
- **Data tabs rebuilt** (`SectionPanel`, `sections.py`): each of the 16 tabs shows its own inline form (e.g. Languages: name + proficiency; Projects: title, role, technologies, link, description), *Add New Entry* / *Update Entry*, entry list, *double-click to edit*, *Delete* (with confirmation + Delete key), reorder. Required-field validation. All data lives in one central dict (`MainWindow.cv_data`) that feeds the PDF/DOCX/preview. Always free.
- **Premium templates via Microsoft Store add-on** (`store_iap.py`): 5 free / 25 Premium, background ownership check, UI-thread purchase, Store-page fallback, no UI freezes. See `store/IAP_SETUP.md`.
- Templates gallery: Free / Premium filters, lock badges, unlock button with localised price.
- `tools/clean.py`, `hooks/hook-winrt.py`, `build_exe.ps1`, `build_msix.ps1 -OneFile`.

## 2.0.0
**Audit findings in 1.1 (verified in code):** all 30 templates were one single-column layout; only colour/font/heading text changed. The DOCX exporter ignored the template (only name alignment + colour). The PDF header/sidebar "layouts" were a thin coloured strip. "Add" in list editors overwrote the selected entry instead of adding one (bug). PDF used base-14 fonts (no Unicode beyond Latin-1). Preview was an HTML approximation, not the PDF. Overwrite protection and failed-export recovery were missing.

**Templates / layout engine** – new `templates.py`, `design.py`, `exporter.py`, `docx_export.py`. 8 structures (sidebar, light sidebar, right sidebar, banner, classic, minimal, bold, compact), per-template palettes, bundled Carlito/Caladea/DejaVu Mono, skill bars, circular photo, bullet lists from `- ` lines, clickable links, multi-page flow, A4/Letter.
**DOCX** – real tables, shading, borders, tab-stops and hyperlinks; sidebar shading extended across pages.
**Editor** – added Courses, Publications, Internships, Memberships, References, Interests; show/hide + reorder sections; fixed Add bug.
**Projects** – duplicate, rename, backup (auto on close/delete), save/restore `.cvbackup`, atomic settings, legacy `CVStudioPro` data migrated.
**GUI** – new theme system (light/dark/system), PDF-based preview with zoom, template gallery (thumbnails, search, categories, ATS filter, favourites, live preview with *your* data), separate Export PDF / Export Word, overwrite confirmation, partial-file safe export, About page.
**Languages** – English, French, Spanish, Arabic (RTL) – switch without restart.
**Packaging** – Windows-only: PyInstaller spec, MSIX manifest/build/sign scripts, GitHub Actions workflow; macOS/Linux scripts moved to `extras/other-platforms/` (unsupported in this release).
