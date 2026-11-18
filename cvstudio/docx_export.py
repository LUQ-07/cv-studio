"""Editable DOCX export (python-docx). Mirrors the PDF layouts using real Word
tables, cell shading, borders and tab stops, so every line stays editable."""
from __future__ import annotations

from pathlib import Path

from .design import build_content, is_safe_url, level_fraction, monogram_png, on_color, palette_for, profile_photo, word_font
from .templates import SIDEBAR_LAYOUTS, get_template


def _rgb(h):
    from docx.shared import RGBColor
    return RGBColor.from_string(h.lstrip("#").upper())


def _shade(cell, hex_color):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_color.lstrip("#").upper())
    tcPr.append(shd)


def _cell_margins(cell, top=0, bottom=0, left=0, right=0):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(int(val * 1440))); el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def _table(doc, widths_in, rows=1):
    from docx.shared import Inches
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    t = doc.add_table(rows=rows, cols=len(widths_in))
    t.autofit = False
    tblPr = t._tbl.tblPr
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "fixed"); tblPr.append(layout)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{edge}"); b.set(qn("w:val"), "nil"); borders.append(b)
    tblPr.append(borders)
    ind = OxmlElement("w:tblInd"); ind.set(qn("w:w"), "0"); ind.set(qn("w:type"), "dxa"); tblPr.append(ind)
    for row in t.rows:
        for i, w in enumerate(widths_in):
            row.cells[i].width = Inches(w)
    grid = t._tbl.tblGrid
    for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(int(widths_in[i] * 1440)))
    return t


def _row_height(row, inches, rule="atLeast"):
    from docx.shared import Inches
    from docx.enum.table import WD_ROW_HEIGHT_RULE
    row.height = Inches(inches)
    row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST if rule == "atLeast" else WD_ROW_HEIGHT_RULE.EXACTLY


def _para(container, text="", *, size=10, color="#1F2937", bold=False, italic=False, align=None, before=0, after=0,
          font=None, line=None, spacing=None, keep_next=False, style=None):
    from docx.shared import Pt
    p = container.add_paragraph()
    if style:
        _apply_style(p, style, font=font or "Calibri", size=size, color=color, bold=bold, italic=italic)
    pf = p.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    if line:
        pf.line_spacing = line
    if keep_next:
        pf.keep_with_next = True
    if align is not None:
        p.alignment = align
    if text:
        _run(p, text, size=size, color=color, bold=bold, italic=italic, font=font, spacing=spacing)
    return p


def _apply_style(p, name, *, font, size, color, bold=False, italic=False, before=None, after=None, base="Normal"):
    """Give the paragraph a named Word style (CV Name, CV Section Heading, ...) that carries the same font, size, colour and
    weight. The paragraph keeps its own formatting, so the look is unchanged; but in Word the styles appear in the Styles
    gallery, so anything the user adds or edits can match the template with one click."""
    from docx.enum.style import WD_STYLE_TYPE
    from docx.shared import Pt
    try:
        styles = p.part.styles
        try:
            style = styles[name]
        except KeyError:
            style = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            style.base_style = styles[base]
            style.quick_style = True
            style.font.name, style.font.size, style.font.bold, style.font.italic = font, Pt(size), bold, italic
            style.font.color.rgb = _rgb(color)
            if before is not None: style.paragraph_format.space_before = Pt(before)
            if after is not None: style.paragraph_format.space_after = Pt(after)
        p.style = style
    except Exception:       # styles are a convenience: never let them break an export
        pass


def _run(p, text, *, size=10, color="#1F2937", bold=False, italic=False, font=None, spacing=None, url=None):
    from docx.shared import Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    r = p.add_run(text)
    r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic; r.font.color.rgb = _rgb(color)
    if font:
        r.font.name = font
        rPr = r._element.get_or_add_rPr()
        rf = rPr.find(qn("w:rFonts"))
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(attr), font)
    if spacing:
        sp = OxmlElement("w:spacing"); sp.set(qn("w:val"), str(int(spacing * 20))); r._element.get_or_add_rPr().append(sp)
    return r


