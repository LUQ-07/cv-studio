"""Thirty CV designs built on eight genuinely different page structures.

Each template is only data: the PDF, DOCX and preview renderers all read the
same fields, so an exported file always matches what the gallery promised.

layout values
  sidebar        dark coloured column on the left (photo, contact, skills)
  sidebar_light  soft tinted column on the left
  sidebar_right  dark coloured column on the right
  banner         full-width colour header, two columns underneath
  classic        centred header, single column, ruled headings
  minimal        left-aligned light header, airy single column
  bold           heavy accent header strip, marker headings
  compact        dense single column for long careers
"""
from dataclasses import dataclass

SIDEBAR_LAYOUTS = {"sidebar", "sidebar_light", "sidebar_right"}
TWO_COLUMN_LAYOUTS = SIDEBAR_LAYOUTS | {"banner"}
ATS_LAYOUTS = {"classic", "minimal", "bold", "compact"}


# Bump when the look of the templates changes: the gallery's cached thumbnails are keyed by it.
DESIGN_REV = 2

# The five (and only five) gallery categories.
CATEGORIES = ("Modern", "Minimal", "Professional", "Creative", "Others")

# Style options understood by the renderers (all optional, "key=value;key=value"):
#   head   section headings : rule | plain | bar | short | band | dot | center
#   skills side column      : bars | dots | plain      single column: inline | cols
#   name   name treatment   : normal | caps | light
#   density spacing         : airy | cozy | tight
#   date   entry dates      : right | below
#   order  section order    : entry | academic | technical  (default: experience first)
DEFAULT_OPTS = {"head": "rule", "skills": "", "name": "normal", "density": "cozy", "date": "right", "order": ""}


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    category: str
    layout: str
    color: str        # accent colour
    panel: str        # dark panel / band colour (sidebar, banner, header strip)
    font: str         # sans (Calibri-style) | serif (Cambria-style) | mono
    description: str
    free: bool = False   # 5 templates are free, the other 25 are Premium (Store add-on)
    style: str = ""

    @property
    def opts(self) -> dict:
        out = dict(DEFAULT_OPTS)
        for part in self.style.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k.strip()] = v.strip()
        if not out["skills"]:
            out["skills"] = "bars" if self.layout in TWO_COLUMN_LAYOUTS else "inline"
        return out

    @property
    def ats_friendly(self) -> bool:
        """Single-column layouts with a conventional reading order."""
        return self.layout in ATS_LAYOUTS

    @property
    def premium(self) -> bool:
        return not self.free

    @property
    def two_column(self) -> bool:
        return self.layout in TWO_COLUMN_LAYOUTS


