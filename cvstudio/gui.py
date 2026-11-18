"""CV Studio desktop interface (PySide6)."""
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QObject, QSize, Qt, QTimer, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
    QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QStackedWidget, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from . import __version__, i18n, pdfview, theme
from .docx_export import export_cover_letter_docx, export_docx
from .exporter import export_cover_letter_pdf, export_pdf
from .i18n import tr
from .job_tools import analyze_job_match, draft_cover_letter
from .models import CVProfile, sample_profile
from .preview import render_html
from .sections import ORDER, SPECS, SectionModel
from .settings import Settings
from .store_iap import PRODUCT_ID, Purchase, State, StoreCore, store_page_url
from .storage import ProfileStore, app_data_dir
from .templates import CATEGORIES, DESIGN_REV, TEMPLATES, get_template
from .validation import validate_profile

APP_NAME = "CV Studio"
PREMIUM_FEATURES = False  # All 30 templates are included; no Premium UI or purchase flow.
YES, NO = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
from PySide6.QtWidgets import QGridLayout
SIDEBAR_W = 230                      # width of the navigation sidebar when it is shown
CARD_W, THUMB_W, THUMB_H = 232, 208, 294   # template gallery card / thumbnail size


def asset_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def safe_export(func, profile, target, *extra):
    """Write to a partial file first so a failed export never damages an existing file."""
    target = Path(target)
    partial = target.with_name(f".{target.stem}.partial{target.suffix}")
    try:
        out = func(profile, *extra, partial) if extra else func(profile, partial)
        os.replace(out, target)
        return target
    finally:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass


class SectionPanel(QWidget):
    """One data-entry tab: an inline form for this category, an entry list below.

    Add New Entry / Update Entry, double-click a row to edit it, Delete to remove it. 100 % free for everyone.
    Rows live in the shared list passed in (MainWindow.cv_data[key]) so the exporters always see the latest data.
    """

    def __init__(self, spec, rows, on_change=None):
        super().__init__()
        self.spec, self.model, self.on_change, self.editing = spec, SectionModel(spec, rows), on_change, -1
        root = QVBoxLayout(self)
        hint = QLabel(tr("Double-click an entry to edit it. Leave optional values blank.")); hint.setWordWrap(True); root.addWidget(hint)
        self.box = QGroupBox(); form = QFormLayout(self.box); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.inputs = {}
        for f in spec.fields:
            label = tr(f.label) + (" *" if f.required else "")
            if f.kind == "text":
                w = QTextEdit(); w.setFixedHeight(84); w.setPlaceholderText(tr(f.placeholder)) if f.placeholder else None
                form.addRow(label, w)
            elif f.kind == "combo":
                w = QComboBox(); w.setEditable(True); w.addItems([tr(o) if o else "" for o in f.options]); w.setCurrentIndex(0)
                form.addRow(label, w)
            elif f.kind == "file":
                w = QLineEdit(); row = QHBoxLayout(); row.addWidget(w, 1); br = QPushButton("…"); br.setFixedWidth(40)
                br.clicked.connect(lambda _=False, t=w: self._choose_file(t)); row.addWidget(br); form.addRow(label, row)
            else:
                w = QLineEdit(); w.setPlaceholderText(f.placeholder); w.returnPressed.connect(self.submit); form.addRow(label, w)
            self.inputs[f.key] = w
        self.msg = QLabel(""); self.msg.setStyleSheet("color:#D64545"); form.addRow("", self.msg)
        row = QHBoxLayout()
        self.add_btn = QPushButton("＋  " + tr("Add New Entry")); self.add_btn.setObjectName("Primary"); self.add_btn.clicked.connect(self.submit)
        self.cancel_btn = QPushButton(tr("Cancel")); self.cancel_btn.clicked.connect(self.reset_form); self.cancel_btn.hide()
        row.addWidget(self.add_btn); row.addWidget(self.cancel_btn); row.addStretch(); form.addRow(row)
        root.addWidget(self.box)
        self.list = QListWidget(); self.list.itemDoubleClicked.connect(lambda it: self.edit(self.list.row(it))); root.addWidget(self.list, 1)
        bar = QHBoxLayout()
        self.del_btn = QPushButton(tr("Delete")); self.del_btn.clicked.connect(self.delete); bar.addWidget(self.del_btn)
        for text, d, tip in (("↑", -1, tr("Move up")), ("↓", 1, tr("Move down"))):
            b = QPushButton(text); b.setToolTip(tip); b.setFixedWidth(44); b.clicked.connect(lambda _=False, dd=d: self.move(dd)); bar.addWidget(b)
        self.count = QLabel(""); bar.addStretch(); bar.addWidget(self.count); root.addLayout(bar)
        self.reset_form(); self.refresh()

    # -- helpers
    def _choose_file(self, target):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose file"), "", "PDF / images (*.pdf *.png *.jpg *.jpeg);;All files (*)")
        if path:
            target.setText(path)

    def _values(self):
        out = {}
        for f in self.spec.fields:
            w = self.inputs[f.key]
            out[f.key] = w.toPlainText() if isinstance(w, QTextEdit) else (w.currentText() if isinstance(w, QComboBox) else w.text())
        return out

    def _fill(self, values):
        for f in self.spec.fields:
            w, v = self.inputs[f.key], values.get(f.key, "") or ""
            if isinstance(w, QTextEdit): w.setPlainText(v)
            elif isinstance(w, QComboBox): w.setCurrentText(v)
            else: w.setText(v)

    def _changed(self):
        if self.on_change:
            self.on_change()

    # -- actions
    def refresh(self):
        self.list.clear()
        for i, text in enumerate(self.model.labels()):
            self.list.addItem(text)
        self.count.setText(f"{len(self.model.rows)}")

    def reset_form(self):
        self.editing = -1; self._fill({}); self.msg.setText("")
        self.box.setTitle(f"{tr(self.spec.title)} — {tr('New entry')}"); self.add_btn.setText("＋  " + tr("Add New Entry")); self.cancel_btn.hide()

    def submit(self):
        values = self._values()
        missing = self.model.missing(values)
        if missing:
            self.msg.setText(tr("Required") + ": " + ", ".join(tr(m) for m in missing)); return
        if self.editing >= 0:
            self.model.update(self.editing, values); row = self.editing
        else:
            row = self.model.add(values)
        self.refresh(); self.list.setCurrentRow(row); self.reset_form(); self._changed()

    def edit(self, index):
        if 0 <= index < len(self.model.rows):
            self.editing = index; self._fill(self.model.rows[index]); self.msg.setText("")
            self.box.setTitle(f"{tr(self.spec.title)} — {tr('Editing entry')}"); self.add_btn.setText("✓  " + tr("Update Entry")); self.cancel_btn.show()

    def delete(self):
        row = self.list.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, tr("Delete"), tr("Delete this entry?")) != YES:
            return
        self.model.delete(row)
        if self.editing == row: self.reset_form()
        elif self.editing > row: self.editing -= 1
        self.refresh(); self.list.setCurrentRow(min(row, len(self.model.rows) - 1)); self._changed()

    def move(self, delta):
        row = self.list.currentRow()
        if row >= 0:
            new = self.model.move(row, delta)
            if new != row:
                if self.editing == row: self.editing = new
                self.refresh(); self.list.setCurrentRow(new); self._changed()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.list.hasFocus():
            self.delete()
        else:
            super().keyPressEvent(event)

    # -- API used by MainWindow
    def set_rows(self, rows):
        self.model.replace_all(rows); self.reset_form(); self.refresh()

    def get_rows(self):
        return self.model.rows


class ClickableLabel(QLabel):
    def __init__(self, on_click=None):
        super().__init__()
        self.on_click = on_click

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click()
        super().mousePressEvent(event)


