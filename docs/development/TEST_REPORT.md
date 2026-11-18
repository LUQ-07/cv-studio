# Test report – CV Studio 1.0.0 (first public release)

Environment: Linux, Python 3.12, ReportLab, python-docx, Pillow, LibreOffice (DOCX viewer), poppler. **No Windows, no PySide6, no Microsoft Store account were available.**
Legend: **PASS** run and passed · **NOT TESTED** could not be run here · **STORE** needs Microsoft Store / Partner Center to verify.

## Test-suite
| Run | Result |
|---|---|
| Before any change (the project as received) | 21 tests – PASS |
| After all changes | 40 tests – PASS (the 21 original tests are unchanged; 19 were added in `tests/test_release.py`) |
| `compileall` of all Python | PASS |

## Requirement checklist (section 11)
| Item | Status | How |
|---|---|---|
| Application startup / main interface | NOT TESTED (real Qt) | Only a *stubbed-Qt* construction of `MainWindow` in EN/FR/AR (names, init order, 25 code paths) – PASS but proves nothing about rendering |
| CV creation / editing | PASS (data layer) · NOT TESTED (GUI) | `SectionModel` CRUD tests; editor widgets untested on real Qt |
| Profile save / load / delete | PASS | storage tests |
| Backup and restore | PASS | incl. new: invalid rows skipped, safety backup taken, no handles left open |
| PDF export | PASS | 30/30 templates valid (`pdfinfo`), multi-page, Unicode/accents, photo |
| Word DOCX export | PASS | 30/30 opened by LibreOffice; page counts match PDF. **Microsoft Word itself not tested** |
| Template gallery | NOT TESTED (visual) | list/filter code runs with stub Qt; contact sheet `docs/template-gallery-overview.png` is the PDF output |
| Free templates / Premium restrictions | PASS (logic) | 5 free / 25 premium; gate rule; MainWindow flow with stub Qt (owned → export, unavailable → refuse, success → export, cancelled → nothing) |
| Purchase handling, cancel, failure | PASS against a **fake** winrt · STORE for real | all `StorePurchaseStatus` values mapped |
| Premium restoration / restart / update | PASS against fake · STORE for real | ownership is re-read from the Store licence on every start; nothing is stored locally; a fresh service starts locked |
| Offline behaviour | PASS (logic) · STORE | not owned + unreachable → UNAVAILABLE (locked); cached licence offline = Microsoft behaviour, verify |
| Hung Store call | PASS | new 25 s timeout |
| Arabic / RTL | PASS (tables, RTL flag) · NOT TESTED (real RTL layout). Arabic *CV content* is a documented limitation |
| French / English translations | PASS | table completeness and sample strings |
| Light / dark theme | PASS (stylesheets build, balanced braces) · NOT TESTED (visual contrast) |
| Application restart / persistence | PASS | profiles and settings reopened |
| Version 1.0.0 | PASS | `__init__`, `pyproject`, `build_msix.ps1` (1.0.0.0), README, checklist |
| About section shows "Version 1.0.0" | PASS (source-level: `f"Version {__version__}"`) · NOT TESTED (on screen) |
| Homepage sentence | PASS (source-level) · NOT TESTED (on screen) |
| No automatic updater | PASS | AST scan: no network-capable imports; no updater identifiers; manifest has no AppInstaller/auto-update |
| No payment data / fake success in source | PASS | static scan |
| Imports, resources, fonts, packaging paths | PASS | every module imported by an entry point/test; 12 fonts, icons, manifest assets, build-script paths exist |
| MSIX manifest | PASS (XML well-formed, 4-part version ending in 0, `runFullTrust`, all asset files exist) |
| MSIX package generation (`makeappx`), PyInstaller build, install/upgrade/uninstall | NOT TESTED – needs Windows + SDK. Use `packaging/windows/build_msix.ps1` or the GitHub workflow |
| Windows App Certification Kit, Partner Center validation, certification | STORE |
| No unnecessary files left | PASS – see `docs/CLEANUP_REPORT.md` |

## Known unverified high-risk piece
`store_iap.associate_window()` (ties the Store context to the app window via ctypes/pywinrt). If it does not work with the installed pywinrt, the payment window will not open and the app offers the Store page instead. Verify first on a real Store-associated package.

## Template-workflow correction addendum
| Check | Result |
|---|---|
| Baseline before changes | 42 tests PASS |
| After changes | 48 tests PASS (6 new in `test_template_workflow.py`) |
| No "Choose template" button / `open_template_gallery` left; one Templates button opens the gallery | PASS (logic, Qt stand-in) |
| "Use this template" visible only with a selection | PASS (logic) |
| Apply keeps all CV data, saves, survives reopening the store, refreshes preview | PASS (logic, real SQLite store) |
| PDF and DOCX follow the selected template (font family differs serif vs sans) | PASS |
| Preview width fits pane | PASS (pure function) |
| Real window: clicks, layout, screenshot-level appearance, startup on Windows | NOT TESTED |
| Microsoft Store / Partner Center behaviour | Requires Store verification (unchanged) |

## UI & template enhancement addendum
| Check | Result |
|---|---|
| Baseline before changes | 48 tests PASS |
| After changes | 62 tests PASS |
| Sidebar hide/show: state, animation start/end values, button stays reachable, page and data unchanged | PASS (logic, Qt stand-in) · smoothness on screen NOT TESTED |
| Exactly five categories incl. Others; 30 templates, ids unchanged; every design distinct | PASS |
| All 30 templates × (long CV with accents, empty CV, old profile data): PDF text complete, DOCX complete, no empty section headings | PASS (pdftotext / DOCX XML) |
| DOCX vs PDF page count for a long CV (LibreOffice) | PASS 30/30 equal (Microsoft Word itself NOT TESTED) |
| Visual review of all 30 PDFs, edge cases (minimal, long, with photo) | Done by viewing renders; no overlap/clipping seen |
| USE THIS TEMPLATE on every card, applies, keeps data, saves, highlights; nothing auto-selected | PASS (logic) |
| ADD TO FAVORITES on every card; toggle, no duplicates, persists via new Settings instance | PASS |
| Export (PDF/DOCX) follows applied template | PASS |
| Real window: card layout, animation smoothness, QSS appearance, high-DPI, Arabic RTL layout, Windows | NOT TESTED |
| Same code with the Premium flag on | Only the Standard-only test fails, as expected (informational run) |

## Go back / filter / editable exports addendum
| Check | Result |
|---|---|
| Suite | 66 tests PASS (62 before + 4 new) |
| Go back: hidden at start; visible after navigating; restores page and editor tab; chain of pages; empty history does nothing; data untouched | PASS (logic, Qt stand-in) |
| Filter has no "Free" entry; exactly five categories | PASS |
| Word: named styles present, bullets are real list items (no typed "•"), numbering part present; file re-opened, text added in the template style, saved and re-read (6 templates) | PASS |
| Word rendering unchanged after the bullet change (LibreOffice render viewed) | PASS · Microsoft Word itself NOT TESTED |
| PDF: no /Encrypt, fonts embedded, text extractable | PASS |
| Look of the Go back button and its click on a real window | NOT TESTED |
