"""Input validation that reports helpful issues without rejecting optional fields."""
import re


def validate_profile(profile) -> list[str]:
    issues = []
    email = (profile.email or "").strip()
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        issues.append("Check the email address format.")
    for item in profile.links:
        url = (item.get("url") or "").strip()
        if url and not re.match(r"^(https?://|mailto:)", url, re.I):
            issues.append(f"Add https:// to the link: {item.get('label') or url}")
    if profile.photo_path:
        from pathlib import Path
        if not Path(profile.photo_path).is_file():
            issues.append("The selected profile photo could not be found. You can remove it or choose another.")
        else:
            try:
                from PIL import Image
                with Image.open(profile.photo_path) as image:
                    image.verify()
            except Exception:
                issues.append("The selected profile photo is not a supported, readable image.")
    from pathlib import Path
    for item in profile.certificates:
        attachment = (item.get("attachment") or "").strip()
        if attachment and not Path(attachment).is_file():
            issues.append(f"Certificate attachment is missing: {Path(attachment).name}")
    return issues