def _hyperlink(p, text, url, *, size, color, font, bold=False):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.shared import Pt
    rid = p.part.relate_to(url, RT.HYPERLINK, is_external=True)
    h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), rid)
    r = OxmlElement("w:r"); rPr = OxmlElement("w:rPr")
    rf = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rf.set(qn(a), font)
    rPr.append(rf)
    if bold:
        rPr.append(OxmlElement("w:b"))
    c = OxmlElement("w:color"); c.set(qn("w:val"), color.lstrip("#").upper()); rPr.append(c)
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); rPr.append(sz)
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rPr.append(u)
    r.append(rPr)
    t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve"); r.append(t)
    h.append(r); p._p.append(h)


def _border(p, side, color, sz=6, space=2):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    pPr = p._p.get_or_add_pPr()
    bdr = pPr.find(qn("w:pBdr"))
    if bdr is None:
        bdr = OxmlElement("w:pBdr"); pPr.append(bdr)
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"), "single"); el.set(qn("w:sz"), str(sz)); el.set(qn("w:space"), str(space)); el.set(qn("w:color"), color.lstrip("#").upper())
    bdr.append(el)


def _drop_empty_first(cell):
    ps = cell.paragraphs
    if len(ps) > 1 and not ps[0].text and not ps[0]._p.findall(".//{*}drawing"):
        ps[0]._p.getparent().remove(ps[0]._p)


def _bullet(container, text, *, size, color, font, indent=0.17, after=1.5):
    """A real Word bullet list item (the user can press Enter to add the next bullet). Falls back to a typed bullet."""
    from docx.shared import Inches, Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    p = container.add_paragraph()
    pf = p.paragraph_format
    real = True
    try:
        _apply_style(p, "CV Bullet", font=font, size=size, color=color, base="List Bullet")
        real = p.style is not None and p.style.name == "CV Bullet"
    except Exception:
        real = False
    pf.left_indent = Inches(indent); pf.first_line_indent = Inches(-indent); pf.space_after = Pt(after); pf.space_before = Pt(0)
    if real:
        pPr = p._p.get_or_add_pPr(); mark = OxmlElement("w:rPr")          # bullet glyph takes the text colour and size
        c = OxmlElement("w:color"); c.set(qn("w:val"), color.lstrip("#").upper()); mark.append(c)
        sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); mark.append(sz)
        pPr.append(mark)
        _run(p, text, size=size, color=color, font=font)
    else:
        pf.tab_stops.add_tab_stop(Inches(indent))
        _run(p, "•\t" + text, size=size, color=color, font=font)
    return p


def _entry(container, e, width_in, ctx):
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_TAB_ALIGNMENT
    pal, font, base = ctx["pal"], ctx["font"], ctx["base"]
    k, below = ctx["k"], ctx["opts"]["date"] == "below" and bool(e.dates)
    p = container.add_paragraph()
    p.paragraph_format.space_before = Pt(3 * k); p.paragraph_format.space_after = Pt(0); p.paragraph_format.keep_with_next = True
    if e.dates and not below:
        p.paragraph_format.tab_stops.add_tab_stop(Inches(width_in), WD_TAB_ALIGNMENT.RIGHT)
    _apply_style(p, "CV Job Title", font=font, size=base + .5, color=pal.ink, bold=True, before=3 * k, after=0)
    if e.url and is_safe_url(e.url):
        _hyperlink(p, e.title, e.url, size=base + .5, color=pal.accent_text, font=font, bold=True)
    else:
        _run(p, e.title, size=base + .5, bold=True, color=pal.ink, font=font)
    if e.dates and not below:
        _run(p, "\t" + e.dates, size=base - .5, bold=True, color=pal.accent_text, font=font)
    if below:                                              # dates on the line under the title, same as the PDF
        s = _para(container, "", keep_next=bool(e.lines), style="CV Details")
        _run(s, e.dates, size=base, bold=True, color=pal.accent_text, font=font)
        if e.sub:
            _run(s, "  ·  " + e.sub, size=base, color=pal.muted, font=font)
    elif e.sub:
        s = _para(container, e.sub, size=base, color=pal.muted, font=font, keep_next=bool(e.lines), style="CV Details")
    for i, line in enumerate(e.lines):
        if line[:1] in "-•*–·" and len(line) > 1:
            _bullet(container, line[1:].strip(), size=base, color=pal.ink, font=font)
        else:
            _para(container, line, size=base, color=pal.ink, font=font, after=2, style="CV Body")
    last = container.paragraphs[-1]
    last.paragraph_format.space_after = Pt(max(4 * k, last.paragraph_format.space_after.pt if last.paragraph_format.space_after else 0))