class TemplateCard(QFrame):
    """One gallery card: thumbnail, name, category and its own USE THIS TEMPLATE / ADD TO FAVORITES buttons."""

    def __init__(self, t, pixmap, selected, favorite, previewed, meta, on_preview, on_use, on_fav):
        super().__init__()
        self.template_id = t.id
        self.setObjectName("TplCard"); self.setFixedWidth(CARD_W)
        self.setProperty("selected", bool(selected)); self.setProperty("favorite", bool(favorite)); self.setProperty("previewed", bool(previewed))
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 10, 10, 12); lay.setSpacing(7)
        self.thumb = ClickableLabel(lambda: on_preview(t.id))
        self.thumb.setFixedSize(THUMB_W, THUMB_H); self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setCursor(Qt.CursorShape.PointingHandCursor); self.thumb.setToolTip(tr("Click to preview"))
        self.thumb.setStyleSheet("border:1px solid rgba(128,128,128,0.35);background:white;")
        self.set_thumb(pixmap)
        lay.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignHCenter)
        head = QHBoxLayout()
        name = ClickableLabel(lambda: on_preview(t.id)); name.setObjectName("TplName"); name.setText(("★ " if favorite else "") + t.name)
        head.addWidget(name, 1)
        if selected:
            tag = QLabel("✓ " + tr("SELECTED")); tag.setObjectName("TplTag"); head.addWidget(tag)
        lay.addLayout(head)
        meta_label = QLabel(meta); meta_label.setObjectName("TplMeta"); lay.addWidget(meta_label)
        self.use_button = QPushButton(tr("USE THIS TEMPLATE")); self.use_button.setObjectName("Primary")
        self.use_button.clicked.connect(lambda _=False: on_use(t.id)); lay.addWidget(self.use_button)
        self.fav_button = QPushButton(tr("★ REMOVE FAVORITE") if favorite else tr("ADD TO FAVORITES")); self.fav_button.setObjectName("Fav")
        self.fav_button.setProperty("favorite", bool(favorite)); self.fav_button.clicked.connect(lambda _=False: on_fav(t.id)); lay.addWidget(self.fav_button)

    def set_thumb(self, pixmap):
        self.thumb.setPixmap(pixmap)

    def set_previewed(self, flag):
        self.setProperty("previewed", bool(flag)); self.style().unpolish(self); self.style().polish(self)


class CardScroll(QScrollArea):
    """Scroll area that tells the gallery when it was resized, so the cards can re-flow into more/fewer columns."""

    def __init__(self, on_resize):
        super().__init__()
        self.on_resize = on_resize
        self.setWidgetResizable(True); self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(80, self.on_resize)


class StoreBridge(QObject):
    """Hands results of the background Store worker to the UI thread (queued signals; the UI never waits)."""
    checked = Signal(object)
    purchased = Signal(object)

    def __init__(self, core):
        super().__init__()
        self.core = core

    def check(self):
        self.core.check().add_done_callback(lambda f: self.checked.emit(f.result()))

    def purchase(self, hwnd):          # call on the UI thread
        self.core.start_purchase(hwnd).add_done_callback(lambda f: self.purchased.emit(f.result()))


def page_width(available_px, zoom=100):
    """Width of a rendered page so that the whole page fits the pane (at most 820 px at 100 % zoom)."""
    return int(min(820, max(300, available_px - 40)) * zoom / 100)


