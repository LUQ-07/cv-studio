"""Shared design helpers: palette, fonts, photo handling and content model.

Every renderer (PDF, DOCX, HTML preview) consumes `build_content()` so the
three outputs always show the same sections in the same order.
"""
from __future__ import annotations

import io
import sys
from dataclasses import dataclass
from pathlib import Path

from .templates import Template, get_template

# --------------------------------------------------------------------------- colour

def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 0, 0, 0


def _hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in rgb)


def mix(a: str, b: str, t: float) -> str:
    """Blend colour a towards colour b by t (0..1)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex([ra[i] + (rb[i] - ra[i]) * t for i in range(3)])


def luminance(hex_color: str) -> float:
    r, g, b = [v / 255 for v in _rgb(hex_color)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@dataclass(frozen=True)
class Palette:
    accent: str       # headings, rules, markers
    panel: str        # dark sidebar / banner background
    tint: str         # very light accent wash (light sidebars)
    ink: str = "#1F2937"
    muted: str = "#6B7280"
    soft: str = "#D9DEE7"
    on_panel: str = "#FFFFFF"
    on_panel_muted: str = "#C9D2E3"
    accent_on_panel: str = "#FFFFFF"   # headings drawn on the dark panel
    accent_text: str = "#1F2937"       # accent that is readable on white


def palette_for(profile, template: Template | None = None) -> Palette:
    t = template or get_template(profile.template_id)
    chosen = (profile.accent_color or t.color).strip() or t.color
    if chosen.upper() == t.color.upper():
        accent, panel = t.color, t.panel
    else:  # user picked a custom colour: derive a harmonious dark panel from it
        accent, panel = chosen, mix(chosen, "#0B1020", 0.68)
    # An accent used for text on white must keep enough contrast.
    accent_text = accent if luminance(accent) < 0.55 else mix(accent, "#000000", 0.38)
    on_panel_accent = accent if luminance(accent) > 0.35 else mix(accent, "#FFFFFF", 0.55)
    return Palette(
        accent=accent, panel=panel, tint=mix(accent, "#FFFFFF", 0.90),
        accent_on_panel=on_panel_accent, accent_text=accent_text,
        on_panel_muted=mix(panel, "#FFFFFF", 0.72),
    )

# --------------------------------------------------------------------------- fonts

FONT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "cvstudio" / "assets" / "fonts"
# kind -> (reportlab family name, files regular/bold/italic/bolditalic, Word font name, fallback family)
FONT_FILES = {
    "sans": ("CVCarlito", ("Carlito-Regular.ttf", "Carlito-Bold.ttf", "Carlito-Italic.ttf", "Carlito-BoldItalic.ttf"), "Calibri", "Helvetica"),
    "serif": ("CVCaladea", ("Caladea-Regular.ttf", "Caladea-Bold.ttf", "Caladea-Italic.ttf", "Caladea-BoldItalic.ttf"), "Cambria", "Times-Roman"),
    "mono": ("CVMono", ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf", "DejaVuSansMono-Oblique.ttf", "DejaVuSansMono-BoldOblique.ttf"), "Consolas", "Courier"),
}
_registered: dict[str, str] = {}


def pdf_font(kind: str) -> str:
    """Register (once) and return the ReportLab family name; <b>/<i> markup works."""
    if kind in _registered:
        return _registered[kind]
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    family, files, _word, fallback = FONT_FILES.get(kind, FONT_FILES["sans"])
    try:
        names = []
        for suffix, fname in zip(("", "-Bold", "-Italic", "-BoldItalic"), files):
            name = family + suffix
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / fname)))
            names.append(name)
        pdfmetrics.registerFontFamily(family, normal=names[0], bold=names[1], italic=names[2], boldItalic=names[3])
        _registered[kind] = family
    except Exception:  # missing font files: fall back to built-in PDF fonts
        _registered[kind] = fallback
    return _registered[kind]


def pdf_bold(family: str) -> str:
    return {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}.get(family, family + "-Bold")


def word_font(kind: str) -> str:
    return FONT_FILES.get(kind, FONT_FILES["sans"])[2]

# --------------------------------------------------------------------------- photo

def circle_photo_png(path: str, px: int = 360) -> io.BytesIO | None:
    """Centre-crop to a square, apply a circular alpha mask, return PNG bytes."""
    if not path:
        return None
    try:
        from PIL import Image, ImageDraw, ImageOps
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
        side = min(img.size)
        left, top = (img.width - side) // 2, (img.height - side) // 2
        img = img.crop((left, top, left + side, top + side)).resize((px, px), Image.LANCZOS)
        mask = Image.new("L", (px * 4, px * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, px * 4 - 1, px * 4 - 1), fill=255)
        img.putalpha(mask.resize((px, px), Image.LANCZOS))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


def on_color(bg: str) -> str:
    """Readable text colour (white or near-black) for a given background."""
    return "#FFFFFF" if luminance(bg) < 0.55 else "#111827"


def initials(name: str) -> str:
    words = [w for w in (name or "").replace("-", " ").split() if w[:1].isalpha()]
    letters = "".join(w[0] for w in words[:2]).upper()
    return letters or "CV"


def monogram_png(name: str, bg: str, fg: str, px: int = 360) -> io.BytesIO | None:
    """Circle with the person's initials; used instead of an empty space when no photo is set."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        S = px * 3
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((0, 0, S - 1, S - 1), fill=_rgb(bg) + (255,))
        text = initials(name)
        font = ImageFont.truetype(str(FONT_DIR / "Carlito-Bold.ttf"), int(S * (0.42 if len(text) == 1 else 0.38)))
        l, t, r, b = d.textbbox((0, 0), text, font=font)
        d.text(((S - (r - l)) / 2 - l, (S - (b - t)) / 2 - t), text, font=font, fill=_rgb(fg) + (255,))
        buf = io.BytesIO()
        img.resize((px, px), Image.LANCZOS).save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None


