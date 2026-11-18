"""Render exported PDFs to images with Qt's own PDF module, so the on-screen preview is the real file."""
from __future__ import annotations


def available() -> bool:
    try:
        from PySide6.QtPdf import QPdfDocument  # noqa: F401
        return True
    except Exception:
        return False


def render_pdf(path, width_px: int, max_pages: int = 8):
    """Return a list of QImage (white background), one per page. Empty list on failure."""
    try:
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtPdf import QPdfDocument
    except Exception:
        return []
    doc = QPdfDocument()
    try:
        if doc.load(str(path)) != QPdfDocument.Error.None_:
            return []
        images = []
        for i in range(min(doc.pageCount(), max_pages)):
            pts = doc.pagePointSize(i)
            if pts.width() <= 0:
                continue
            h = max(1, int(width_px * pts.height() / pts.width()))
            raw = doc.render(i, QSize(width_px, h))
            canvas = QImage(width_px, h, QImage.Format.Format_ARGB32)
            canvas.fill(QColor("white"))
            p = QPainter(canvas)
            p.drawImage(0, 0, raw)
            p.end()
            images.append(canvas)
        return images
    finally:
        doc.close()
