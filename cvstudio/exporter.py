"""PDF generation (ReportLab). Eight real page structures, embedded Unicode fonts.

Layouts are driven by `templates.Template.layout`; see templates.py.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas  # noqa: F401  (ensures canvas import errors surface early)
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, FrameBreak, HRFlowable, Image, KeepInFrame,
                                KeepTogether, NextPageTemplate, PageTemplate, Paragraph, Spacer, Table, TableStyle)

from .design import (build_content, is_safe_url, level_fraction, luminance, monogram_png, on_color, palette_for, pdf_bold, pdf_font, profile_photo)
from .templates import SIDEBAR_LAYOUTS, get_template

HC = colors.HexColor


def _e(value) -> str:
    return escape(str(value or ""))


def _link(text: str, url: str, color: str) -> str:
    if is_safe_url(url):
        return f'<link href="{escape(url, {chr(34): "&quot;"})}" color="{color}">{_e(text)}</link>'
    return _e(text)


class Bar(Flowable):
    """Thin rounded skill-level bar."""

    def __init__(self, width, frac, fg, bg, h=2.4 * mm):
        super().__init__()
        self.width, self.frac, self.fg, self.bg, self.h = width, frac, fg, bg, h

    def wrap(self, aw, ah):
        return self.width, self.h + 1.2 * mm

    def draw(self):
        c = self.canv
        r = self.h / 2
        c.setFillColor(HC(self.bg))
        c.roundRect(0, 0.6 * mm, self.width, self.h, r, stroke=0, fill=1)
        c.setFillColor(HC(self.fg))
        c.roundRect(0, 0.6 * mm, max(self.h, self.width * self.frac), self.h, r, stroke=0, fill=1)


class Dots(Flowable):
    """Five small dots, `frac` of them filled (skill level)."""

    def __init__(self, frac, fg, bg, d=2.0 * mm, gap=1.3 * mm):
        super().__init__()
        self.frac, self.fg, self.bg, self.d, self.gap = frac, fg, bg, d, gap

    def wrap(self, aw, ah):
        return 5 * self.d + 4 * self.gap, self.d + 1.4 * mm

    def draw(self):
        c, filled = self.canv, max(1, round(self.frac * 5))
        for i in range(5):
            c.setFillColor(HC(self.fg if i < filled else self.bg))
            c.circle(self.d / 2 + i * (self.d + self.gap), 0.7 * mm + self.d / 2, self.d / 2, stroke=0, fill=1)


class Dot(Flowable):
    """Small accent dot used in front of section headings."""

    def __init__(self, color, d=2.4 * mm):
        super().__init__()
        self.color, self.d = color, d

    def wrap(self, aw, ah):
        return self.d, self.d

    def draw(self):
        self.canv.setFillColor(HC(self.color))
        self.canv.circle(self.d / 2, self.d / 2, self.d / 2, stroke=0, fill=1)


class Styles:
    """All paragraph styles for one document."""

    def __init__(self, profile, tpl, pal):
        base = max(8.5, min(13, float(profile.font_size or 10)))
        self.base = base
        self.opts = tpl.opts
        self.lead, self.k = {"airy": (1.46, 1.18), "tight": (1.30, 0.84)}.get(self.opts["density"], (1.38, 1.0))   # line height, spacing factor
        self.face = pdf_font(tpl.font)
        self.bold = pdf_bold(self.face)
        f, b = self.face, self.bold
        mk = lambda name, **kw: ParagraphStyle(name, fontName=kw.pop("fontName", f), **kw)
        self.body = mk("body", fontSize=base, leading=base * self.lead, textColor=HC(pal.ink))
        self.small = mk("small", fontSize=base - 1, leading=(base - 1) * 1.35, textColor=HC(pal.muted))
        self.sub = mk("sub", fontSize=base, leading=base * 1.3, textColor=HC(pal.muted), fontName=f)
        self.title = mk("title", fontSize=base + 0.5, leading=(base + 0.5) * 1.3, textColor=HC(pal.ink), fontName=b)
        self.dates = mk("dates", fontSize=base - 0.5, leading=base * 1.3, textColor=HC(pal.accent_text), alignment=TA_RIGHT, fontName=b)
        self.bullet = mk("bullet", fontSize=base, leading=base * self.lead, textColor=HC(pal.ink), leftIndent=4.2 * mm, bulletIndent=0.6 * mm, spaceAfter=0.6 * mm * self.k)
        self.cell = mk("cell", fontSize=base - 0.5, leading=(base - 0.5) * 1.3, textColor=HC(pal.ink), leftIndent=3.6 * mm, bulletIndent=0.2 * mm, spaceAfter=0.8 * mm)
        self.side_body = mk("sbody", fontSize=base - 0.5, leading=(base - 0.5) * 1.4, textColor=HC(pal.on_panel))
        self.side_muted = mk("smuted", fontSize=base - 1.5, leading=(base - 1.5) * 1.3, textColor=HC(pal.on_panel_muted))
        self.light_body = mk("lbody", fontSize=base - 0.5, leading=(base - 0.5) * 1.4, textColor=HC(pal.ink))
        self.light_muted = mk("lmuted", fontSize=base - 1.5, leading=(base - 1.5) * 1.3, textColor=HC(pal.muted))


def _desc(lines, st, bullet_style=None):
    """Lines starting with -, • or * become bullets; other lines are paragraphs."""
    out = []
    for line in lines:
        if line[:1] in "-•*–·" and len(line) > 1:
            out.append(Paragraph(_e(line[1:].strip()), bullet_style or st.bullet, bulletText="•"))
        else:
            out.append(Paragraph(_e(line), st.body))
    return out


def _entry_block(e, st, width, pal):
    title = _link(e.title, e.url, pal.accent_text) if e.url else _e(e.title)
    rows = []
    if e.dates and st.opts["date"] == "below":          # dates sit on the line under the title: calmer, no right-hand column
        rows.append(Paragraph(title, st.title))
        rows.append(Paragraph(f'<font color="{pal.accent_text}"><b>{_e(e.dates)}</b></font>' + (f" &nbsp;·&nbsp; {_e(e.sub)}" if e.sub else ""), st.sub))
    elif e.dates:
        t = Table([[Paragraph(title, st.title), Paragraph(_e(e.dates), st.dates)]], colWidths=[width - 34 * mm, 34 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        rows.append(t)
    elif e.title:
        rows.append(Paragraph(title, st.title))
    if e.sub and not (e.dates and st.opts["date"] == "below"):
        rows.append(Paragraph(_e(e.sub), st.sub))
    body = _desc(e.lines, st)
    head = rows + body[:1]
    return [KeepTogether(head)] + body[1:] + [Spacer(1, 2.6 * mm * st.k)]


def _heading(title, kind, st, pal, width, caps=True):
    text = title.upper() if caps else title
    k = st.k
    hs = ParagraphStyle("h", fontName=st.bold, fontSize=st.base + (1.2 if kind != "plain" else 0), leading=st.base + 5,
                        textColor=HC(pal.accent_text if kind != "plain" else pal.ink), spaceBefore=0, spaceAfter=0,
                        keepWithNext=True, wordSpace=0, charSpace=1.1 if caps else 0, alignment=TA_CENTER if kind == "center" else TA_LEFT)
    zero = [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]
    if kind == "bar":
        t = Table([["", Paragraph(_e(text), hs)]], colWidths=[1.6 * mm, width - 1.6 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), HC(pal.accent)), ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                               ("LEFTPADDING", (1, 0), (1, 0), 2.6 * mm), ("TOPPADDING", (0, 0), (-1, -1), 0.6 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6 * mm)]))
        return [Spacer(1, 3.8 * mm * k), t, Spacer(1, 2.4 * mm * k)]
    if kind == "band":                                   # soft tinted band with an accent edge
        t = Table([[Paragraph(_e(text), hs)]], colWidths=[width])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HC(pal.tint)), ("LINEBEFORE", (0, 0), (0, 0), 2.4, HC(pal.accent)),
                               ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                               ("TOPPADDING", (0, 0), (-1, -1), 1.3 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.3 * mm)]))
        return [Spacer(1, 3.8 * mm * k), t, Spacer(1, 2.6 * mm * k)]
    if kind == "dot":
        t = Table([[Dot(pal.accent), Paragraph(_e(text), hs)]], colWidths=[5 * mm, width - 5 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return [Spacer(1, 3.8 * mm * k), t, HRFlowable(width="100%", thickness=0.5, color=HC(pal.soft), spaceBefore=1.2 * mm, spaceAfter=2.4 * mm * k)]
    if kind == "short":
        return [Spacer(1, 3.8 * mm * k), Paragraph(_e(text), hs),
                HRFlowable(width=14 * mm, thickness=1.8, color=HC(pal.accent), spaceBefore=1 * mm, spaceAfter=2.6 * mm * k, hAlign="LEFT")]
    if kind == "center":
        return [Spacer(1, 3.8 * mm * k), Paragraph(_e(text), hs),
                HRFlowable(width=16 * mm, thickness=1.0, color=HC(pal.accent), spaceBefore=1 * mm, spaceAfter=2.6 * mm * k, hAlign="CENTER")]
    rule = HRFlowable(width="100%", thickness=0.9 if kind == "rule" else 0.5, color=HC(pal.accent if kind == "rule" else pal.soft), spaceBefore=1 * mm, spaceAfter=2.4 * mm * k)
    return [Spacer(1, 3.5 * mm * k), Paragraph(_e(text), hs), rule]


def _name_para(text, st, color, size, align=TA_LEFT):
    """Name in the template's name style: normal bold, CAPS with tracking, or large light weight."""
    mode = st.opts["name"]
    if mode == "caps":
        text, size, font, cs = text.upper(), size * 0.82, st.bold, 1.6
    elif mode == "light":
        font, size, cs = st.face, size * 1.08, 0.5
    else:
        font, cs = st.bold, 0
    return Paragraph(_e(text), ParagraphStyle("name", fontName=font, fontSize=size, leading=size + 4, textColor=HC(color), alignment=align, charSpace=cs))