def _heading(container, title, kind, ctx, width_in):
    from docx.shared import Inches, Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    pal, font, base, k = ctx["pal"], ctx["font"], ctx["base"], ctx["k"]
    p = _para(container, "", before=11 * k, after=4 * k, keep_next=True)
    _apply_style(p, "CV Section Heading", font=font, size=base + 1.2, color=pal.accent_text if kind != "plain" else pal.ink, bold=True, before=11 * k, after=4 * k)
    if kind == "dot":                                      # accent dot in front of the heading
        _run(p, "● ", size=base - 1, color=pal.accent, font="Segoe UI Symbol")
    _run(p, title.upper(), size=base + 1.2, bold=True, font=font, color=pal.accent_text if kind != "plain" else pal.ink, spacing=1.0)
    pf = p.paragraph_format
    if kind == "rule":
        _border(p, "bottom", pal.accent, 8, 2)
    elif kind in ("plain", "dot"):
        _border(p, "bottom", pal.soft, 4, 2)
    elif kind == "bar":
        _border(p, "left", pal.accent, 36, 6)
    elif kind in ("short", "center"):
        # a short accent underline = a separate 2 pt paragraph with a bottom border and wide indents
        # (narrowing the heading paragraph itself would wrap the heading text)
        pf.space_after = Pt(0)
        if kind == "center":
            p.alignment = 1
        u = _para(container, "", after=4 * k, keep_next=True)
        u.paragraph_format.line_spacing = Pt(3)
        u.add_run(" ").font.size = Pt(1)
        if kind == "center":
            side = max(0.0, (width_in - 0.55) / 2)
            u.paragraph_format.left_indent = Inches(side); u.paragraph_format.right_indent = Inches(side)
            _border(u, "bottom", pal.accent, 8, 1)
        else:
            u.paragraph_format.right_indent = Inches(max(0.0, width_in - 0.55)); _border(u, "bottom", pal.accent, 14, 1)
    elif kind == "band":                                   # tinted band with an accent edge
        pf.left_indent = Inches(0.06)
        pPr = p._p.get_or_add_pPr(); shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), pal.tint.lstrip("#").upper()); pPr.append(shd)
        _border(p, "left", pal.accent, 24, 4)
    return p


def _skills_flat(container, section, ctx, width_in):
    names = [(e.title + (f" ({e.level})" if e.level else "")) for e in section.entries]
    if ctx["opts"]["skills"] == "cols" and len(names) > 3:      # tidy three-column grid, same as the PDF
        rows = [names[i:i + 3] for i in range(0, len(names), 3)]
        t = _table(container, [width_in / 3] * 3, rows=len(rows))
        for r, chunk in enumerate(rows):
            for c in range(3):
                cell = t.cell(r, c)
                if c < len(chunk):
                    para = cell.paragraphs[0]; para.paragraph_format.space_after = 0
                    _run(para, "•  " + chunk[c], size=ctx["base"] - .5, color=ctx["pal"].ink, font=ctx["font"])
        return
    _para(container, "  ·  ".join(names), size=ctx["base"], color=ctx["pal"].ink, font=ctx["font"], after=3)


def _skills_side(container, section, ctx, dark, width_in):
    pal, font, base = ctx["pal"], ctx["font"], ctx["base"]
    ink = pal.on_panel if dark else pal.ink
    muted = pal.on_panel_muted if dark else pal.muted
    mode = ctx["opts"]["skills"] if ctx["opts"]["skills"] in {"bars", "dots", "plain"} else "bars"
    for e in section.entries:
        if section.key == "certificates":
            _para(container, e.title, size=base - .5, bold=True, color=ink, font=font, before=2)
            sub = " · ".join(x for x in (e.sub, e.dates) if x)
            if sub:
                _para(container, sub, size=base - 1.5, color=muted, font=font, after=3)
            continue
        frac = level_fraction(e.level)
        if mode == "plain" or frac is None:
            p = _para(container, "", before=2, after=2)
            _run(p, e.title, size=base - .5, color=ink, font=font)
            if e.level:
                _run(p, "  · " + e.level, size=base - 1.5, color=muted, font=font)
            continue
        _para(container, e.title, size=base - .5, color=ink, font=font, before=2, after=0)
        n = round(frac * (8 if mode == "bars" else 5))
        total = 8 if mode == "bars" else 5
        glyphs = ("▰" * n + "▱" * (total - n)) if mode == "bars" else ("●" * max(1, n) + "○" * (total - max(1, n)))
        _para(container, glyphs, size=base - 2.5, color=pal.accent_on_panel if dark else pal.accent, font="Segoe UI Symbol", after=2)


