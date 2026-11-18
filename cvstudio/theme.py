"""Light / dark Qt style sheets for CV Studio."""

PALETTES = {
    "light": dict(bg="#F4F6FB", surface="#FFFFFF", surface2="#EEF1F8", border="#DCE2EE", text="#1B2338", muted="#6B7690",
                  accent="#4F5BD5", accent_hover="#4048B8", accent_soft="#E9ECFF", side="#111827", side_hover="#27324A", side_text="#D5DCEA", on_accent="#FFFFFF"),
    "dark": dict(bg="#121826", surface="#1B2335", surface2="#232D44", border="#324058", text="#E8ECF5", muted="#9AA6BF",
                 accent="#7B87FF", accent_hover="#939DFF", accent_soft="#2A3358", side="#0B101C", side_hover="#1E2940", side_text="#C3CCDF", on_accent="#0B1020"),
}


def resolve(mode: str, app=None) -> str:
    if mode in ("light", "dark"):
        return mode
    try:  # follow system (Qt >= 6.5)
        from PySide6.QtCore import Qt
        scheme = (app or __import__("PySide6.QtWidgets", fromlist=["QApplication"]).QApplication.instance()).styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    except Exception:
        return "light"


def qss(mode: str) -> str:
    c = PALETTES[mode]
    return f"""
* {{ font-family:'Segoe UI','Inter',Arial; font-size:13px; }}
QWidget {{ background:{c['bg']}; color:{c['text']}; }}
QLabel {{ background:transparent; }}
QToolTip {{ background:{c['surface']}; color:{c['text']}; border:1px solid {c['border']}; padding:6px; }}
QFrame#Sidebar {{ background:{c['side']}; border:0; }}
QFrame#Sidebar QLabel {{ color:#FFFFFF; background:transparent; }}
QFrame#Card {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:14px; }}
QFrame#Hero {{ background:{c['side']}; border-radius:18px; }}
QFrame#Hero QLabel {{ color:#FFFFFF; background:transparent; }}
QPushButton {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:10px; padding:9px 15px; font-weight:600; }}
QPushButton:hover {{ border-color:{c['accent']}; background:{c['accent_soft']}; }}
QPushButton:focus {{ border-color:{c['accent']}; }}
QPushButton:disabled {{ color:{c['muted']}; }}
QPushButton#Primary {{ background:{c['accent']}; color:{c['on_accent']}; border:0; }}
QPushButton#Primary:hover {{ background:{c['accent_hover']}; }}
QPushButton#Back {{ padding:5px 16px; border-radius:17px; font-weight:600; color:{c['accent']}; background:{c['surface']}; border:1px solid {c['border']}; }}
QPushButton#Back:hover {{ background:{c['accent_soft']}; border-color:{c['accent']}; }}
QPushButton#Back:pressed {{ background:{c['accent']}; color:{c['on_accent']}; }}
QPushButton#Burger {{ font-size:18px; padding:2px; border-radius:8px; }}
QFrame#TplCard {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:14px; }}
QFrame#TplCard[previewed="true"] {{ border:1px solid {c['accent']}; }}
QFrame#TplCard[selected="true"] {{ border:2px solid {c['accent']}; background:{c['accent_soft']}; }}
QLabel#TplName {{ font-weight:700; font-size:14px; }}
QLabel#TplMeta {{ color:{c['muted']}; font-size:12px; }}
QLabel#TplTag {{ background:{c['accent']}; color:{c['on_accent']}; border-radius:8px; padding:2px 8px; font-size:11px; font-weight:700; }}
QPushButton#Fav[favorite="true"] {{ background:{c['accent_soft']}; border:1px solid {c['accent']}; color:{c['accent']}; }}
QPushButton#Nav {{ background:transparent; color:{c['side_text']}; border:0; text-align:left; padding:12px 14px; border-radius:10px; }}
QPushButton#Nav:hover, QPushButton#Nav:checked {{ background:{c['side_hover']}; color:#FFFFFF; }}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:8px; padding:8px; selection-background-color:{c['accent']}; selection-color:{c['on_accent']}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border:1px solid {c['accent']}; }}
QComboBox QAbstractItemView {{ background:{c['surface']}; color:{c['text']}; selection-background-color:{c['accent_soft']}; selection-color:{c['text']}; }}
QTabWidget::pane {{ border:1px solid {c['border']}; border-radius:12px; background:{c['surface']}; top:-1px; }}
QTabBar::tab {{ padding:9px 14px; background:{c['surface2']}; border-top-left-radius:8px; border-top-right-radius:8px; margin-right:3px; color:{c['muted']}; }}
QTabBar::tab:selected {{ background:{c['surface']}; color:{c['accent']}; font-weight:600; }}
QGroupBox {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:12px; margin-top:14px; padding:14px; font-weight:700; }}
QGroupBox::title {{ subcontrol-origin:margin; left:14px; padding:0 5px; }}
QListWidget {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:10px; padding:5px; outline:0; }}
QListWidget::item {{ padding:8px; border-radius:8px; }}
QListWidget::item:selected {{ background:{c['accent_soft']}; color:{c['text']}; border:1px solid {c['accent']}; }}
QListWidget::item:hover {{ background:{c['surface2']}; }}
QScrollArea {{ border:0; background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:12px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{c['border']}; border-radius:5px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{c['muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}
QScrollBar:horizontal {{ background:transparent; height:12px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{c['border']}; border-radius:5px; min-width:30px; }}
QProgressBar {{ border:0; background:{c['surface2']}; border-radius:5px; height:8px; text-align:center; }}
QProgressBar::chunk {{ background:{c['accent']}; border-radius:5px; }}
QCheckBox {{ background:transparent; spacing:8px; }}
QMessageBox, QDialog {{ background:{c['bg']}; }}
"""