class PdfPane(QWidget):
    """Scrollable, zoomable view of a rendered PDF (falls back to HTML if Qt PDF is missing)."""

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.zoom = 100
        for text, delta, tip in (("−", -15, tr("Zoom out")), ("+", 15, tr("Zoom in"))):
            b = QPushButton(text); b.setToolTip(tip); b.setFixedWidth(40); b.clicked.connect(lambda _=False, d=delta: self.set_zoom(self.zoom + d)); bar.addWidget(b)
        self.zoom_label = QLabel("100%"); bar.addWidget(self.zoom_label); bar.addStretch()
        self.info = QLabel(""); bar.addWidget(self.info)
        outer.addLayout(bar)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.holder = QWidget(); self.col = QVBoxLayout(self.holder); self.col.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.holder); outer.addWidget(self.scroll, 1)
        self.pdf_path = None
        self.html = QTextBrowser(); self.html.hide(); outer.addWidget(self.html, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.pdf_path:
            QTimer.singleShot(150, self._refit)

    def _refit(self):
        if self.pdf_path and page_width(self.scroll.width(), self.zoom) != getattr(self, "_last_w", None):
            self.show_pdf(self.pdf_path)

    def clear(self):
        self.pdf_path = None
        while self.col.count():
            w = self.col.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.info.setText("")

    def set_zoom(self, value):
        self.zoom = max(50, min(220, value)); self.zoom_label.setText(f"{self.zoom}%")
        if self.pdf_path:
            self.show_pdf(self.pdf_path)

    def show_pdf(self, path):
        self.pdf_path = path
        self._last_w = page_width(self.scroll.width(), self.zoom)
        images = pdfview.render_pdf(path, int(self._last_w * self.devicePixelRatioF()), max_pages=10)
        while self.col.count():
            w = self.col.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not images:
            self.info.setText(tr("Preview unavailable"))
            return False
        for img in images:
            lab = QLabel()
            pm = QPixmap.fromImage(img); pm.setDevicePixelRatio(self.devicePixelRatioF())
            lab.setPixmap(pm); lab.setStyleSheet("background:white;border:1px solid #C9D0DE;")
            self.col.addWidget(lab)
        self.info.setText(f"{len(images)} p.")
        return True

    def show_html(self, html):
        self.scroll.hide(); self.html.show(); self.html.setHtml(html)


SECTION_KEYS = [("summary", "Profile summary"), ("experience", "Experience"), ("internships", "Internships"), ("education", "Education"),
                ("courses", "Courses"), ("projects", "Projects"), ("publications", "Publications"), ("awards", "Awards"),
                ("volunteer", "Volunteer work"), ("memberships", "Memberships"), ("references", "References"),
                ("skills", "Skills"), ("languages", "Languages"), ("certificates", "Certificates"), ("hobbies", "Interests")]


class MainWindow(QMainWindow):
    def __init__(self, settings, store, open_profile_id=None):
        super().__init__()
        self.settings, self.store = settings, store
        self.setWindowTitle(APP_NAME)
        self.resize(1360, 880)
        self.setMinimumSize(980, 640)
        self.profile = store.load(open_profile_id) if open_profile_id else None
        self.profile = self.profile or CVProfile()
        self._building, self._dirty = False, False
        self._preview_id, self._cards, self._cols = None, {}, 0       # gallery: previewed template, its cards
        self._sidebar_open, self._sidebar_anim = True, None
        self._back_stack, self._going_back = [], False                 # pages visited before the current one (for Go back)
        self.cv_data = {key: [] for key in ORDER}      # central state: every list entry of the CV, by section
        self.iap = StoreCore(); self.bridge = StoreBridge(self.iap)
        self.bridge.checked.connect(self._on_store_checked); self.bridge.purchased.connect(self._on_purchased)
        self._pending, self._busy_count, self._recheck_on_focus = None, 0, False
        self.tmp = tempfile.TemporaryDirectory(prefix="cvstudio-")
        cache = app_data_dir() / "cache"
        self.thumb_dir = cache / f"thumbs-{__version__}-d{DESIGN_REV}"      # keyed by template design revision
        for old in cache.glob("thumbs-*") if cache.is_dir() else []:        # thumbnails of older designs are obsolete
            if old != self.thumb_dir:
                import shutil
                shutil.rmtree(old, ignore_errors=True)
        self.thumb_dir.mkdir(parents=True, exist_ok=True)
        self.thumb_queue = []
        self.preview_timer = QTimer(self); self.preview_timer.setSingleShot(True); self.preview_timer.timeout.connect(self.update_preview)
        self.detail_timer = QTimer(self); self.detail_timer.setSingleShot(True); self.detail_timer.timeout.connect(self._render_template_detail)
        self._make_shell()
        self._make_editor()
        self._make_templates()
        self._make_job_tools()
        self._make_settings()
        self._make_about()
        self._load_profile(self.profile)
        if PREMIUM_FEATURES:
            QTimer.singleShot(1200, self.bridge.check)  # warm-up ownership check, in the background
        self.autosave = QTimer(self); self.autosave.setInterval(6000)
        self.autosave.timeout.connect(lambda: self._dirty and self.save_profile(quiet=True)); self.autosave.start()

    # ------------------------------------------------------------------ shell
    def _make_shell(self):
        root = QWidget(); shell = QHBoxLayout(root); shell.setContentsMargins(0, 0, 0, 0); shell.setSpacing(0)
        self.sidebar = sidebar = QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(SIDEBAR_W)
        side = QVBoxLayout(sidebar); side.setContentsMargins(14, 22, 14, 18)
        logo = QLabel("CV Studio"); logo.setStyleSheet("font-size:22px;font-weight:800;padding:4px 8px 18px;letter-spacing:.5px")
        side.addWidget(logo)
        self.stack = QStackedWidget()
        self.nav_buttons = []
        for i, (icon, label) in enumerate([("⌂", "Overview"), ("✎", "CV editor"), ("▦", "Templates"), ("✉", "Job tools"), ("⚙", "Settings"), ("ⓘ", "About")]):
            b = QPushButton(f"{icon}   {tr(label)}"); b.setObjectName("Nav"); b.setCheckable(True)
            b.clicked.connect(lambda _=False, idx=i: self.navigate(idx)); side.addWidget(b); self.nav_buttons.append(b)
        side.addStretch()
        note = QLabel("● " + tr("Stored on this device")); note.setStyleSheet("font-size:11px;color:#AEB9CB;padding:8px"); side.addWidget(note)
        content = QWidget(); column = QVBoxLayout(content); column.setContentsMargins(0, 0, 0, 0); column.setSpacing(0)
        bar = QHBoxLayout(); bar.setContentsMargins(12, 8, 12, 0)
        self.sidebar_btn = QPushButton("☰"); self.sidebar_btn.setObjectName("Burger"); self.sidebar_btn.setFixedSize(40, 34)
        self.sidebar_btn.setToolTip(tr("Toggle sidebar")); self.sidebar_btn.clicked.connect(self.toggle_sidebar)
        self.back_btn = QPushButton("←  " + tr("Go back")); self.back_btn.setObjectName("Back"); self.back_btn.setFixedHeight(34)
        self.back_btn.setToolTip(tr("Go back") + "  (Alt+Left)"); self.back_btn.setShortcut("Alt+Left"); self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setVisible(False)                                  # appears as soon as there is a page to go back to
        bar.addWidget(self.sidebar_btn); bar.addWidget(self.back_btn); bar.addStretch(); column.addLayout(bar); column.addWidget(self.stack, 1)   # the button stays visible when the sidebar is hidden
        shell.addWidget(sidebar); shell.addWidget(content, 1)
        self.stack.addWidget(self._make_home())
        self.setCentralWidget(root)

    def toggle_sidebar(self):
        """Slide the sidebar away / back. Only the sidebar width changes: the current page and all data stay as they are."""
        self._sidebar_open = not self._sidebar_open
        if self._sidebar_anim is not None:
            self._sidebar_anim.stop()
        start, end = self.sidebar.width(), (SIDEBAR_W if self._sidebar_open else 0)
        if self._sidebar_open:
            self.sidebar.setVisible(True)
        anim = QVariantAnimation(self)
        anim.setDuration(220); anim.setEasingCurve(QEasingCurve.Type.InOutCubic); anim.setStartValue(start); anim.setEndValue(end)
        anim.valueChanged.connect(lambda v: self.sidebar.setFixedWidth(max(0, int(v))))
        anim.finished.connect(lambda: self.sidebar.setVisible(self._sidebar_open))
        self._sidebar_anim = anim
        anim.start()

    def go_back(self):
        """Return to the previous page (and, for the CV editor, to the tab you were on). Data is never touched."""
        if not self._back_stack:
            return
        page, tab = self._back_stack.pop()
        self._going_back = True
        try:
            self.navigate(page)
            if page == 1:
                self.editor_tabs.setCurrentIndex(tab)
        finally:
            self._going_back = False
            self._update_back()

    def _update_back(self):
        if hasattr(self, "back_btn"):
            self.back_btn.setVisible(bool(self._back_stack))

    def navigate(self, index):
        if index >= self.stack.count():
            return
        if self.stack.currentIndex() == 1 and index != 1:
            self.save_profile(quiet=True)
        if not self._going_back and index != self.stack.currentIndex():          # remember where we came from
            tab = self.editor_tabs.currentIndex() if hasattr(self, "editor_tabs") else 0
            self._back_stack.append((self.stack.currentIndex(), tab)); del self._back_stack[:-30]
        self.stack.setCurrentIndex(index)
        self._update_back()
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == index)
        if index == 0:
            self.refresh_profiles()
        if index == 2:
            self._start_thumbnails(); self.refresh_template_list(); self._schedule_detail()

    def toast(self, text):
        self.status_label.setText(text)
        QTimer.singleShot(4000, lambda: self.status_label.setText(tr("Auto-save is on")))

    # ------------------------------------------------------------------ home
    def _make_home(self):
        page = QWidget(); outer = QVBoxLayout(page); outer.setContentsMargins(34, 26, 34, 26)
        title = QLabel(tr("Build a CV that feels like you")); title.setStyleSheet("font-size:28px;font-weight:800"); outer.addWidget(title)
        hero = QFrame(); hero.setObjectName("Hero"); hl = QVBoxLayout(hero); hl.setContentsMargins(28, 22, 28, 22)
        t = QLabel("Professional designs · PDF & editable Word · 100% private"); t.setStyleSheet("font-size:20px;font-weight:700"); hl.addWidget(t)
        row = QHBoxLayout()
        start = QPushButton("＋  " + tr("Create a CV")); start.setObjectName("Primary"); start.clicked.connect(self.new_profile)
        demo = QPushButton(tr("Explore sample CV")); demo.clicked.connect(self.load_sample)
        row.addWidget(start); row.addWidget(demo); row.addStretch(); hl.addLayout(row)
        outer.addWidget(hero)
        h = QLabel(tr("Your saved CVs")); h.setStyleSheet("font-size:19px;font-weight:700;margin-top:10px"); outer.addWidget(h)
        actions = QHBoxLayout()
        for text, cb, primary in ((tr("Open selected"), self.open_selected, True), (tr("Duplicate"), self.duplicate_selected, False),
                                  (tr("Rename"), self.rename_selected, False), (tr("Delete selected"), self.delete_selected, False)):
            b = QPushButton(text); b.clicked.connect(cb)
            if primary:
                b.setObjectName("Primary")
            actions.addWidget(b)
        actions.addStretch(); outer.addLayout(actions)
        self.saved_list = QListWidget(); self.saved_list.itemDoubleClicked.connect(lambda *_: self.open_selected()); outer.addWidget(self.saved_list, 1)
        h2 = QLabel(tr("Recent exports")); h2.setStyleSheet("font-size:16px;font-weight:700"); outer.addWidget(h2)
        self.history_list = QListWidget(); self.history_list.setMaximumHeight(140)
        self.history_list.itemDoubleClicked.connect(lambda it: it.data(Qt.ItemDataRole.UserRole) and QDesktopServices.openUrl(QUrl.fromLocalFile(it.data(Qt.ItemDataRole.UserRole))))
        outer.addWidget(self.history_list)
        self.refresh_profiles()
        return page

    def refresh_profiles(self):
        if not hasattr(self, "saved_list"):
            return
        selected = self.saved_list.currentItem().data(Qt.ItemDataRole.UserRole) if self.saved_list.currentItem() else None
        self.saved_list.clear()
        rows = self.store.list_profiles()
        if not rows:
            it = QListWidgetItem(tr("No saved CVs yet.")); it.setFlags(Qt.ItemFlag.NoItemFlags); self.saved_list.addItem(it)
        for r in rows:
            it = QListWidgetItem(f"{r['title']}    ·    {r['updated_at']}"); it.setData(Qt.ItemDataRole.UserRole, r["id"]); self.saved_list.addItem(it)
            if r["id"] == selected:
                self.saved_list.setCurrentItem(it)
        self.history_list.clear()
        history = self.store.history()[:8]
        if not history:
            it = QListWidgetItem(tr("No exports yet.")); it.setFlags(Qt.ItemFlag.NoItemFlags); self.history_list.addItem(it)
        for r in history:
            it = QListWidgetItem(f"{Path(r['file_path']).name}    ·    {r['created_at']}"); it.setToolTip(r["file_path"]); it.setData(Qt.ItemDataRole.UserRole, r["file_path"]); self.history_list.addItem(it)

    def _selected_id(self):
        it = self.saved_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def open_selected(self):
        pid = self._selected_id()
        profile = self.store.load(pid) if pid else None
        if profile:
            self._load_profile(profile); self.navigate(1)

    def duplicate_selected(self):
        pid = self._selected_id()
        if pid and self.store.duplicate(pid, " (" + tr("copy") + ")"):
            self.refresh_profiles()

    def rename_selected(self):
        pid = self._selected_id()
        if not pid:
            return
        current = self.store.load(pid)
        name, ok = QInputDialog.getText(self, tr("Rename"), tr("CV name"), text=current.title if current else "")
        if ok and name.strip():
            self.store.rename(pid, name)
            if pid == self.profile.id:
                self.profile.title = name.strip(); self.inputs["title"].setText(name.strip())
            self.refresh_profiles()

    def delete_selected(self):
        pid = self._selected_id()
        if pid and QMessageBox.question(self, tr("Delete CV"), tr("Delete this saved CV and its export history?")) == YES:
            self.store.backup()
            self.store.delete(pid); self.refresh_profiles()

    def new_profile(self):
        self._load_profile(CVProfile()); self.editor_tabs.setCurrentIndex(0); self.navigate(1)

    def load_sample(self):
        self._load_profile(sample_profile()); self.navigate(1); self.open_preview()

    # ------------------------------------------------------------------ editor
    def _make_editor(self):
        page = QWidget(); root = QVBoxLayout(page); root.setContentsMargins(26, 22, 26, 22)
        top = QHBoxLayout(); title = QLabel(tr("CV editor")); title.setStyleSheet("font-size:26px;font-weight:800"); top.addWidget(title); top.addStretch()
        self.status_label = QLabel(tr("Auto-save is on")); top.addWidget(self.status_label)
        b = QPushButton(tr("Save now")); b.clicked.connect(lambda: self.save_profile()); top.addWidget(b)
        p = QPushButton(tr("Preview & export")); p.setObjectName("Primary"); p.clicked.connect(self.open_preview); top.addWidget(p)
        root.addLayout(top)
        self.editor_tabs = QTabWidget(); root.addWidget(self.editor_tabs, 1)
        self._build_profile_tab(); self._build_collection_tabs(); self._build_sections_tab()
        pv = QWidget(); pl = QVBoxLayout(pv)
        bar = QHBoxLayout()
        self.template_chip = QLabel(""); bar.addWidget(self.template_chip)
        change = QPushButton(tr("Templates")); change.clicked.connect(lambda: self.navigate(2)); bar.addWidget(change)
        bar.addStretch()
        refresh = QPushButton("⟳"); refresh.setToolTip("Refresh"); refresh.clicked.connect(self.update_preview); bar.addWidget(refresh)
        self.export_btns = []
        for text, kind in ((tr("Export Word"), "docx"), (tr("Export PDF"), "pdf")):
            e = QPushButton(text); e.clicked.connect(lambda _=False, k=kind: self.export_cv(k)); self.export_btns.append(e)
            if kind == "pdf":
                e.setObjectName("Primary")
            bar.addWidget(e)
        pl.addLayout(bar)
        self.preview = PdfPane(); pl.addWidget(self.preview, 1)
        self.editor_tabs.addTab(pv, tr("Preview & export"))
        self.editor_tabs.currentChanged.connect(lambda i: i == self.editor_tabs.count() - 1 and self.preview_timer.start(50))
        self.stack.addWidget(page)

    def _build_profile_tab(self):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        body = QWidget(); form = QFormLayout(body); form.setContentsMargins(24, 22, 24, 22); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.inputs = {}
        for key, label in (("title", "CV name"), ("full_name", "Full name"), ("headline", "Professional headline"), ("email", "Email"),
                           ("phone", "Phone"), ("location", "City / country"), ("address", "Address")):
            e = QLineEdit(); e.setPlaceholderText(tr(label)); e.textChanged.connect(self._touch); self.inputs[key] = e; form.addRow(tr(label), e)
        self.summary_input = QTextEdit(); self.summary_input.setFixedHeight(130); self.summary_input.textChanged.connect(self._touch)
        self.summary_input.setPlaceholderText("A short introduction focused on the value you bring.")
        form.addRow(tr("Professional summary"), self.summary_input)
        row = QHBoxLayout(); self.photo_label = QLabel("—")
        pick = QPushButton(tr("Choose photo…")); pick.clicked.connect(self.choose_photo)
        rm = QPushButton(tr("Remove")); rm.clicked.connect(lambda: self._set_photo(""))
        row.addWidget(self.photo_label, 1); row.addWidget(pick); row.addWidget(rm); form.addRow(tr("Profile photo"), row)
        scroll.setWidget(body); self.editor_tabs.addTab(scroll, tr("Personal details"))

    def _build_collection_tabs(self):
        self.collections = {}
        for key in ORDER:
            panel = SectionPanel(SPECS[key], self.cv_data[key], on_change=self._touch)
            self.collections[key] = panel; self.editor_tabs.addTab(panel, tr(SPECS[key].title))
        self.editor_tabs.setUsesScrollButtons(True); self.editor_tabs.setElideMode(Qt.TextElideMode.ElideNone)

    def _build_sections_tab(self):
        page = QWidget(); l = QVBoxLayout(page)
        hint = QLabel(tr("Tick the sections to show in your CV. Use the arrows to change their order (applies to the main column).")); hint.setWordWrap(True); l.addWidget(hint)
        self.section_list = QListWidget(); self.section_list.itemChanged.connect(lambda *_: self._touch()); l.addWidget(self.section_list, 1)
        row = QHBoxLayout()
        for text, d in (("↑  " + tr("Move up"), -1), ("↓  " + tr("Move down"), 1)):
            b = QPushButton(text); b.clicked.connect(lambda _=False, dd=d: self._move_section(dd)); row.addWidget(b)
        row.addStretch(); l.addLayout(row)
        self.editor_tabs.addTab(page, tr("Sections"))

    def _move_section(self, d):
        r = self.section_list.currentRow(); t = r + d
        if 0 <= r < self.section_list.count() and 0 <= t < self.section_list.count():
            it = self.section_list.takeItem(r); self.section_list.insertItem(t, it); self.section_list.setCurrentRow(t); self._touch()

    def _fill_sections(self, profile):
        self.section_list.blockSignals(True); self.section_list.clear()
        names = dict(SECTION_KEYS)
        order = [k for k in profile.section_order if k in names] + [k for k, _ in SECTION_KEYS if k not in profile.section_order]
        for k in order:
            it = QListWidgetItem(tr(names[k])); it.setData(Qt.ItemDataRole.UserRole, k)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Unchecked if k in profile.hidden_sections else Qt.CheckState.Checked)
            self.section_list.addItem(it)
        self.section_list.blockSignals(False)

    def _touch(self, *_):
        if not self._building:
            self._dirty = True

    def choose_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Choose photo…"), "", "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self._set_photo(path)

    def _set_photo(self, path):
        self.profile.photo_path = path or ""; self.photo_label.setText(Path(path).name if path else "—"); self._touch()

    def _collect(self):
        for k, w in self.inputs.items():
            setattr(self.profile, k, w.text().strip())
        self.profile.summary = self.summary_input.toPlainText().strip()
        for k in ORDER:
            setattr(self.profile, k, [dict(r) for r in self.cv_data[k]])
        keys = [self.section_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.section_list.count())]
        self.profile.section_order = keys
        self.profile.hidden_sections = [self.section_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.section_list.count())
                                        if self.section_list.item(i).checkState() != Qt.CheckState.Checked]
        self.profile.font_size = self.font_spin.value()
        self.profile.page_size = "A4" if self.page_combo.currentIndex() == 0 else "US Letter"
        self.profile.show_photo = self.photo_check.isChecked()
        self.profile.target_role = self.target_role_input.text().strip()
        self.profile.target_company = self.target_company_input.text().strip()
        self.profile.hiring_manager = self.hiring_manager_input.text().strip()
        self.profile.job_description = self.job_description_input.toPlainText().strip()
        self.profile.why_role = self.why_role_input.toPlainText().strip()
        self.profile.relevant_contribution = self.contribution_input.toPlainText().strip()
        self.profile.cover_letter_text = self.cover_letter_input.toPlainText().strip()
        return self.profile

    def _load_profile(self, profile):
        self._building = True; self.profile = profile
        for k, w in self.inputs.items():
            w.setText(getattr(profile, k, "") or "")
        self.summary_input.setPlainText(profile.summary)
        for k, ed in self.collections.items():
            ed.set_rows(list(getattr(profile, k, []) or []))
        self._fill_sections(profile)
        self.photo_label.setText(Path(profile.photo_path).name if profile.photo_path else "—")
        self.font_spin.setValue(profile.font_size)
        self.page_combo.setCurrentIndex(0 if profile.page_size == "A4" else 1)
        self.photo_check.setChecked(profile.show_photo)
        self.accent_button.setText(profile.accent_color or get_template(profile.template_id).color)
        self.target_role_input.setText(profile.target_role); self.target_company_input.setText(profile.target_company)
        self.hiring_manager_input.setText(profile.hiring_manager); self.job_description_input.setPlainText(profile.job_description)
        self.why_role_input.setPlainText(profile.why_role); self.contribution_input.setPlainText(profile.relevant_contribution)
        self.cover_letter_input.setPlainText(profile.cover_letter_text)
        self._building = False; self._dirty = False
        self._preview_id = None             # opening a CV never auto-selects a template in the gallery
        self._update_chip()

    def _update_chip(self):
        t = get_template(self.profile.template_id)
        self.template_chip.setText(f"▦  {t.name} · {t.category}")

    def save_profile(self, quiet=False):
        if self._building:
            return
        try:
            self._collect(); self.store.save(self.profile); self._dirty = False
            if not quiet:
                self.toast(tr("Saved"))
        except Exception as exc:  # never crash the app on a failed autosave
            self.toast(f"Could not save: {exc}")
        self.refresh_profiles()

    # ------------------------------------------------------------------ preview + export
    def _tmp_pdf(self, name):
        return Path(self.tmp.name) / name

    def update_preview(self):
        if self._building:
            return
        self._collect(); self._update_chip()
        try:
            out = export_pdf(self.profile, self._tmp_pdf("preview.pdf"))
            if not self.preview.show_pdf(out):
                self.preview.show_html(render_html(self.profile))
        except Exception as exc:
            self.preview.info.setText(str(exc))

    def open_preview(self):
        self.save_profile(quiet=True); self.navigate(1); self.editor_tabs.setCurrentIndex(self.editor_tabs.count() - 1)
        self.preview_timer.start(50)

    # ---- Premium gating: free templates export immediately; Premium ones need the Store add-on ----------
    def export_cv(self, kind):
        self.save_profile(quiet=True)
        t = get_template(self.profile.template_id)
        if not PREMIUM_FEATURES or t.free or self.iap.state == State.OWNED:
            self._export_now(kind)
        else:
            self._require_premium(lambda: self._export_now(kind))

    def _busy(self, on, text=""):
        self._busy_count = max(0, self._busy_count + (1 if on else -1))
        if on and self._busy_count == 1:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        elif not on and self._busy_count == 0:
            QApplication.restoreOverrideCursor()
        if text:
            self.toast(text)
        for b in getattr(self, "export_btns", []):
            b.setEnabled(self._busy_count == 0)

    def _require_premium(self, then):
        """Check ownership in the background; owned -> `then()`, not owned -> Microsoft payment window."""
        self._pending = then
        self._busy(True, tr("Checking your purchase…"))
        self._awaiting = True
        self.bridge.check()

    def _on_store_checked(self, result):
        self.iap.state = result.state
        if result.store_id: self.iap.store_id = result.store_id
        if result.price: self.iap.price = result.price
        self.refresh_template_list(); self._render_template_detail_labels()
        if not getattr(self, "_awaiting", False):
            return                                      # warm-up check only
        self._awaiting = False; self._busy(False)
        if result.state == State.OWNED:
            self._run_pending()
        elif result.state == State.NOT_OWNED:
            self._busy(True, tr("Opening Microsoft Store…"))
            self.bridge.purchase(int(self.winId()))      # must start on the UI thread; returns immediately
        else:
            self._pending = None
            QMessageBox.information(self, tr("Premium templates"), tr("We could not verify your purchase.") + "\n\n" + tr("Premium templates need the Microsoft Store version of CV Studio and an internet connection. The 5 free templates always work.") + (f"\n\n({result.detail})" if result.detail else ""))

    def _on_purchased(self, outcome):
        status, detail = outcome
        self._busy(False)
        if status in (Purchase.SUCCEEDED, Purchase.ALREADY_OWNED):
            self.iap.state = State.OWNED; self.refresh_template_list(); self._render_template_detail_labels()
            self.toast("✓ " + tr("Premium unlocked")); self._run_pending()
        elif status == Purchase.CANCELLED:
            self._pending = None; self.toast(tr("Purchase cancelled"))
        else:   # the in-app window could not be shown (or network/server error): offer the Store page instead
            if QMessageBox.question(self, tr("Premium templates"), tr("The purchase window could not be opened.") + f"\n({detail})\n\n" + tr("Open the Microsoft Store page instead?")) == YES:
                self._recheck_on_focus = True
                QDesktopServices.openUrl(QUrl(store_page_url(self.iap.store_id)))
            else:
                self._pending = None

    def _run_pending(self):
        action, self._pending = self._pending, None
        if action:
            action()

    def changeEvent(self, event):
        super().changeEvent(event)
        if getattr(self, "_recheck_on_focus", False) and self.isActiveWindow() and self._pending:
            self._recheck_on_focus = False       # user came back from the Store: verify silently, then continue
            self._awaiting = True; self._busy(True, tr("Checking your purchase…")); self.bridge.check()

    def _export_now(self, kind):
        issues = validate_profile(self.profile)
        if issues and QMessageBox.question(self, tr("Check your CV"), "\n".join(issues) + "\n\n" + tr("Continue with export?")) != YES:
            return
        stem = (self.profile.full_name or self.profile.title or "CV").strip().replace(" ", "_")
        start = Path(self.settings.get("last_export_dir") or Path.home() / "Documents")
        dlg = QFileDialog(self, tr("Export PDF") if kind == "pdf" else tr("Export Word"), str(start / f"{stem}.{kind}"))
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setNameFilter("PDF (*.pdf)" if kind == "pdf" else "Word (*.docx)"); dlg.setDefaultSuffix(kind)
        if not dlg.exec():
            return
        target = Path(dlg.selectedFiles()[0])
        if target.suffix.lower() != "." + kind:
            target = target.with_suffix("." + kind)
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            out = safe_export(export_pdf if kind == "pdf" else export_docx, self.profile, target)
        except PermissionError:
            QMessageBox.critical(self, tr("Export failed"), f"{target}\n\nThe file is open in another program or the folder is read-only. Close the file or choose another folder.")
            return
        except Exception as exc:
            QMessageBox.critical(self, tr("Export failed"), str(exc)); return
        finally:
            QApplication.restoreOverrideCursor()
        self.settings.set("last_export_dir", str(target.parent)); self.store.record_export(self.profile.id, str(out)); self.refresh_profiles()
        self.toast(f"{kind.upper()} ✓")
        if QMessageBox.question(self, tr("Export complete"), f"{out}\n\n{tr('Open it now?')}") == YES:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))

    # ------------------------------------------------------------------ template gallery
    def _make_templates(self):
        page = QWidget(); layout = QHBoxLayout(page); layout.setContentsMargins(26, 22, 26, 22)
        left = QVBoxLayout()
        title = QLabel(tr("Choose your layout")); title.setStyleSheet("font-size:24px;font-weight:800"); left.addWidget(title)
        row = QHBoxLayout()
        self.template_search = QLineEdit(); self.template_search.setPlaceholderText(tr("Search templates…")); self.template_search.setClearButtonEnabled(True)
        self.template_search.textChanged.connect(self.refresh_template_list); row.addWidget(self.template_search, 1)
        self.template_filter = QComboBox()
        self._filter_keys = ["all", "fav", "ats"] + (["free", "premium"] if PREMIUM_FEATURES else []) + ["cat:" + c for c in CATEGORIES]   # exactly five categories
        labels = {"all": tr("All categories"), "fav": tr("Favorites"), "ats": tr("ATS-friendly"), "free": tr("Free"), "premium": tr("Premium")}
        self.template_filter.addItems([labels.get(k, k[4:]) for k in self._filter_keys])
        self.template_filter.currentIndexChanged.connect(self.refresh_template_list); row.addWidget(self.template_filter)
        left.addLayout(row)
        self.card_scroll = CardScroll(self._relayout_cards)
        self.card_host = QWidget(); self.card_grid = QGridLayout(self.card_host)
        self.card_grid.setContentsMargins(4, 6, 4, 6); self.card_grid.setSpacing(14)
        self.card_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.card_scroll.setWidget(self.card_host); left.addWidget(self.card_scroll, 1)
        self.thumb_progress = QLabel(""); left.addWidget(self.thumb_progress)
        right = QVBoxLayout()
        self.template_name = QLabel(""); self.template_name.setStyleSheet("font-size:20px;font-weight:800"); right.addWidget(self.template_name)
        self.template_desc = QLabel(""); self.template_desc.setWordWrap(True); right.addWidget(self.template_desc)
        self.detail = PdfPane(); right.addWidget(self.detail, 1)
        if PREMIUM_FEATURES:
            self.unlock_btn = QPushButton(""); self.unlock_btn.clicked.connect(lambda: self._require_premium(lambda: self.toast("✓ " + tr("Premium unlocked")))); self.unlock_btn.hide()
            right.addWidget(self.unlock_btn)
        layout.addLayout(left, 5); layout.addLayout(right, 4)
        self.stack.addWidget(page)
        self.refresh_template_list()

    def _thumb_file(self, tid):
        return self.thumb_dir / f"{tid}.png"

    def _card_pixmap(self, tid):
        f = self._thumb_file(tid)
        pm = QPixmap(str(f)) if f.is_file() else QPixmap()
        if pm.isNull():                                   # thumbnail not rendered yet: accent-coloured placeholder
            pm = QPixmap(THUMB_W, THUMB_H); pm.fill(QColor(get_template(tid).color)); return pm
        return pm.scaled(QSize(THUMB_W, THUMB_H), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def _start_thumbnails(self):
        self.thumb_queue = [t.id for t in TEMPLATES if not self._thumb_file(t.id).is_file()]
        if self.thumb_queue:
            QTimer.singleShot(30, self._thumb_step)

    def _thumb_step(self):
        if not self.thumb_queue:
            self.thumb_progress.setText(""); return
        tid = self.thumb_queue.pop(0)
        try:
            p = sample_profile(); p.template_id = tid; p.accent_color = ""; p.show_photo = True
            out = export_pdf(p, self._tmp_pdf(f"thumb-{tid}.pdf"))
            imgs = pdfview.render_pdf(out, 420, max_pages=1)      # rendered from the real PDF, so the card shows exactly what exports
            if imgs:
                imgs[0].save(str(self._thumb_file(tid)), "PNG")
        except Exception:
            pass
        done = len(TEMPLATES) - len(self.thumb_queue)
        self.thumb_progress.setText(f"⏳ {done}/{len(TEMPLATES)}" if self.thumb_queue else "")
        card = self._cards.get(tid)
        if card is not None:
            card.set_thumb(self._card_pixmap(tid))
        QTimer.singleShot(10, self._thumb_step)

    def _visible_templates(self):
        idx = self.template_filter.currentIndex()
        key = self._filter_keys[idx] if 0 <= idx < len(self._filter_keys) else "all"
        q = self.template_search.text().strip().lower()
        favs = set(self.settings.get("favorites"))
        out = []
        for t in TEMPLATES:
            if key == "fav" and t.id not in favs: continue
            if key == "ats" and not t.ats_friendly: continue
            if key == "free" and not t.free: continue
            if key == "premium" and t.free: continue
            if key.startswith("cat:") and t.category != key[4:]: continue
            if q and q not in f"{t.name} {t.category} {t.layout} {t.description}".lower(): continue
            out.append(t)
        return out

    def refresh_template_list(self, *_):
        """Rebuild the cards (filter, search, favourites, highlight). Nothing is selected unless the user chose it."""
        if not hasattr(self, "card_scroll"):
            return
        favs = set(self.settings.get("favorites"))
        chosen = self.profile.template_id if getattr(self.profile, "template_chosen", False) else None
        while self.card_grid.count():
            w = self.card_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._cards = {}
        for t in self._visible_templates():
            badge = (" · " + (tr("Free") if t.free else ("🔓 " + tr("Premium") if self.iap.state == State.OWNED else "🔒 " + tr("Premium")))) if PREMIUM_FEATURES else ""
            self._cards[t.id] = TemplateCard(t, self._card_pixmap(t.id), t.id == chosen, t.id in favs, t.id == self._preview_id, t.category + badge,
                                             self._preview_template, self.choose_template, self.toggle_favorite)
        if not self._cards:
            empty = QLabel(tr("No templates match your search.")); empty.setStyleSheet("padding:30px"); self.card_grid.addWidget(empty, 0, 0)
        self._cols = 0
        self._relayout_cards()

    def _relayout_cards(self):
        if not hasattr(self, "card_scroll") or not self._cards:
            return
        cols = max(1, (self.card_scroll.viewport().width() - 8) // (CARD_W + 14))
        if cols == self._cols and self.card_grid.count():
            return
        self._cols = cols
        while self.card_grid.count():
            self.card_grid.takeAt(0)
        for i, card in enumerate(self._cards.values()):
            self.card_grid.addWidget(card, i // cols, i % cols)
        self.card_grid.setRowStretch(len(self._cards) // cols + 1, 1)

    def _preview_template(self, tid):
        """Click on a card: show a large preview of that template with the user's own CV data. Does not apply it."""
        self._preview_id = tid
        for cid, card in self._cards.items():
            card.set_previewed(cid == tid)
        self._schedule_detail()

    def _current_template(self):
        return get_template(self._preview_id) if self._preview_id else None

    def _schedule_detail(self):
        self.detail_timer.start(180)

    def _render_template_detail(self):
        t = self._current_template()
        if not t:
            self.template_name.setText(tr("Select a template to preview"))
            self.template_desc.setText(tr("Click a template to see it here with your own CV information."))
            self.detail.clear(); self._render_template_detail_labels()
            return
        self.template_name.setText(f"{t.name}  ·  {t.category}")
        details = f"{t.description}\n" + ("✓ ATS-friendly single column" if t.ats_friendly else "Two-column / decorative design")
        if PREMIUM_FEATURES:
            details += "  ·  " + (tr("Free") if t.free else tr("Premium"))
        self.template_desc.setText(details)
        self._render_template_detail_labels()
        self._collect()
        base = self.profile if (self.profile.full_name or self.profile.experience) else sample_profile()
        import copy
        p = copy.deepcopy(base); p.template_id = t.id; p.accent_color = ""
        try:
            out = export_pdf(p, self._tmp_pdf("detail.pdf"))
            self.detail.show_pdf(out)
        except Exception as exc:
            self.detail.info.setText(str(exc))

    def _render_template_detail_labels(self):
        t = self._current_template() if hasattr(self, "card_scroll") else None
        if not PREMIUM_FEATURES or not t or not hasattr(self, "unlock_btn"):
            if hasattr(self, "unlock_btn"):
                self.unlock_btn.hide()
            return
        owned = self.iap.state == State.OWNED
        self.unlock_btn.setVisible(t.premium and not owned)
        price = f" — {self.iap.price}" if self.iap.price else ""
        self.unlock_btn.setText("🔓  " + tr("Unlock all 25 Premium templates") + price)

    def toggle_favorite(self, tid=None):
        """ADD TO FAVORITES / remove: one template at a time, saved in settings.json (no duplicates)."""
        tid = tid or self._preview_id
        if tid:
            self.settings.toggle_favorite(tid); self.refresh_template_list()

    def choose_template(self, tid=None):
        """USE THIS TEMPLATE: apply this card's template to the existing CV, keep all data, save, highlight, show the preview."""
        t = get_template(tid) if tid else self._current_template()
        if not t:
            self.toast(tr("Select a template first"))
            return
        self._collect()
        self.profile.template_id = t.id
        self.profile.accent_color = t.color
        self.profile.template_chosen = True
        self.accent_button.setText(t.color)
        self._update_chip()
        self.save_profile(quiet=True)
        self.refresh_template_list()                       # highlights the selected card
        self.toast(f"{t.name} ✓")
        self.open_preview()

    # ------------------------------------------------------------------ job tools
    def _make_job_tools(self):
        page=QWidget();outer=QVBoxLayout(page);outer.setContentsMargins(28,24,28,24)
        heading=QLabel("Job application tools");heading.setStyleSheet("font-size:25px;font-weight:800");outer.addWidget(heading)
        intro=QLabel("Tailor your CV wording and prepare a cover letter. Everything runs locally on this device.");intro.setStyleSheet("color:#68758A;font-size:14px");outer.addWidget(intro)
        targets=QGroupBox("Target role");form=QFormLayout(targets)
        self.target_role_input=QLineEdit();self.target_role_input.setPlaceholderText("e.g. Junior Python Developer")
        self.target_company_input=QLineEdit();self.target_company_input.setPlaceholderText("Company name")
        self.hiring_manager_input=QLineEdit();self.hiring_manager_input.setPlaceholderText("Optional; otherwise the letter uses ‘Hiring Team’")
        form.addRow("Job title",self.target_role_input);form.addRow("Company",self.target_company_input);form.addRow("Greeting name",self.hiring_manager_input);outer.addWidget(targets)
        self.job_tabs=QTabWidget();outer.addWidget(self.job_tabs,1)
        match=QWidget();ml=QVBoxLayout(match);ml.addWidget(QLabel("Paste the job description. The comparison checks wording overlap in your CV."))
        self.job_description_input=QTextEdit();self.job_description_input.setPlaceholderText("Paste the job description here…");ml.addWidget(self.job_description_input,2)
        analyze=QPushButton("Review job match");analyze.setObjectName("Primary");analyze.clicked.connect(self.review_job_match);ml.addWidget(analyze)
        from PySide6.QtWidgets import QTextBrowser
        self.match_report=QTextBrowser();self.match_report.setMinimumHeight(175);ml.addWidget(self.match_report,2);self.job_tabs.addTab(match,"Job match review")
        letter=QWidget();ll=QVBoxLayout(letter);letter_hint=QLabel("Generate a factual starter from your CV, then edit it in your own voice.");letter_hint.setStyleSheet("color:#68758A");ll.addWidget(letter_hint)
        why_form=QFormLayout();self.why_role_input=QTextEdit();self.why_role_input.setPlaceholderText("What specifically interests you about this role or company?");self.why_role_input.setFixedHeight(75)
        self.contribution_input=QTextEdit();self.contribution_input.setPlaceholderText("Which relevant contribution can you support with a real example?");self.contribution_input.setFixedHeight(75)
        why_form.addRow("Why this role",self.why_role_input);why_form.addRow("Relevant contribution",self.contribution_input);ll.addLayout(why_form)
        letter_actions=QHBoxLayout();draft=QPushButton("Create / refresh draft");draft.setObjectName("Primary");draft.clicked.connect(self.make_letter_draft);save=QPushButton("Save draft");save.clicked.connect(self.save_letter_draft);export=QPushButton("Export letter…");export.clicked.connect(self.export_letter_dialog)
        letter_actions.addWidget(draft);letter_actions.addWidget(save);letter_actions.addWidget(export);letter_actions.addStretch();ll.addLayout(letter_actions)
        self.cover_letter_input=QTextEdit();self.cover_letter_input.setPlaceholderText("Your editable cover letter will appear here…");ll.addWidget(self.cover_letter_input,1)
        self.job_tabs.addTab(letter,"Cover letter");self.stack.addWidget(page)

    def review_job_match(self):
        self._collect();self.save_profile()
        if not self.profile.job_description:
            self.match_report.setHtml("<p>Paste a job description first. Your text stays on this device.</p>");return
        result=analyze_job_match(self.profile,self.profile.job_description)
        matched=" · ".join(result["matched"]) or "No overlap found in the terms checked."
        missing=" · ".join(result["missing"]) or "No unmatched terms in this short review."
        checks=[("Name",bool(self.profile.full_name)),("Email",bool(self.profile.email)),("Summary",bool(self.profile.summary)),("Skills",bool(self.profile.skills)),("Experience or projects",bool(self.profile.experience or self.profile.projects))]
        checklist="".join(f"<li style='color:{'#237650' if ok else '#9A5B16'}'>{'✓' if ok else '○'} {label}{'' if ok else ' — consider adding it if relevant'}</li>" for label,ok in checks)
        self.match_report.setHtml(f"<h2>Wording overlap: {result['coverage']}%</h2><p>This compares terms in your CV with the pasted posting. It is not an ATS simulation or a hiring prediction.</p><b>Terms found</b><p>{matched}</p><b>Terms not found</b><p>{missing}</p><p>Only add missing terms when they accurately describe your experience.</p><h3>Before you send it</h3><ul>{checklist}</ul>")

    def make_letter_draft(self):
        self._collect()
        self.cover_letter_input.setPlainText(draft_cover_letter(self.profile,self.profile.target_role,self.profile.target_company,self.profile.hiring_manager,self.profile.why_role,self.profile.relevant_contribution))
        self._collect();self.save_profile()

    def save_letter_draft(self):
        self._collect();self.save_profile();QMessageBox.information(self,"Draft saved","The cover-letter draft is saved with this CV on your device.")

    def export_letter_dialog(self):
        self._collect();text=self.profile.cover_letter_text
        if not text:
            QMessageBox.information(self,"No letter yet","Create or write a cover letter before exporting.");return
        self.save_profile()
        default=(self.profile.full_name or "Cover_Letter").replace(" ","_")+"_Cover_Letter.pdf"
        path,selected_filter=QFileDialog.getSaveFileName(self,"Export cover letter",str(Path.home()/default),"PDF document (*.pdf);;Word document (*.docx)")
        if not path:return
        try:
            output=export_cover_letter_docx(self.profile,text,path) if "docx" in selected_filter.lower() or path.lower().endswith(".docx") else export_cover_letter_pdf(self.profile,text,path)
            self.store.record_export(self.profile.id,str(output));self.refresh_profiles()
            if QMessageBox.question(self,"Export complete",f"Saved {output.suffix[1:].upper()}:\n{output}\n\nOpen it now?")==QMessageBox.Yes:QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))
        except Exception as exc:QMessageBox.critical(self,"Export failed",f"The cover letter could not be created.\n\n{exc}")


    # ------------------------------------------------------------------ settings / about
    def _make_settings(self):
        page = QWidget(); outer = QVBoxLayout(page); outer.setContentsMargins(30, 25, 30, 25)
        h = QLabel(tr("Settings")); h.setStyleSheet("font-size:25px;font-weight:800"); outer.addWidget(h)
        look = QGroupBox(tr("Appearance")); f = QFormLayout(look)
        self.theme_combo = QComboBox()
        for code, label in (("light", "Light"), ("dark", "Dark"), ("system", "Follow system")):
            self.theme_combo.addItem(tr(label), code)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.settings.get("theme"))))
        self.theme_combo.currentIndexChanged.connect(self.change_theme); f.addRow(tr("Appearance"), self.theme_combo)
        self.lang_combo = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.setCurrentIndex(max(0, self.lang_combo.findData(i18n.current())))
        self.lang_combo.currentIndexChanged.connect(self.change_language); f.addRow(tr("Language"), self.lang_combo)
        outer.addWidget(look)
        doc = QGroupBox("Document"); g = QFormLayout(doc)
        self.accent_button = QPushButton("#"); self.accent_button.clicked.connect(self.choose_color); g.addRow(tr("Accent colour"), self.accent_button)
        self.font_spin = QSpinBox(); self.font_spin.setRange(9, 13); self.font_spin.setSuffix(" pt"); self.font_spin.valueChanged.connect(self._touch); g.addRow(tr("Base font size"), self.font_spin)
        self.page_combo = QComboBox(); self.page_combo.addItems(["A4", "US Letter"]); self.page_combo.currentIndexChanged.connect(self._touch); g.addRow(tr("Page size"), self.page_combo)
        self.photo_check = QCheckBox("Show photo when the template supports it"); self.photo_check.stateChanged.connect(self._touch); g.addRow("", self.photo_check)
        outer.addWidget(doc)
        data = QGroupBox(tr("Your data")); d = QVBoxLayout(data)
        d.addWidget(QLabel(tr("CV Studio stores your CVs only on this device. No account, no cloud, no analytics, no network calls.")))
        row = QHBoxLayout()
        o = QPushButton(tr("Open data folder")); o.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir())))); row.addWidget(o)
        bk = QPushButton(tr("Back up now")); bk.clicked.connect(lambda: self.toast(("✓ " + str(self.store.backup())) if self.store.backup() else "Backup failed")); row.addWidget(bk)
        sv = QPushButton(tr("Save a backup copy…")); sv.clicked.connect(self.save_backup_copy); row.addWidget(sv)
        ld = QPushButton(tr("Restore from backup…")); ld.clicked.connect(self.restore_backup); row.addWidget(ld)
        c = QPushButton(tr("Delete all saved CV data…")); c.clicked.connect(self.clear_all_data); row.addWidget(c); row.addStretch()
        d.addLayout(row); outer.addWidget(data); outer.addStretch()
        self.stack.addWidget(page)

    def _make_about(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(40, 40, 40, 40)
        icon = QLabel(); icon.setPixmap(QIcon(str(asset_root() / "cvstudio" / "assets" / "cv-studio.svg")).pixmap(72, 72)); l.addWidget(icon)
        t = QLabel(APP_NAME); t.setStyleSheet("font-size:30px;font-weight:800"); l.addWidget(t)
        l.addWidget(QLabel(f"Version {__version__}"))
        txt = QLabel("Create professional CVs and export them as PDF or editable Word documents.\n\n"
                     "Built with Qt for Python (PySide6), ReportLab, python-docx and Pillow.\n"
                     "Fonts: Carlito and Caladea (SIL Open Font License), DejaVu Sans Mono (free licence).\n"
                     "See NOTICE.md for full third-party licence information.\n\n"
                     "Your data never leaves this device.")
        txt.setWordWrap(True); l.addWidget(txt); l.addStretch()
        self.stack.addWidget(page)

    def choose_color(self):
        c = QColorDialog.getColor(QColor(self.profile.accent_color or get_template(self.profile.template_id).color), self)
        if c.isValid():
            self.profile.accent_color = c.name().upper(); self.accent_button.setText(c.name().upper()); self._touch()

    def change_theme(self, *_):
        mode = self.theme_combo.currentData(); self.settings.set("theme", mode); apply_theme(mode)

    def change_language(self, *_):
        code = self.lang_combo.currentData()
        if code == i18n.current():
            return
        self.save_profile(quiet=True)
        self.settings.set("language", code); i18n.set_language(code)
        app = QApplication.instance(); app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight)
        new = MainWindow(self.settings, self.store, self.profile.id)
        new.show(); new.navigate(4); app._cv_main = new
        self.autosave.stop(); self.close()

    def save_backup_copy(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("Save a backup copy…"), str(Path.home() / "Documents" / "CVStudio-backup.cvbackup"), "CV Studio backup (*.cvbackup)")
        if path:
            try:
                self.store.backup_to(path); self.toast("✓ " + path)
            except Exception as exc:
                QMessageBox.critical(self, tr("Export failed"), str(exc))

    def restore_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Restore from backup…"), str(Path.home() / "Documents"), "CV Studio backup (*.cvbackup);;All files (*)")
        if path:
            try:
                n = self.store.restore_from(path); self.refresh_profiles(); self.toast(f"✓ {n} CV")
            except Exception as exc:
                QMessageBox.critical(self, tr("Export failed"), f"This does not look like a CV Studio backup.\n\n{exc}")

    def clear_all_data(self):
        if QMessageBox.question(self, tr("Delete all saved CV data…"), "This deletes all saved CVs and export history from this device. Exported files are not touched. Continue?") == YES:
            self.store.backup(); self.store.clear_all(); self.refresh_profiles()

    def closeEvent(self, event):
        try:
            if self._dirty:
                self.save_profile(quiet=True)
            self.store.backup()
            self.iap.shutdown()
            self.tmp.cleanup()
        except Exception:
            pass
        event.accept()



def apply_theme(mode: str) -> None:
    app = QApplication.instance()
    app.setStyleSheet(theme.qss(theme.resolve(mode, app)))


def run():
    settings = Settings()
    i18n.set_language(settings.get("language"))
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setOrganizationName(APP_NAME)
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight)
    app.setWindowIcon(QIcon(str(asset_root() / "cvstudio" / "assets" / "cv-studio.svg")))
    apply_theme(settings.get("theme"))
    try:  # re-apply when Windows switches between light and dark
        app.styleHints().colorSchemeChanged.connect(lambda *_: settings.get("theme") == "system" and apply_theme("system"))
    except Exception:
        pass
    window = MainWindow(settings, ProfileStore())
    app._cv_main = window
    window.show()
    if os.environ.get("CVSTUDIO_SMOKE_TEST") == "1":
        QTimer.singleShot(900, app.quit)
    app.exec()
