# Change report – CV Studio 1.0.0

Only the files below were modified. No algorithm, template, layout, translation or UI structure was changed.

| File | Why | What changed | Existing behaviour affected? | Tested by |
|---|---|---|---|---|
| `cvstudio/__init__.py` | First public release | `__version__` 2.1.0 → 1.0.0 (About page reads it; thumbnail-cache folder name follows it, harmless cache) | No | `test_release.VersionAndText` |
| `pyproject.toml` | Version | `version = "1.0.0"` | No | same |
| `packaging/windows/build_msix.ps1` | MSIX version | default `-Version "1.0.0.0"` | No | same + manifest test |
| `cvstudio/gui.py` | Homepage tagline | Only the text literal: "30 professional designs…" → "Professional designs…"; styles, sizes, layout untouched | No | `test_about_and_homepage_text` |
| `cvstudio/store_iap.py` | Robustness/security | (1) `asyncio.wait_for` (25 s) around the two Store lookups → returns UNAVAILABLE on a hung call instead of an endless "busy" state; (2) `store_page_url` keeps only alphanumerics of the Store ID. Purchase flow, ownership rule and product ID unchanged | No (only adds a timeout) | `test_hung_store_times_out…`, `test_store_page_url_is_sanitised`, original 14 store/section tests |
| `cvstudio/storage.py` | Data protection / Windows file locks | (1) connections closed after use (`_ClosingConnection`, `closing`); (2) `load` returns `None` for a damaged row instead of raising; (3) `restore_from` validates rows, skips invalid ones, takes a safety backup first. Schema unchanged, no migration | No schema/data change | `DataProtection` tests + original storage tests |
| `tests/test_release.py` | Release checks | **New file**; existing tests untouched | – | itself |
| `README.md`, `LIMITATIONS.md`, `store/SUBMISSION_CHECKLIST.md`, `store/STORE_LISTING.md`, `store/MONETIZATION.md` | Version consistency; Store disclosure (free vs Premium, in-app purchase) and IAP verification steps | text only | – | review |
| `CHANGELOG.md` | 1.0.0 entry added on top; **history preserved** | text only | – | – |
| `TEST_REPORT.md`, `docs/CLEANUP_REPORT.md`, `docs/CHANGE_REPORT.md` | Reports | rewritten/new | – | – |

Deleted files: see `docs/CLEANUP_REPORT.md`.
Update system: none existed; none added. (Updates are delivered by the Microsoft Store, not by the app.)
Security audit summary: local SQLite with parameterised queries ✔ · no network code ✔ · no logging of CV data ✔ · exports written via a partial file then atomic replace ✔ · only http(s)/mailto links are emitted into documents ✔ · temp preview files live in a per-session temp folder deleted on close (after a crash they remain in `%TEMP%` until Windows clears it – documented, not changed) ✔ · Premium unlock comes only from the Store licence; the developer shortcut `CVSTUDIO_DEV_UNLOCK` is ignored in packaged builds.