def profile_photo(profile) -> io.BytesIO | None:
    if profile.show_photo and profile.photo_path and Path(profile.photo_path).is_file():
        return circle_photo_png(profile.photo_path)
    return None

# --------------------------------------------------------------------------- content

LEVELS = {"beginner": .3, "basic": .3, "elementary": .3, "a1": .2, "a2": .3, "intermediate": .6, "b1": .5, "b2": .65,
          "good": .7, "advanced": .85, "c1": .85, "proficient": .85, "professional": .85, "fluent": .9, "expert": 1.0,
          "native": 1.0, "mother tongue": 1.0, "c2": 1.0, "bilingual": 1.0, "excellent": .95}


def level_fraction(level: str) -> float | None:
    key = (level or "").strip().lower()
    if key in LEVELS:
        return LEVELS[key]
    for word, frac in LEVELS.items():
        if word in key and len(word) > 3:
            return frac
    return None


@dataclass
class Entry:
    title: str = ""
    sub: str = ""
    dates: str = ""
    lines: tuple = ()
    url: str = ""
    level: str = ""


def _clean(value) -> str:
    return str(value or "").strip()


def _entry(item, key: str = "") -> Entry:
    if isinstance(item, str):
        return Entry(title=_clean(item))
    g = lambda *keys: next((_clean(item.get(k)) for k in keys if _clean(item.get(k))), "")
    desc = _clean(item.get("description"))
    lines = tuple(l.strip() for l in desc.splitlines() if l.strip())
    if key == "projects":      # title, then "Role · Technologies" underneath
        tech = g("technologies")
        sub = " · ".join(x for x in [g("role"), (f"Tech: {tech}" if tech else "")] if x)
        return Entry(title=g("title", "name"), sub=sub, dates=g("dates", "date"), lines=lines, url=g("url"))
    if key in {"publications", "courses", "memberships", "awards", "certificates"}:
        sub = " · ".join(x for x in [g("issuer", "organization", "publisher", "company"), g("role"), g("location")] if x)
        return Entry(title=g("title", "name"), sub=sub, dates=g("dates", "date"), lines=lines, url=g("url"), level=g("level"))
    if key == "references":
        sub = " · ".join(x for x in [g("company", "position"), g("contact")] if x)
        return Entry(title=g("name", "title"), sub=sub, lines=lines)
    sub = " · ".join(x for x in [g("company", "school", "issuer", "organization"), g("location")] if x)
    return Entry(title=g("role", "degree", "name", "title", "label"), sub=sub, dates=g("dates", "date"),
                 lines=lines, url=g("url"), level=g("level"))


def _entries(items, key: str = "") -> list[Entry]:
    out = [_entry(i, key) for i in (items or [])]
    return [e for e in out if e.title or e.sub or e.lines]


