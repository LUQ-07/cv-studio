# Cleanup report – CV Studio 1.0.0

Original project (as received) is preserved **outside** the project: `CV_Studio_Pro_ORIGINAL_BACKUP_as_received.zip` (delivered next to the final ZIP). The old v1.1 backup is also kept separately as `ORIGINAL_v1.1_backup.zip`.

## Removed
| Item | Why unnecessary | How verified |
|---|---|---|
| `cvstudio/__pycache__/` (16 `.pyc`), `tests/__pycache__/` | Python bytecode generated at run time; must not ship | Regenerated automatically; project runs/tests pass without them |
| `backup/ORIGINAL_v1.1_backup.zip` (and the empty `backup/`) | Historical backup the owner asked to exclude | Byte-compared copy kept outside the project (`cmp` + `unzip -t` OK); no code/script/doc references `backup/` |

## Preserved although they looked optional (importance uncertain or documented use)
| Item | Reason |
|---|---|
| `extras/other-platforms/build_linux.sh`, `build_macos.sh` | Unreferenced by the Windows release, but they belong to the owner's original project and cost 2 KB. Delete if you will never ship those platforms |
| `examples/sample_profile.json` | Not referenced by code or tests, but it is the owner's sample data (demonstration use) |
| `docs/*.png` (3 images) | Referenced by README/TEST_REPORT as visual proof |
| `tools/clean.py`, `hooks/hook-winrt.py`, `build_exe.ps1`, `packaging/windows/sign_test.ps1`, `requirements-build.txt`, `CV Studio.spec` | Used by build scripts / documented procedures |
| `.github/workflows/windows-build.yml` | Existing CI/build process |
| All 12 font files + 3 licence texts | All four styles of each family are registered by `design.pdf_font`; licences required |
| All `packaging/windows/Assets/*` incl. `targetsize-*` | Referenced by the manifest / Windows icon scaling |
| `store/*`, `tests/*`, `LICENSE`, `NOTICE.md` | Required for submission, QA and licensing |

## Python modules
All 16 modules are imported by an entry point (`run_app.py`, `__main__.py`) or by another module/test – none removed.
## Dependencies
None removed. Runtime: PySide6, reportlab, python-docx, Pillow, and (Windows only) the pywinrt wheels used by `store_iap`. The extra `winrt-Windows.*` wheels (ApplicationModel, Storage, System, Web.Http, Foundation.Collections) may be pulled in automatically by `winrt-Windows.Services.Store`; they are kept because that could not be confirmed without Windows.
## Files moved: none.
## Verification after cleanup
Tests 40/40 · `compileall` · all imports · fonts/icons/assets exist · 30 PDF + 30 DOCX exports · manifest asset references · no `__pycache__`/`.pyc` in the final ZIP.
