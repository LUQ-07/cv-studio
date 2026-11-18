"""Local SQLite storage. CV information never leaves this device."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from .models import CVProfile


class _ClosingConnection(sqlite3.Connection):
    """`with conn:` normally commits but leaves the file open (a lock on Windows); this also closes it."""

    def __exit__(self, *exc):
        try:
            return super().__exit__(*exc)
        finally:
            self.close()


def app_data_dir() -> Path:
    import os
    root = os.environ.get("APPDATA") if os.name == "nt" else None
    if root:
        base = Path(root)
    elif __import__("sys").platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "CVStudio"
    legacy = base / "CVStudioPro"
    if not path.exists() and legacy.exists():   # keep customers' CVs from earlier builds
        import shutil
        try:
            shutil.copytree(legacy, path)
        except OSError:
            pass
    path.mkdir(parents=True, exist_ok=True)
    return path


class ProfileStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else app_data_dir() / "profiles.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS profiles (id TEXT PRIMARY KEY, title TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS exports (id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT, file_path TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    def _connect(self):
        db = sqlite3.connect(self.path, factory=_ClosingConnection)
        db.row_factory = sqlite3.Row
        return db

    def save(self, profile: CVProfile) -> None:
        data = json.dumps(profile.to_dict(), ensure_ascii=False)
        with self._connect() as db:
            db.execute("INSERT INTO profiles(id,title,data) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,data=excluded.data,updated_at=CURRENT_TIMESTAMP", (profile.id, profile.title or profile.full_name or "My CV", data))

    def load(self, profile_id: str) -> CVProfile | None:
        with self._connect() as db:
            row = db.execute("SELECT data FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if not row:
            return None
        try:
            return CVProfile.from_dict(json.loads(row["data"]))
        except (ValueError, TypeError):      # a damaged row must not crash the app
            return None

    def list_profiles(self) -> list[dict]:
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT id,title,updated_at FROM profiles ORDER BY updated_at DESC")]

    def delete(self, profile_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
            db.execute("DELETE FROM exports WHERE profile_id=?", (profile_id,))

    def clear_all(self) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM profiles")
            db.execute("DELETE FROM exports")

    def record_export(self, profile_id: str, file_path: str) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO exports(profile_id,file_path) VALUES(?,?)", (profile_id, file_path))

    def history(self, profile_id: str | None = None) -> list[dict]:
        with self._connect() as db:
            if profile_id:
                rows = db.execute("SELECT * FROM exports WHERE profile_id=? ORDER BY created_at DESC", (profile_id,))
            else:
                rows = db.execute("SELECT * FROM exports ORDER BY created_at DESC")
            return [dict(r) for r in rows]

    def duplicate(self, profile_id: str, suffix: str = " (copy)") -> "CVProfile | None":
        profile = self.load(profile_id)
        if not profile:
            return None
        from .models import new_id
        profile.id = new_id()
        profile.title = (profile.title or "My CV") + suffix
        self.save(profile)
        return profile

    def rename(self, profile_id: str, title: str) -> None:
        profile = self.load(profile_id)
        if profile and title.strip():
            profile.title = title.strip()
            self.save(profile)

    def backup(self, keep: int = 5) -> Path | None:
        """Copy the database to a timestamped backup; keep the newest few."""
        import shutil, time
        try:
            folder = self.path.parent / "backups"
            folder.mkdir(exist_ok=True)
            target = folder / time.strftime("profiles-%Y%m%d-%H%M%S.sqlite3")
            with self._connect() as src, closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
            for old in sorted(folder.glob("profiles-*.sqlite3"))[:-keep]:
                old.unlink(missing_ok=True)
            return target
        except (OSError, sqlite3.Error):
            return None

    def backup_to(self, target: str | Path) -> Path:
        """Copy the whole database to a location the user chose (survives uninstall)."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as src, closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
        return target

    def restore_from(self, source: str | Path) -> int:
        """Merge CVs from a backup file; returns how many valid CVs were imported.

        Rows that are not valid CV data are skipped. A safety backup of the current database is taken first,
        because a restored CV with the same id replaces the current one."""
        with closing(sqlite3.connect(f"file:{Path(source).as_posix()}?mode=ro", uri=True)) as src:
            rows = src.execute("SELECT id,title,data FROM profiles").fetchall()
        valid = []
        for pid, title, data in rows:
            try:
                if not (isinstance(pid, str) and pid and isinstance(title, str) and isinstance(data, str)):
                    continue
                CVProfile.from_dict(json.loads(data))
                valid.append((pid, title, data))
            except (ValueError, TypeError):
                continue
        if valid:
            self.backup()
        with self._connect() as db:
            for pid, title, data in valid:
                db.execute("INSERT INTO profiles(id,title,data) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,data=excluded.data,updated_at=CURRENT_TIMESTAMP", (pid, title, data))
        return len(valid)
