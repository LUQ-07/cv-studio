"""User settings (language, theme, favourites) stored as JSON in the Windows user-data folder."""
import json
import os
import tempfile
from pathlib import Path

from .storage import app_data_dir

DEFAULTS = {"language": "en", "theme": "system", "favorites": [], "last_export_dir": ""}


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else app_data_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
            favs = self.data.get("favorites")
            self.data["favorites"] = list(dict.fromkeys(f for f in favs if isinstance(f, str))) if isinstance(favs, list) else []   # no duplicates
        except (OSError, ValueError):
            pass

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        """Atomic write so a crash never leaves a half-written settings file."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def toggle_favorite(self, template_id) -> bool:
        favs = list(self.data["favorites"])
        if template_id in favs:
            favs.remove(template_id)
        else:
            favs.append(template_id)
        self.set("favorites", favs)
        return template_id in favs