def _skill_flow(section, st, pal, width, on_dark):
    out = []
    body = st.side_body if on_dark else st.light_body
    muted = st.side_muted if on_dark else st.light_muted
    fg = pal.accent_on_panel if on_dark else pal.accent
    bg = pal.on_panel_muted if on_dark else pal.soft
    mode = st.opts["skills"] if st.opts["skills"] in {"bars", "dots", "plain"} else "bars"
    for e in section.entries:
        if section.key == "certificates":
            out.append(Paragraph(f"<b>{_e(e.title)}</b>", body))
            sub = " · ".join(x for x in (e.sub, e.dates) if x)
            if sub:
                out.append(Paragraph(_e(sub), muted))
            out.append(Spacer(1, 1.6 * mm))
            continue
        frac = level_fraction(e.level)
        if mode == "plain" or frac is None:                # plain: "Name · Level" on one line
            lvl = f' <font size="{st.base - 2}" color="{pal.on_panel_muted if on_dark else pal.muted}">· {_e(e.level)}</font>' if e.level else ""
            out.append(Paragraph(_e(e.title) + lvl, body)); out.append(Spacer(1, 1.2 * mm if mode != "plain" else 0.8 * mm))
            continue
        out.append(Paragraph(_e(e.title), body))
        out.append(Bar(width, frac, fg, bg) if mode == "bars" else Dots(frac, fg, bg))
    return out


