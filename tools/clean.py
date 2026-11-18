"""Delete development leftovers: __pycache__, .pyc/.pyo, PyInstaller/MSIX build output, test caches.

    python tools/clean.py            # safe clean (keeps virtualenvs and your .spec file)
    python tools/clean.py --all      # also removes .venv, .venv-build and dist/
    python tools/clean.py --dry-run  # show what would be removed
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "build", "msix_layout"}
FILE_GLOBS = ["*.pyc", "*.pyo", "*.partial.pdf", "*.partial.docx", "*.log"]
ALL_ONLY = {"dist", ".venv", ".venv-build"}


def main(argv):
    everything, dry = "--all" in argv, "--dry-run" in argv
    names = DIR_NAMES | (ALL_ONLY if everything else set())
    removed = 0
    for path in sorted(ROOT.rglob("*")):
        if any(part in {".git", ".venv", ".venv-build"} for part in path.relative_to(ROOT).parts[:-1]) and not everything:
            continue
        if path.is_dir() and path.name in names:
            print(("would remove " if dry else "removed ") + str(path.relative_to(ROOT)))
            if not dry: shutil.rmtree(path, ignore_errors=True)
            removed += 1
        elif path.is_file() and any(path.match(g) for g in FILE_GLOBS):
            print(("would remove " if dry else "removed ") + str(path.relative_to(ROOT)))
            if not dry: path.unlink(missing_ok=True)
            removed += 1
    print(f"\n{removed} item(s) {'found' if dry else 'removed'}.")


if __name__ == "__main__":
    main(sys.argv[1:])