def is_safe_url(url: str) -> bool:
    return (url or "").startswith(("https://", "http://", "mailto:"))


@dataclass
class Section:
    key: str
    title: str
    entries: list
    kind: str = "entries"      # entries | skills | text


@dataclass
class Content:
    name: str
    headline: str
    contact: list             # [(label, text, url)]
    summary: str
    main: list                # sections for the wide column
    side: list                # sections for the narrow column (two-column layouts)
    flat: list                # every section in order (single-column layouts)


ORDERS = {        # keyed by the template's `order=` style option
    "entry": ["education", "projects", "experience", "volunteer", "awards"],
    "academic": ["education", "experience", "projects", "awards", "volunteer"],
    "technical": ["experience", "projects", "education", "awards", "volunteer"],
}


def build_content(profile, template: Template | None = None) -> Content:
    t = template or get_template(profile.template_id)
    contact = []
    for label, val in (("Email", profile.email), ("Phone", profile.phone), ("Location", profile.location), ("Address", profile.address)):
        if _clean(val):
            contact.append((label, _clean(val), f"mailto:{_clean(val)}" if label == "Email" else ""))
    links = []
    for link in profile.links or []:
        url = _clean(link.get("url"))
        if url:
            links.append(("Link", _clean(link.get("label")) or url.replace("https://", "").replace("http://", "").rstrip("/"), url if is_safe_url(url) else ""))
    contact += links

    def sec(key, title, items, kind="entries"):
        entries = _entries(items, key)
        return Section(key, title, entries, kind) if entries else None

    experience = sec("experience", "Experience", profile.experience)
    education = sec("education", "Education", profile.education)
    projects = sec("projects", "Projects", profile.projects)
    awards = sec("awards", "Awards", profile.awards)
    volunteer = sec("volunteer", "Volunteer work", profile.volunteer)
    internships = sec("internships", "Internships", getattr(profile, "internships", []))
    courses = sec("courses", "Courses", getattr(profile, "courses", []))
    publications = sec("publications", "Publications", getattr(profile, "publications", []))
    memberships = sec("memberships", "Memberships", getattr(profile, "memberships", []))
    references = sec("references", "References", getattr(profile, "references", []))
    hobbies = sec("hobbies", "Interests", getattr(profile, "hobbies", []), "skills")
    skills = sec("skills", "Skills", [s for s in (profile.skills or []) if _clean(s.get("name") if isinstance(s, dict) else s)], "skills")
    languages = sec("languages", "Languages", profile.languages, "skills")
    certificates = sec("certificates", "Certificates", profile.certificates)
    custom = [Section("custom%d" % i, _clean(c.get("title")) or "Additional information",
                      [Entry(lines=tuple(l.strip() for l in _clean(c.get("content")).splitlines() if l.strip()))], "text")
              for i, c in enumerate(profile.custom_sections or []) if _clean(c.get("content"))]
    summary = "" if "summary" in set(getattr(profile, "hidden_sections", []) or []) else _clean(profile.summary)

    hidden = set(getattr(profile, "hidden_sections", []) or [])
    wide = {s.key: s for s in (experience, internships, education, courses, projects, publications, awards, volunteer, memberships, references) if s and s.key not in hidden}
    default = ORDERS.get(t.opts["order"], ["experience", "education", "projects", "awards", "volunteer"])
    default = default + [k for k in ("internships", "courses", "publications", "memberships", "references") if k not in default]
    user = [k for k in (getattr(profile, "section_order", []) or []) if k in wide]
    order = user + [k for k in default if k not in user]
    custom = [c for c in custom if c.key not in hidden]
    main = [wide[k] for k in order if k in wide] + custom
    side = [s for s in (skills, languages, certificates, hobbies) if s and s.key not in hidden]
    flat_extra = list(side)
    # single-column order: skills early for Technical/Entry-level, otherwise after education
    flat = list(main)
    if flat_extra:
        idx = 0 if t.opts["order"] in {"technical", "entry"} and skills else next((i for i, s in enumerate(flat) if s.key == "education"), len(flat) - len(custom)) + 1
        idx = max(0, min(idx, len(flat)))
        flat[idx:idx] = flat_extra
    return Content(name=_clean(profile.full_name) or "Your Name", headline=_clean(profile.headline), contact=contact,
                   summary=summary, main=main, side=side, flat=flat)