def _flat_skills(section, st, width):
    names = [(e.title + (f" ({e.level})" if e.level else "")) for e in section.entries]
    if st.opts["skills"] == "cols" and len(names) > 3:      # tidy three-column grid
        rows = [names[i:i + 3] for i in range(0, len(names), 3)]
        data = [[Paragraph(_e(n), st.cell, bulletText="•") if n else "" for n in (r + [""] * (3 - len(r)))] for r in rows]
        t = Table(data, colWidths=[width / 3] * 3)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return [t]
    return [Paragraph(" &nbsp;·&nbsp; ".join(_e(n) for n in names), st.body)]


def _section_flow(section, st, pal, width, head_kind, side=None):
    flow = _heading(section.title, head_kind, st, pal, width, caps=head_kind != "plain" or True)
    if section.kind == "skills":
        return flow + _flat_skills(section, st, width)
    if section.kind == "text":
        return flow + _desc(section.entries[0].lines, st)
    if section.key == "certificates":
        for e in section.entries:
            flow += _entry_block(e, st, width, pal)
        return flow
    for e in section.entries:
        flow += _entry_block(e, st, width, pal)
    return flow


def _contact_para(content, st, color, link_color, sep=" &nbsp;·&nbsp; ", style=None):
    parts = []
    for _label, text, url in content.contact:
        parts.append(_link(text, url, link_color) if url else _e(text))
    return Paragraph(sep.join(parts), style) if parts else None