def _side_head(container, title, ctx, dark):
    pal = ctx["pal"]
    p = _para(container, title.upper(), size=ctx["base"], bold=True, font=ctx["font"], before=12, after=4, keep_next=True,
              color=pal.accent_on_panel if dark else pal.accent_text, spacing=1.2)
    _border(p, "bottom", pal.on_panel_muted if dark else pal.soft, 4, 2)


def _contact_side(container, content, ctx, dark):
    pal, font, base = ctx["pal"], ctx["font"], ctx["base"]
    muted = pal.on_panel_muted if dark else pal.muted
    ink = pal.on_panel if dark else pal.ink
    for label, text, url in content.contact:
        _para(container, label.upper(), size=base - 2.5, color=muted, font=font, before=3, after=0)
        p = _para(container, "", after=2)
        if url and is_safe_url(url):
            _hyperlink(p, text, url, size=base - .5, color=ink if dark else pal.accent_text, font=font)
        else:
            _run(p, text, size=base - .5, color=ink, font=font)


def _tiny_tail(doc):
    from docx.shared import Pt
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0); p.paragraph_format.space_before = Pt(0); p.paragraph_format.line_spacing = Pt(1)
    r = p.add_run(" "); r.font.size = Pt(1)


def _estimated_pages(profile) -> int:
    """Page count of the matching PDF layout; used to extend sidebar shading over every page."""
    import re, tempfile
    from .exporter import export_pdf
    try:
        with tempfile.TemporaryDirectory() as tmp:
            data = export_pdf(profile, Path(tmp) / "est.pdf").read_bytes()
        return max(1, len(re.findall(rb"/Type\s*/Page\b", data)))
    except Exception:
        return 1


