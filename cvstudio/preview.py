"""Simple HTML preview used only as a fallback when Qt's PDF module is unavailable.
The primary preview renders the real exported PDF (see gui.py)."""
from html import escape

from .design import build_content, palette_for
from .templates import get_template


def render_html(profile) -> str:
    t = get_template(profile.template_id)
    pal = palette_for(profile, t)
    c = build_content(profile, t)
    dark = t.layout in {"sidebar", "sidebar_right"}
    face = "Cambria,Georgia,serif" if t.font == "serif" else ("Consolas,monospace" if t.font == "mono" else "Calibri,Segoe UI,Arial,sans-serif")

    def sections(items):
        out = []
        for s in items:
            rows = []
            for e in s.entries:
                head = f"<b>{escape(e.title)}</b>" + (f" <span style='color:{pal.accent_text}'>&nbsp;{escape(e.dates)}</span>" if e.dates else "")
                if s.kind == "skills":
                    rows.append(f"<div>{escape(e.title)} {escape(e.level)}</div>")
                    continue
                rows.append(f"<p style='margin:6px 0'>{head}<br/><span style='color:{pal.muted}'>{escape(e.sub)}</span><br/>{'<br/>'.join(escape(l) for l in e.lines)}</p>")
            out.append(f"<h3 style='color:{pal.accent_text};letter-spacing:1px;border-bottom:1px solid {pal.accent};margin:14px 0 4px'>{escape(s.title.upper())}</h3>{''.join(rows)}")
        return "".join(out)

    contact = "<br/>".join(escape(x[1]) for x in c.contact)
    head = f"<h1 style='margin:0;color:{pal.accent_text}'>{escape(c.name)}</h1><div style='color:{pal.muted};font-size:14px'>{escape(c.headline)}</div>"
    summary = f"<p>{escape(c.summary)}</p>" if c.summary else ""
    if t.two_column:
        side_bg = pal.panel if dark or t.layout == "banner" and False else pal.tint
        side_fg = "#FFFFFF" if dark else pal.ink
        body = (f"<table width='100%' cellspacing='0' cellpadding='14'><tr><td width='30%' bgcolor='{side_bg if dark else pal.tint}' valign='top' style='color:{side_fg}'>"
                f"<div>{contact}</div>{sections(c.side)}</td><td valign='top'>{head}{summary}{sections(c.main)}</td></tr></table>")
    else:
        body = f"<div style='padding:20px'>{head}<div style='color:{pal.muted}'>{contact.replace('<br/>', ' · ')}</div>{summary}{sections(c.flat)}</div>"
    return f"<!doctype html><html><body style='margin:0;background:#E5E8EF'><div class='{escape(t.layout)}' style='background:white;margin:16px;font-family:{face};font-size:12px;color:{pal.ink}'>{body}</div></body></html>"