def export_pdf(profile, output_path: str | Path) -> Path:
    """Write the CV as a PDF and return its path. Raises OSError/ValueError on failure."""
    tpl = get_template(profile.template_id)
    pal = palette_for(profile, tpl)
    content = build_content(profile, tpl)
    path = Path(output_path).expanduser()
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    page = A4 if profile.page_size == "A4" else LETTER
    pw, ph = page
    st = Styles(profile, tpl, pal)
    photo = profile_photo(profile)
    layout = tpl.layout
    story, templates = [], []
    mg = 16 * mm

    def panel_rect(c, x, w, color):
        c.setFillColor(HC(color))
        c.rect(x, 0, w, ph, stroke=0, fill=1)

    def photo_img(size, mono_bg=None):
        """The user's photo; if there is none (and photos are on), a monogram circle instead of an empty gap."""
        if photo:
            photo.seek(0)
            return Image(photo, width=size, height=size)
        if mono_bg and profile.show_photo:
            buf = monogram_png(content.name, mono_bg, on_color(mono_bg))
            if buf:
                return Image(buf, width=size, height=size)
        return None

    # ------------------------------------------------------------------ sidebar layouts
    if layout in SIDEBAR_LAYOUTS:
        sw = 70 * mm
        dark = layout != "sidebar_light"
        right = layout == "sidebar_right"
        pad = 8 * mm
        sx = pw - sw if right else 0
        mx = mg if right else sw + 11 * mm
        mw = pw - sw - 11 * mm - mg
        top, bot = 15 * mm, 13 * mm
        fill = pal.panel if dark else pal.tint

        def bg(c, doc):
            c.saveState()
            panel_rect(c, sx, sw, fill)
            if not dark:
                c.setFillColor(HC(pal.accent))
                c.rect(sx + (0 if right else sw - 1.2 * mm), 0, 1.2 * mm, ph, stroke=0, fill=1)
            c.restoreState()

        first = PageTemplate("first", [Frame(sx + pad, bot, sw - 2 * pad, ph - top - bot, 0, 0, 0, 0, id="side"),
                                       Frame(mx, bot, mw, ph - top - bot, 0, 0, 0, 0, id="main")], onPage=bg)
        later = PageTemplate("later", [Frame(mx, bot, mw, ph - top - bot, 0, 0, 0, 0, id="main2")], onPage=bg)
        templates = [first, later]
        sw_in = sw - 2 * pad
        side = []
        pimg = photo_img(34 * mm, pal.accent_on_panel if dark else pal.accent)
        if pimg:
            pimg.hAlign = "CENTER"
            side += [pimg, Spacer(1, 6 * mm)]
        body = st.side_body if dark else st.light_body
        muted = st.side_muted if dark else st.light_muted
        hs = ParagraphStyle("sh", fontName=st.bold, fontSize=st.base, leading=st.base + 4, charSpace=1.4,
                            textColor=HC(pal.accent_on_panel if dark else pal.accent_text), keepWithNext=True)
        link_col = pal.on_panel if dark else pal.accent_text

        def side_head(title):
            return [Spacer(1, 5 * mm), Paragraph(_e(title.upper()), hs),
                    HRFlowable(width="100%", thickness=0.6, color=HC(pal.on_panel_muted if dark else pal.soft), spaceBefore=1 * mm, spaceAfter=2.5 * mm)]

        if content.contact:
            side += side_head("Contact")
            for label, text, url in content.contact:
                side.append(Paragraph(f'<font size="{st.base - 2.5}" color="{pal.on_panel_muted if dark else pal.muted}">{label.upper()}</font><br/>' +
                                      (_link(text, url, link_col) if url else _e(text)), body))
                side.append(Spacer(1, 2 * mm))
        for s in content.side:
            side += side_head(s.title) + _skill_flow(s, st, pal, sw_in, dark)
        story.append(KeepInFrame(sw_in, ph - top - bot, side, mode="shrink"))
        story += [NextPageTemplate("later"), FrameBreak()]
        head_style = ParagraphStyle("hl", fontName=st.face, fontSize=st.base + 3, leading=st.base + 7, textColor=HC(pal.accent_text))
        kind = st.opts["head"]
        story += [_name_para(content.name, st, pal.ink, 27)]
        if content.headline:
            story.append(Paragraph(_e(content.headline), head_style))
        story.append(HRFlowable(width=40 * mm, thickness=2.2, color=HC(pal.accent), spaceBefore=3 * mm, spaceAfter=1 * mm, hAlign="LEFT"))
        if content.summary:
            story += _heading("Profile", kind, st, pal, mw) + [Paragraph(_e(content.summary), st.body)]
        for s in content.main:
            story += _section_flow(s, st, pal, mw, kind)
        frame_w = mw

    # ------------------------------------------------------------------ banner
    elif layout == "banner":
        bh = 46 * mm
        sw = 62 * mm
        top_later, bot = 14 * mm, 13 * mm
        gap = 8 * mm
        mw = pw - 2 * mg - sw - gap
        sx = pw - mg - sw

        def bg1(c, doc):
            c.saveState()
            c.setFillColor(HC(pal.panel))
            c.rect(0, ph - bh, pw, bh, stroke=0, fill=1)
            c.setFillColor(HC(pal.accent))
            c.rect(0, ph - bh - 1.6 * mm, pw, 1.6 * mm, stroke=0, fill=1)
            c.setFillColor(HC(pal.tint))
            c.rect(sx - 6 * mm, 0, pw - sx + 6 * mm, ph - bh - 1.6 * mm, stroke=0, fill=1)
            c.restoreState()

        def bg2(c, doc):
            c.saveState()
            c.setFillColor(HC(pal.panel))
            c.rect(0, ph - 6 * mm, pw, 6 * mm, stroke=0, fill=1)
            c.restoreState()

        body_h = ph - bh - 1.6 * mm - 8 * mm - bot
        first = PageTemplate("first", [Frame(mg, ph - bh + 4 * mm, pw - 2 * mg, bh - 8 * mm, 0, 0, 0, 0, id="hdr"),
                                       Frame(sx, bot, sw, body_h, 0, 0, 0, 0, id="side"),
                                       Frame(mg, bot, mw, body_h, 0, 0, 0, 0, id="main")], onPage=bg1)
        later = PageTemplate("later", [Frame(mg, bot, pw - 2 * mg, ph - 6 * mm - 8 * mm - bot, 0, 0, 0, 0, id="m2")], onPage=bg2)
        templates = [first, later]
        head_style = ParagraphStyle("hl", fontName=st.face, fontSize=st.base + 3.5, leading=st.base + 8, textColor=HC(pal.accent_on_panel))
        con_style = ParagraphStyle("c", fontName=st.face, fontSize=st.base - 0.5, leading=st.base + 3, textColor=HC(pal.on_panel_muted))
        left = [_name_para(content.name, st, pal.on_panel, 29)]
        if content.headline:
            left.append(Paragraph(_e(content.headline), head_style))
        pimg = photo_img(30 * mm, pal.accent_on_panel)
        hdr_w = pw - 2 * mg
        inner = Table([[left, pimg or ""]], colWidths=[hdr_w - (34 * mm if pimg else 0), 34 * mm if pimg else 0.1])
        inner.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        story.append(KeepInFrame(hdr_w, bh - 8 * mm, [inner], mode="shrink"))
        story.append(FrameBreak())
        hs = ParagraphStyle("sh", fontName=st.bold, fontSize=st.base, leading=st.base + 4, charSpace=1.4, textColor=HC(pal.accent_text), keepWithNext=True)
        side = []
        if content.contact:
            side += [Paragraph("CONTACT", hs), HRFlowable(width="100%", thickness=0.6, color=HC(pal.accent), spaceBefore=1 * mm, spaceAfter=2.5 * mm)]
            for label, text, url in content.contact:
                side.append(Paragraph(f'<font size="{st.base - 2.5}" color="{pal.muted}">{label.upper()}</font><br/>' + (_link(text, url, pal.accent_text) if url else _e(text)), st.light_body))
                side.append(Spacer(1, 2 * mm))
        for s in content.side:
            side += [Spacer(1, 4 * mm), Paragraph(_e(s.title.upper()), hs), HRFlowable(width="100%", thickness=0.6, color=HC(pal.accent), spaceBefore=1 * mm, spaceAfter=2.5 * mm)]
            side += _skill_flow(s, st, pal, sw, False)
        story.append(KeepInFrame(sw, body_h, side, mode="shrink"))
        story += [NextPageTemplate("later"), FrameBreak()]
        if content.summary:
            story += [Paragraph(_e(content.summary), ParagraphStyle("sum", parent=st.body, fontSize=st.base + 1, leading=(st.base + 1) * 1.45)), Spacer(1, 1 * mm)]
        for s in content.main:
            story += _section_flow(s, st, pal, mw, st.opts["head"])
        frame_w = mw

    # ------------------------------------------------------------------ single column layouts
    else:
        top = 16 * mm
        strip = layout == "bold"

        def bg(c, doc):
            if strip:
                c.saveState()
                c.setFillColor(HC(pal.panel))
                c.rect(0, ph - 7 * mm, pw, 7 * mm, stroke=0, fill=1)
                c.setFillColor(HC(pal.accent))
                c.rect(0, ph - 8.4 * mm, pw, 1.4 * mm, stroke=0, fill=1)
                c.restoreState()

        topm = top + (6 * mm if strip else 0)
        fw = pw - 2 * mg
        frame = Frame(mg, 14 * mm, fw, ph - topm - 14 * mm, 0, 0, 0, 0)
        templates = [PageTemplate("first", [frame], onPage=bg), PageTemplate("later", [Frame(mg, 14 * mm, fw, ph - topm - 14 * mm, 0, 0, 0, 0)], onPage=bg)]
        align = TA_CENTER if layout == "classic" else TA_LEFT
        size = {"classic": 27, "minimal": 31, "bold": 28, "compact": 22}[layout]
        name_color = pal.accent_text if layout in {"classic", "bold"} else pal.ink
        head_style = ParagraphStyle("hl", fontName=st.face, fontSize=st.base + 2.5, leading=st.base + 6, textColor=HC(pal.accent_text if layout != "classic" else pal.muted), alignment=align)
        con_style = ParagraphStyle("c", fontName=st.face, fontSize=st.base - 0.5, leading=st.base + 3.5, textColor=HC(pal.muted), alignment=align)
        left = [_name_para(content.name, st, name_color, size, align)]
        if content.headline:
            left.append(Paragraph(_e(content.headline), head_style))
        cp = _contact_para(content, st, pal.muted, pal.accent_text, style=con_style)
        if cp:
            left += [Spacer(1, 1.5 * mm), cp]
        pimg = photo_img(27 * mm)
        if pimg and layout != "classic":
            hdr = Table([[left, pimg]], colWidths=[fw - 31 * mm, 31 * mm])
            hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                     ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            story.append(hdr)
        else:
            if pimg:
                pimg.hAlign = "CENTER"
                story += [pimg, Spacer(1, 2 * mm)]
            story += left
        thick = 2.4 if layout in {"bold", "classic"} else 0.8
        story.append(HRFlowable(width="100%", thickness=thick, color=HC(pal.accent), spaceBefore=3.5 * mm, spaceAfter=1 * mm))
        kind = st.opts["head"]
        if content.summary:
            story += _heading("Profile", kind, st, pal, fw) + [Paragraph(_e(content.summary), st.body)]
        for s in content.flat:
            story += _section_flow(s, st, pal, fw, kind)
        frame_w = fw

    story.insert(0, NextPageTemplate("later")) if False else None
    doc = BaseDocTemplate(str(path), pagesize=page, pageTemplates=templates, title=profile.title or profile.full_name or "CV",
                          author=profile.full_name or "CV Studio", subject="CV created with CV Studio", creator="CV Studio")
    doc.build(story)
    if not path.is_file() or path.stat().st_size < 800:
        raise OSError("The PDF export did not produce a valid file.")
    return path