def export_docx(profile, output_path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    tpl = get_template(profile.template_id)
    pal = palette_for(profile, tpl)
    content = build_content(profile, tpl)
    font = word_font(tpl.font)
    base = max(8.5, min(13, float(profile.font_size or 10)))
    ctx = {"pal": pal, "font": font, "base": base, "opts": tpl.opts,
           "k": {"airy": 1.18, "tight": 0.84}.get(tpl.opts["density"], 1.0)}
    path = Path(output_path).expanduser()
    if path.suffix.lower() != ".docx":
        path = path.with_suffix(".docx")
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = font; normal.font.size = Pt(base)
    normal.paragraph_format.line_spacing = {"airy": 1.12, "tight": 1.0}.get(tpl.opts["density"], 1.05)
    rpr = normal.element.get_or_add_rPr()
    rf = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
    for a in ("ascii", "hAnsi", "cs", "eastAsia"):
        rf.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}" + a, font)
    sec = doc.sections[0]
    pw_in, ph_in = (8.27, 11.69) if profile.page_size == "A4" else (8.5, 11.0)
    sec.page_width, sec.page_height = Inches(pw_in), Inches(ph_in)
    sec.header_distance = sec.footer_distance = Inches(0)
    # remove the default empty first paragraph
    photo = profile_photo(profile)
    layout = tpl.layout

    def add_photo(container, width, align=WD_ALIGN_PARAGRAPH.CENTER, mono_bg=None):
        """The user's photo; with none (and photos on) a monogram circle, like the PDF."""
        img = photo
        if img is None and mono_bg and profile.show_photo:
            img = monogram_png(content.name, mono_bg, on_color(mono_bg))
        if img is None:
            return
        img.seek(0)
        p = container.add_paragraph(); p.alignment = align
        p.add_run().add_picture(img, width=Inches(width))
        p.paragraph_format.space_after = Pt(6)

    def main_flow(container, width_in, kind, sections):
        for s in sections:
            _heading(container, s.title, kind, ctx, width_in)
            if s.kind == "skills":
                _skills_flat(container, s, ctx, width_in)
            elif s.kind == "text":
                for line in s.entries[0].lines:
                    _para(container, line, size=base, font=font, after=3)
            else:
                for e in s.entries:
                    _entry(container, e, width_in, ctx)

    def name_block(container, align, color, size, head_color, bold=True, light_name=False):
        mode = tpl.opts["name"]                      # normal | caps | light, same as the PDF
        text, spacing = content.name, None
        if mode == "caps":
            text, size, bold, spacing = content.name.upper(), size * 0.82, True, 1.6
        elif mode == "light":
            size, bold, spacing = size * 1.08, False, 0.5
        else:
            bold = True
        _para(container, text, size=size, bold=bold, color=color, font=font, align=align, after=1, line=1.0, spacing=spacing, style="CV Name")
        if content.headline:
            _para(container, content.headline, size=base + 3, color=head_color, font=font, align=align, after=3, style="CV Headline")

    # ------------------------------------------------------------ sidebar
    if layout in SIDEBAR_LAYOUTS:
        dark = layout != "sidebar_light"
        right = layout == "sidebar_right"
        sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Inches(0)
        sw, mw = 2.75, pw_in - 2.75
        widths = [mw, sw] if right else [sw, mw]
        t = _table(doc, widths)
        _row_height(t.rows[0], min(21.9, _estimated_pages(profile) * (ph_in - 0.12)))
        side, main = (t.cell(0, 1), t.cell(0, 0)) if right else (t.cell(0, 0), t.cell(0, 1))
        _shade(side, pal.panel if dark else pal.tint)
        _cell_margins(side, top=0.45, bottom=0.3, left=0.3, right=0.3)
        _cell_margins(main, top=0.5, bottom=0.4, left=0.4 if not right else 0.55, right=0.55 if not right else 0.4)
        add_photo(side, 1.45, mono_bg=pal.accent_on_panel if dark else pal.accent)
        if content.contact:
            _side_head(side, "Contact", ctx, dark); _contact_side(side, content, ctx, dark)
        for s in content.side:
            _side_head(side, s.title, ctx, dark); _skills_side(side, s, ctx, dark, sw - .6)
        _drop_empty_first(side)
        text_w = mw - 0.95
        name_block(main, WD_ALIGN_PARAGRAPH.LEFT, pal.ink, 27, pal.accent_text)
        p = _para(main, "", after=2); _border(p, "bottom", pal.accent, 18, 1)
        if content.summary:
            _heading(main, "Profile", tpl.opts["head"], ctx, text_w); _para(main, content.summary, size=base, font=font, after=3)
        main_flow(main, text_w, tpl.opts["head"], content.main)
        _drop_empty_first(main)
        sec.left_margin = sec.right_margin = Inches(0)

    # ------------------------------------------------------------ banner
    elif layout == "banner":
        sec.top_margin = sec.bottom_margin = sec.left_margin = sec.right_margin = Inches(0)
        sw = 2.45
        mw = pw_in - sw
        t = _table(doc, [mw, sw], rows=2)
        top = t.cell(0, 0).merge(t.cell(0, 1))
        _row_height(t.rows[0], 1.7, "exact")
        _shade(top, pal.panel)
        _cell_margins(top, top=0.35, bottom=0.2, left=0.6, right=0.6)
        hdr = _table(top, [pw_in - 1.2 - 1.3, 1.3])
        from docx.enum.table import WD_ALIGN_VERTICAL
        left_cell, right_cell = hdr.cell(0, 0), hdr.cell(0, 1)
        left_cell.vertical_alignment = right_cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        name_block(left_cell, WD_ALIGN_PARAGRAPH.LEFT, pal.on_panel, 29, pal.accent_on_panel)
        add_photo(right_cell, 1.05, WD_ALIGN_PARAGRAPH.RIGHT, mono_bg=pal.accent_on_panel)
        _drop_empty_first(left_cell); _drop_empty_first(right_cell); _drop_empty_first(top)
        tail = top.paragraphs[-1]; tail.paragraph_format.space_after = Pt(0); tail.paragraph_format.line_spacing = Pt(1)
        for r in tail.runs: r.font.size = Pt(1)
        _row_height(t.rows[1], min(21.9 - 1.7, _estimated_pages(profile) * (ph_in - 0.12) - 1.7))
        main, side = t.cell(1, 0), t.cell(1, 1)
        _shade(side, pal.tint)
        _cell_margins(main, top=0.3, bottom=0.4, left=0.6, right=0.3)
        _cell_margins(side, top=0.3, bottom=0.3, left=0.3, right=0.4)
        if content.contact:
            _side_head(side, "Contact", ctx, False); _contact_side(side, content, ctx, False)
        for s in content.side:
            _side_head(side, s.title, ctx, False); _skills_side(side, s, ctx, False, sw - .7)
        _drop_empty_first(side)
        text_w = mw - 0.9
        if content.summary:
            _para(main, content.summary, size=base + 1, font=font, after=4, before=2)
        main_flow(main, text_w, tpl.opts["head"], content.main)
        _drop_empty_first(main)

    # ------------------------------------------------------------ single column
    else:
        sec.top_margin = Inches(0.7 if layout != "bold" else 0.6); sec.bottom_margin = Inches(0.65)
        sec.left_margin = sec.right_margin = Inches(0.75)
        text_w = pw_in - 1.5
        kind = tpl.opts["head"]
        align = WD_ALIGN_PARAGRAPH.CENTER if layout == "classic" else WD_ALIGN_PARAGRAPH.LEFT
        size = {"classic": 27, "minimal": 30, "bold": 28, "compact": 22}[layout]
        if layout == "bold":
            t = _table(doc, [text_w])
            c = t.cell(0, 0)
            _shade(c, pal.panel)
            _cell_margins(c, top=0.18, bottom=0.18, left=0.25, right=0.25)
            name_block(c, align, pal.on_panel, size, pal.accent_on_panel)
            _drop_empty_first(c)
            hdr_parent = doc
            _para(doc, "", after=0)
            contact_parent = doc
        else:
            if photo and layout != "classic":
                add_photo(doc, 0.95, WD_ALIGN_PARAGRAPH.RIGHT)
            name_block(doc, align, pal.accent_text if layout in {"classic", "bold"} else pal.ink, size,
                       pal.muted if layout == "classic" else pal.accent_text)
            contact_parent = doc
        if content.contact:
            p = _para(contact_parent, "", align=align, after=4)
            for i, (_l, text, url) in enumerate(content.contact):
                if i:
                    _run(p, "  ·  ", size=base - .5, color=pal.muted, font=font)
                if url and is_safe_url(url):
                    _hyperlink(p, text, url, size=base - .5, color=pal.accent_text, font=font)
                else:
                    _run(p, text, size=base - .5, color=pal.muted, font=font)
        if layout != "bold":
            _border(p if content.contact else doc.paragraphs[-1], "bottom", pal.accent, 18 if layout == "classic" else 8, 4)
        if content.summary:
            _heading(doc, "Profile", kind, ctx, text_w); _para(doc, content.summary, size=base, font=font, after=3)
        main_flow(doc, text_w, kind, content.flat)

    _tiny_tail(doc)
    doc.core_properties.title = profile.title or profile.full_name or "CV"
    doc.core_properties.author = profile.full_name or "CV Studio"
    doc.core_properties.comments = "Created with CV Studio"
    doc.save(path)
    if not path.is_file() or path.stat().st_size < 1500:
        raise OSError("The DOCX export did not produce a valid file.")
    return path