_rows = [
    # id, name, category, layout, accent, panel, font, description, style
    ("modern_summit", "Summit", "Modern", "sidebar", "#6C8CFF", "#1E2A44", "sans", "Deep navy sidebar with photo or monogram, skill bars and a crisp main column.", "head=rule;skills=bars;name=normal;density=cozy;date=right"),
    ("modern_atlas", "Atlas", "Modern", "sidebar_light", "#0E8F9A", "#12303B", "sans", "Soft teal sidebar, airy spacing, dotted skill levels; friendly and professional.", "head=short;skills=dots;name=normal;density=airy;date=right"),
    ("modern_horizon", "Horizon", "Modern", "banner", "#E4572E", "#243447", "sans", "Wide colour banner introduces you, shaded section bands and two clean columns follow.", "head=band;skills=bars;name=caps;density=cozy;date=right"),
    ("modern_pulse", "Pulse", "Modern", "bold", "#C2185B", "#2B2D42", "sans", "Heavy accent strip and marker headings. Confident, still ATS-safe.", "head=bar;skills=inline;name=caps;density=cozy;date=right"),
    ("minimal_still", "Still", "Minimal", "minimal", "#3F4A5A", "#1F2937", "serif", "Typography-first, generous whitespace, quiet serif details.", "head=plain;skills=inline;name=light;density=airy;date=right"),
    ("minimal_paper", "Paper", "Minimal", "classic", "#4B5563", "#1F2937", "serif", "Classic centred header and centred headings on a calm, printable page.", "head=center;skills=inline;name=normal;density=airy;date=right"),
    ("minimal_line", "Line", "Minimal", "minimal", "#2F6F8F", "#1B2B3A", "sans", "Light sans header with fine rules, a blue accent and a tidy skill grid.", "head=rule;skills=cols;name=light;density=cozy;date=right"),
    ("minimal_clear", "Clear", "Minimal", "compact", "#3B82A0", "#1B2B3A", "sans", "Dense but readable, built for quick scanning.", "head=short;skills=inline;name=normal;density=tight;date=right"),
    ("corporate_meridian", "Meridian", "Professional", "banner", "#2F6DB5", "#0F2D4D", "sans", "Navy banner and structured columns for leadership profiles.", "head=rule;skills=bars;name=normal;density=cozy;date=right"),
    ("corporate_keystone", "Keystone", "Professional", "classic", "#1F4E79", "#12263F", "serif", "Traditional hierarchy for established sectors (banking, law, public).", "head=rule;skills=inline;name=caps;density=cozy;date=right"),
    ("corporate_north", "North", "Modern", "sidebar", "#4FB0C6", "#163447", "sans", "Slate-blue sidebar with a discreet cyan accent and compact dates under each title.", "head=dot;skills=plain;name=normal;density=tight;date=below"),
    ("corporate_civic", "Civic", "Professional", "compact", "#34546B", "#1E2F3B", "sans", "Information-dense, aligned and easy to print.", "head=bar;skills=cols;name=normal;density=tight;date=right"),
    ("creative_canvas", "Canvas", "Creative", "bold", "#8E44AD", "#2E1A47", "serif", "Expressive purple strip with shaded headings and elegant serif body text.", "head=band;skills=inline;name=caps;density=cozy;date=right"),
    ("creative_form", "Forma", "Creative", "sidebar_light", "#7E57C2", "#2A1F4D", "sans", "Lavender sidebar for designers and portfolio-led profiles.", "head=dot;skills=bars;name=light;density=airy;date=right"),
    ("creative_mosaic", "Mosaic", "Creative", "sidebar", "#F2994A", "#3B2A22", "sans", "Warm espresso sidebar with an orange accent.", "head=short;skills=dots;name=caps;density=cozy;date=right"),
    ("creative_studio", "Studio", "Creative", "sidebar_right", "#2E8B6F", "#18382F", "serif", "Sidebar on the right puts your story first.", "head=plain;skills=bars;name=normal;density=airy;date=right"),
    ("technical_signal", "Signal", "Others", "compact", "#0B7A9E", "#0F2A3A", "mono", "Monospace precision, compact sections for engineers.", "head=bar;skills=inline;name=normal;density=tight;date=right;order=technical"),
    ("technical_stack", "Stack", "Others", "sidebar", "#3DDC97", "#10241C", "sans", "Dark green sidebar listing the stack at a glance.", "head=dot;skills=bars;name=normal;density=cozy;date=right;order=technical"),
    ("technical_grid", "Grid", "Others", "sidebar_light", "#2F5D9F", "#16263D", "sans", "Modular, grid-like hierarchy with a light technical sidebar.", "head=rule;skills=dots;name=normal;density=cozy;date=right;order=technical"),
    ("technical_terminal", "Terminal", "Others", "banner", "#22C55E", "#0B1220", "mono", "Near-black banner with green accents and monospace headline.", "head=band;skills=plain;name=caps;density=cozy;date=right;order=technical"),
    ("academic_scholar", "Scholar", "Professional", "classic", "#5B3F8C", "#2A1B45", "serif", "Formal serif typography, publication-friendly order.", "head=rule;skills=inline;name=normal;density=cozy;date=below;order=academic"),
    ("academic_field", "Field", "Minimal", "minimal", "#4F6F52", "#1F2E22", "serif", "A calm research profile; education leads.", "head=dot;skills=inline;name=normal;density=cozy;date=below;order=academic"),
    ("academic_lecture", "Lecture", "Professional", "classic", "#2C5F7C", "#142F3F", "serif", "Compact credentials, shaded section bands and clear structure.", "head=band;skills=cols;name=light;density=tight;date=right;order=academic"),
    ("academic_archive", "Archive", "Others", "sidebar_right", "#8A6B3F", "#33291B", "serif", "Scholarly layout with a warm bronze sidebar.", "head=rule;skills=plain;name=light;density=airy;date=right;order=academic"),
    ("entry_spark", "Spark", "Creative", "bold", "#F07F2D", "#26334D", "sans", "Skills and projects lead when experience is limited.", "head=short;skills=cols;name=normal;density=cozy;date=right;order=entry"),
    ("entry_launch", "Launch", "Modern", "sidebar_light", "#2A9D8F", "#183A37", "sans", "Fresh and friendly for graduates and career starters.", "head=bar;skills=dots;name=normal;density=airy;date=right;order=entry"),
    ("entry_path", "Path", "Others", "banner", "#4C6EF5", "#1C2A5A", "sans", "Education and projects get a strong visual hierarchy.", "head=dot;skills=dots;name=normal;density=cozy;date=right;order=entry"),
    ("entry_firstlight", "Firstlight", "Minimal", "minimal", "#C2563A", "#3A2A25", "serif", "Uncluttered, warm format for first applications.", "head=short;skills=cols;name=light;density=airy;date=right;order=entry"),
    ("senior_pinnacle", "Pinnacle", "Professional", "banner", "#B08D57", "#1F1A2E", "serif", "Executive banner with a gold accent and spacious summary.", "head=short;skills=dots;name=caps;density=airy;date=right"),
    ("senior_legacy", "Legacy", "Professional", "classic", "#8A5D23", "#2B1D0C", "serif", "A distinguished format for long career histories.", "head=dot;skills=inline;name=normal;density=airy;date=below"),
]

# Five free templates, one per single-/two-column style family so free users get real choice.
FREE_IDS = {"modern_summit", "minimal_paper", "minimal_clear", "modern_pulse", "minimal_still"}
TEMPLATES = [Template(*r[:8], free=r[0] in FREE_IDS, style=r[8]) for r in _rows]
TEMPLATE_BY_ID = {t.id: t for t in TEMPLATES}
assert len(TEMPLATES) == 30
assert len(TEMPLATE_BY_ID) == 30
assert sum(t.free for t in TEMPLATES) == 5 and sum(not t.free for t in TEMPLATES) == 25


def get_template(template_id: str) -> Template:
    return TEMPLATE_BY_ID.get(template_id, TEMPLATES[0])