def export_cover_letter_pdf(profile, text: str, output_path: str | Path) -> Path:
    """Export the user's editable letter text as a readable PDF in the CV's accent colour."""
    tpl = get_template(profile.template_id)
    pal = palette_for(profile, tpl)
    face = pdf_font(tpl.font)
    bold = pdf_bold(face)
    path = Path(output_path).expanduser()
    if path.suffix.lower() != ".pdf":
        path = path.with_suffix(".pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    page = A4 if profile.page_size == "A4" else LETTER
    pw, ph = page

    def bg(c, doc):
        c.saveState()
        c.setFillColor(HC(pal.panel))
        c.rect(0, ph - 6 * mm, pw, 6 * mm, stroke=0, fill=1)
        c.setFillColor(HC(pal.accent))
        c.rect(0, ph - 7.4 * mm, pw, 1.4 * mm, stroke=0, fill=1)
        c.restoreState()

    doc = BaseDocTemplate(str(path), pagesize=page, title="Cover Letter", author=profile.full_name or "CV Studio", creator="CV Studio")
    doc.addPageTemplates([PageTemplate("p", [Frame(22 * mm, 20 * mm, pw - 44 * mm, ph - 46 * mm, 0, 0, 0, 0)], onPage=bg)])
    story = []
    if profile.full_name:
        story.append(Paragraph(_e(profile.full_name), ParagraphStyle("n", fontName=bold, fontSize=22, leading=26, textColor=HC(pal.accent_text))))
    contact = " · ".join(x for x in [profile.email, profile.phone, profile.location] if x)
    if contact:
        story += [Paragraph(_e(contact), ParagraphStyle("c", fontName=face, fontSize=9.5, leading=13, textColor=HC(pal.muted))),
                  HRFlowable(width="100%", thickness=1.2, color=HC(pal.accent), spaceBefore=3 * mm, spaceAfter=8 * mm)]
    body = ParagraphStyle("b", fontName=face, fontSize=11, leading=16.5, textColor=HC(pal.ink), spaceAfter=5 * mm)
    for para in (text or "").split("\n\n"):
        if para.strip():
            story.append(Paragraph(_e(para.strip()).replace("\n", "<br/>"), body))
    doc.build(story)
    if not path.is_file() or path.stat().st_size < 600:
        raise OSError("The cover letter PDF export did not produce a valid file.")
    return path