def export_cover_letter_docx(profile, text, output_path):
    from docx import Document
    from docx.shared import Inches, Pt
    tpl = get_template(profile.template_id)
    pal = palette_for(profile, tpl)
    font = word_font(tpl.font)
    path = Path(output_path).expanduser()
    if path.suffix.lower() != ".docx":
        path = path.with_suffix(".docx")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    s = doc.sections[0]
    s.page_width = Inches(8.27 if profile.page_size == "A4" else 8.5); s.page_height = Inches(11.69 if profile.page_size == "A4" else 11)
    s.top_margin = s.bottom_margin = Inches(.9); s.left_margin = s.right_margin = Inches(1)
    if profile.full_name:
        _para(doc, profile.full_name, size=22, bold=True, color=pal.accent_text, font=font, after=2)
    contact = "  ·  ".join(x for x in [profile.email, profile.phone, profile.location] if x)
    if contact:
        p = _para(doc, contact, size=9.5, color=pal.muted, font=font, after=14)
        _border(p, "bottom", pal.accent, 12, 6)
    for para in (text or "").split("\n\n"):
        if para.strip():
            _para(doc, para.strip(), size=11, color=pal.ink, font=font, after=9, line=1.25)
    doc.core_properties.title = "Cover Letter"; doc.core_properties.author = profile.full_name or "CV Studio"
    doc.save(path)
    if not path.is_file() or path.stat().st_size < 1200:
        raise OSError("The cover letter DOCX export did not produce a valid file.")
    return path
