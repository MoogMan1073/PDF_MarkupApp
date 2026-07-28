"""Main window: Viewer / TODO / Wire Numbers / Component Labels / PDF Tools
panes (tabified, floatable dock widgets), toolbar, comment + navigation docks,
settings dialog (Phases 1-9 integration)."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QEvent, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QFileDialog, QMessageBox, QDockWidget,
    QSpinBox, QLabel, QWidget, QDialogButtonBox, QDialog, QVBoxLayout,
    QHBoxLayout, QFormLayout, QLineEdit, QCheckBox, QComboBox, QPlainTextEdit,
    QColorDialog, QDoubleSpinBox, QPushButton, QGroupBox, QStatusBar,
    QApplication, QSlider,
)

from . import __app_name__, __version__, __copyright__, app_icon
from .config import AppConfig
from .model.document import Document
from .model.annotations import Annotation, KIND_COMMENT, KIND_TEXTBOX, KIND_CALLOUT
from .viewer.pdf_view import PdfView
from .viewer import tools as T
from .viewer.command_stack import ModifyAnnotationCommand, RemoveAnnotationCommand, capture
from .extraction import claude_api
from .panels.comment_panel import CommentPanel
from .panels.todo_panel import TodoPanel
from .panels.wire_panel import WirePanel
from .panels.component_panel import ComponentPanel
from .panels.tools_panel import ToolsPanel, pdf_path_from_mime
from .panels.nav_panel import NavPanel


# --- comment / textbox text editor -----------------------------------------


class TextEditDialog(QDialog):
    def __init__(self, ann: Annotation, parent=None, is_textbox=False):
        super().__init__(parent)
        self.ann = ann
        self.is_textbox = is_textbox
        self._font_color = tuple(ann.color)
        if ann.kind == KIND_CALLOUT:
            title = "Edit callout"
        elif is_textbox or ann.kind == KIND_TEXTBOX:
            title = "Edit text box"
        elif ann.kind == KIND_COMMENT:
            title = "Edit comment"
        else:
            # a free note attached to a highlight / arrow / rectangle / pen
            title = "Edit note" if (ann.text or "").strip() else "Add note"
        self.setWindowTitle(title)
        lay = QVBoxLayout(self)
        self.edit = QPlainTextEdit(ann.text or "")
        self.edit.setMinimumSize(320, 120)
        self.edit.installEventFilter(self)  # Ctrl/Shift+Enter -> OK
        lay.addWidget(self.edit)

        # font styling — only meaningful for on-page text boxes
        if is_textbox:
            self._fill_color = tuple(ann.fill_color) if ann.fill_color else None
            self._fill_opacity = float(ann.fill_opacity)
            frow = QHBoxLayout()
            self.size_spin = QSpinBox(); self.size_spin.setRange(4, 96)
            self.size_spin.setValue(int(ann.font_size))
            self.bold_cb = QCheckBox("B"); self.bold_cb.setChecked(ann.bold)
            self.italic_cb = QCheckBox("I"); self.italic_cb.setChecked(ann.italic)
            self.color_btn = QPushButton("Font color")
            self.color_btn.clicked.connect(self._pick_color)
            self._update_color_swatch()
            self.fill_btn = QPushButton("Fill")
            self.fill_btn.setToolTip("Box background — pick color + opacity "
                                     "(alpha 0 = none, 100% = opaque cover)")
            self.fill_btn.clicked.connect(self._pick_fill)
            self._update_fill_swatch()
            frow.addWidget(QLabel("Size:")); frow.addWidget(self.size_spin)
            frow.addWidget(self.bold_cb); frow.addWidget(self.italic_cb)
            frow.addWidget(self.color_btn); frow.addWidget(self.fill_btn)
            frow.addStretch(1)
            lay.addLayout(frow)

        self.todo = QCheckBox("Flag as TODO")
        self.todo.setChecked(ann.is_todo)
        lay.addWidget(self.todo)
        hint = QLabel("Ctrl+Enter or Shift+Enter to save · Esc to cancel")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _pick_color(self):
        rgb = self._font_color
        col = QColorDialog.getColor(
            QColor(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)), self,
            "Font color")
        if col.isValid():
            self._font_color = (col.redF(), col.greenF(), col.blueF())
            self._update_color_swatch()

    def _update_color_swatch(self):
        self.color_btn.setIcon(_swatch(QColor(
            int(self._font_color[0] * 255), int(self._font_color[1] * 255),
            int(self._font_color[2] * 255))))

    def _pick_fill(self):
        ok, color, opacity = FillDialog.ask(self, self._fill_color,
                                            self._fill_opacity, "Box fill")
        if not ok:
            return
        self._fill_color = color
        if color is not None:
            self._fill_opacity = opacity
        self._update_fill_swatch()

    def _update_fill_swatch(self):
        self.fill_btn.setIcon(_fill_swatch(self._fill_color, self._fill_opacity))

    def eventFilter(self, obj, event):
        if obj is self.edit and event.type() == QEvent.KeyPress:
            if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                    and (event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))):
                self.accept()
                return True
        return super().eventFilter(obj, event)

    def values(self):
        return self.edit.toPlainText(), self.todo.isChecked()

    def font_values(self):
        """Font styling for a text box, or ``None`` for a comment."""
        if not self.is_textbox:
            return None
        return {
            "font_size": float(self.size_spin.value()),
            "bold": self.bold_cb.isChecked(),
            "italic": self.italic_cb.isChecked(),
            "color": tuple(self._font_color),
            "fill_color": tuple(self._fill_color) if self._fill_color else None,
            "fill_opacity": float(self._fill_opacity),
        }


def _apply_font(ann: Annotation, fv) -> None:
    if not fv:
        return
    ann.font_size = fv["font_size"]
    ann.bold = fv["bold"]
    ann.italic = fv["italic"]
    ann.color = tuple(fv["color"])
    if "fill_color" in fv:
        ann.fill_color = tuple(fv["fill_color"]) if fv["fill_color"] else None
        ann.fill_opacity = fv["fill_opacity"]


# --- settings dialog --------------------------------------------------------


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.resize(560, 470)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs, 1)

        # identity
        gb_id = QGroupBox("Identity")
        f = QFormLayout(gb_id)
        self.name = QLineEdit(config.your_name)
        f.addRow("Your name (commenter):", self.name)

        # wire fields
        gb_w = QGroupBox("Wire number fields")
        fw = QFormLayout(gb_w)
        self.sheet_w = QSpinBox(); self.sheet_w.setRange(1, 6); self.sheet_w.setValue(int(config.get("wire/sheet_width")))
        self.rung_w = QSpinBox(); self.rung_w.setRange(1, 6); self.rung_w.setValue(int(config.get("wire/rung_width")))
        self.wire_w = QSpinBox(); self.wire_w.setRange(1, 6); self.wire_w.setValue(int(config.get("wire/wire_width")))
        self.zero_pad = QCheckBox("Zero-pad fields"); self.zero_pad.setChecked(bool(config.get("wire/zero_pad")))
        self.regex = QLineEdit(str(config.get("wire/regex_override") or ""))
        self.regex.setPlaceholderText(r"optional override, e.g. ^\d{6}$")
        self.cross_check = QCheckBox("Cross-check sheet (flag mismatches)")
        self.cross_check.setChecked(bool(config.get("wire/cross_check_sheet")))
        self.wire_method = QComboBox(); self.wire_method.addItems(["AI assist", "OCR"])
        self.wire_method.setCurrentIndex(0 if config.wire_extract_method == "ai" else 1)
        self.wire_method.setToolTip(
            "Default engine for scanned (no-text) pages in the Wire Numbers tab. "
            "You can also switch it there per extraction.")
        fw.addRow("Sheet width:", self.sheet_w)
        fw.addRow("Rung width:", self.rung_w)
        fw.addRow("Wire-index width:", self.wire_w)
        fw.addRow(self.zero_pad)
        fw.addRow("Full-label regex:", self.regex)
        fw.addRow(self.cross_check)
        fw.addRow("Scanned-page method:", self.wire_method)

        # component labels (FAMILY-SHEETRUNG, e.g. LT-10010)
        gb_cmp = QGroupBox("Component labels")
        fcmp = QFormLayout(gb_cmp)
        self.cmp_sheet_w = QSpinBox(); self.cmp_sheet_w.setRange(1, 6)
        self.cmp_sheet_w.setValue(int(config.get("component/sheet_width")))
        self.cmp_rung_w = QSpinBox(); self.cmp_rung_w.setRange(1, 6)
        self.cmp_rung_w.setValue(int(config.get("component/rung_width")))
        self.cmp_zero_pad = QCheckBox("Zero-pad fields")
        self.cmp_zero_pad.setChecked(bool(config.get("component/zero_pad")))
        self.cmp_method = QComboBox(); self.cmp_method.addItems(["AI assist", "OCR"])
        self.cmp_method.setCurrentIndex(0 if config.component_extract_method == "ai" else 1)
        self.cmp_labels_per = QSpinBox(); self.cmp_labels_per.setRange(1, 99)
        self.cmp_labels_per.setValue(config.component_labels_per_device)
        self.cmp_families = QPlainTextEdit(", ".join(config.component_families()))
        self.cmp_families.setMaximumHeight(90)
        self.cmp_families.setToolTip(
            "Known device family codes (comma- or newline-separated), e.g. "
            "LT, CR, PB. Labels with codes not listed here are still captured "
            "but flagged 'unknown family'.")
        fcmp.addRow("Sheet width:", self.cmp_sheet_w)
        fcmp.addRow("Rung width:", self.cmp_rung_w)
        fcmp.addRow(self.cmp_zero_pad)
        fcmp.addRow("Scanned-page method:", self.cmp_method)
        fcmp.addRow("Labels per device:", self.cmp_labels_per)
        fcmp.addRow("Family codes:", self.cmp_families)

        # export
        gb_e = QGroupBox("Export defaults")
        fe = QFormLayout(gb_e)
        self.labels_per = QSpinBox(); self.labels_per.setRange(1, 99); self.labels_per.setValue(int(config.get("export/labels_per_wire")))
        self.exp_mode = QComboBox(); self.exp_mode.addItems(["single", "per_sheet"])
        self.exp_mode.setCurrentText(str(config.get("export/mode")))
        self.exp_fmt = QComboBox(); self.exp_fmt.addItems(["xlsx", "csv"])
        self.exp_fmt.setCurrentText(str(config.get("export/format")))
        fe.addRow("Labels per wire:", self.labels_per)
        fe.addRow("Default mode:", self.exp_mode)
        fe.addRow("Default format:", self.exp_fmt)

        # comments / junk
        gb_c = QGroupBox("Comments & junk filter")
        fc = QFormLayout(gb_c)
        self.treat_todo = QCheckBox("Treat all comments as TODO items")
        self.treat_todo.setChecked(bool(config.get("comments/treat_all_as_todo")))
        self.show_ignored = QCheckBox("Show ignored (SHX/AutoCAD junk)")
        self.show_ignored.setChecked(bool(config.get("filter/show_ignored")))
        self.ignore = QPlainTextEdit("\n".join(config.ignore_patterns()))
        self.ignore.setMaximumHeight(90)
        fc.addRow(self.treat_todo)
        fc.addRow(self.show_ignored)
        fc.addRow("Ignore patterns (one regex/line):", self.ignore)

        # ocr / ai
        gb_a = QGroupBox("OCR & AI assist")
        fa = QFormLayout(gb_a)
        self.ocr = QCheckBox("Enable OCR fallback (Tesseract)")
        self.ocr.setChecked(bool(config.get("ocr/enabled")))
        self.ai = QCheckBox("Enable Claude vision assist")
        self.ai.setChecked(bool(config.get("ai/enabled")))
        self.ai.toggled.connect(self._on_ai_toggled)
        self.ai_key = QLineEdit(str(config.get("ai/api_key") or ""))
        self.ai_key.setEchoMode(QLineEdit.Password)
        self.ai_key.setPlaceholderText("sk-ant-…  (leave blank to use ANTHROPIC_API_KEY)")
        self.ai_key.textChanged.connect(self._refresh_api_status)
        self.ai_show = QCheckBox("Show")
        self.ai_show.toggled.connect(
            lambda v: self.ai_key.setEchoMode(QLineEdit.Normal if v else QLineEdit.Password))
        key_row = QHBoxLayout(); key_row.addWidget(self.ai_key, 1); key_row.addWidget(self.ai_show)
        key_wrap = QWidget(); key_wrap.setLayout(key_row)
        self.ai_status = QLabel()
        self.btn_check = QPushButton("Check API status")
        self.btn_check.clicked.connect(self._check_api)
        self.ai_model = QLineEdit(str(config.get("ai/model")))
        self.ai_tiles = QSpinBox(); self.ai_tiles.setRange(1, 4)
        self.ai_tiles.setValue(int(config.get("ai/tiles")))
        self.ai_tiles.setToolTip(
            "Split each scanned page into an N×N grid of tiles, each read at full "
            "resolution so small wire numbers survive. Higher = more accurate but "
            "more API calls per page (N×N). 1 = whole page.")
        fa.addRow(self.ocr)
        fa.addRow(self.ai)
        fa.addRow("API key:", key_wrap)
        fa.addRow("", self.btn_check)
        fa.addRow("Status:", self.ai_status)
        fa.addRow("AI model:", self.ai_model)
        fa.addRow("AI tiling (N×N, calls/page = N²):", self.ai_tiles)
        self._on_ai_toggled(self.ai.isChecked())
        self._refresh_api_status()

        # organise the group boxes into tabs so the dialog never outgrows the
        # screen (was a single tall column of every section stacked vertically)
        def _page(*boxes):
            w = QWidget(); v = QVBoxLayout(w)
            for b in boxes:
                v.addWidget(b)
            v.addStretch(1)
            return w
        tabs.addTab(_page(gb_id, gb_e, gb_c), "General")
        tabs.addTab(_page(gb_w), "Wire numbers")
        tabs.addTab(_page(gb_cmp), "Component labels")
        tabs.addTab(_page(gb_a), "OCR / AI")

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def apply(self):
        c = self.config
        c.set("your_name", self.name.text() or "user")
        c.set("wire/sheet_width", self.sheet_w.value())
        c.set("wire/rung_width", self.rung_w.value())
        c.set("wire/wire_width", self.wire_w.value())
        c.set("wire/zero_pad", self.zero_pad.isChecked())
        c.set("wire/regex_override", self.regex.text())
        c.set("wire/cross_check_sheet", self.cross_check.isChecked())
        c.set("wire/extract_method", "ai" if self.wire_method.currentIndex() == 0 else "ocr")
        c.set("component/sheet_width", self.cmp_sheet_w.value())
        c.set("component/rung_width", self.cmp_rung_w.value())
        c.set("component/zero_pad", self.cmp_zero_pad.isChecked())
        c.set("component/extract_method", "ai" if self.cmp_method.currentIndex() == 0 else "ocr")
        c.set("component/labels_per_device", self.cmp_labels_per.value())
        import re as _re
        fams = [f for f in _re.split(r"[,\n]+", self.cmp_families.toPlainText()) if f.strip()]
        c.set_component_families(fams)
        c.set("export/labels_per_wire", self.labels_per.value())
        c.set("export/mode", self.exp_mode.currentText())
        c.set("export/format", self.exp_fmt.currentText())
        c.set("comments/treat_all_as_todo", self.treat_todo.isChecked())
        c.set("filter/show_ignored", self.show_ignored.isChecked())
        c.set_ignore_patterns([l.strip() for l in self.ignore.toPlainText().splitlines() if l.strip()])
        c.set("ocr/enabled", self.ocr.isChecked())
        c.set("ai/enabled", self.ai.isChecked())
        c.set("ai/api_key", self.ai_key.text().strip())
        c.set("ai/model", self.ai_model.text())
        c.set("ai/tiles", self.ai_tiles.value())
        c.sync()

    # -- AI assist helpers ---------------------------------------------------

    def _on_ai_toggled(self, on: bool):
        for w in (self.ai_key, self.ai_show, self.btn_check, self.ai_model, self.ai_tiles):
            w.setEnabled(on)
        self._refresh_api_status()

    def _refresh_api_status(self):
        if not self.ai.isChecked():
            self.ai_status.setText("AI assist disabled")
            self.ai_status.setStyleSheet("color: gray;")
            return
        state, msg = claude_api.status(self.ai_key.text())
        color = {"present": "#1b7f3a", "missing": "#b8860b", "no_sdk": "#c0392b"}.get(state, "gray")
        self.ai_status.setText(msg)
        self.ai_status.setStyleSheet(f"color: {color};")

    def _check_api(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, msg = claude_api.validate_key(
                self.ai_key.text(), self.ai_model.text() or claude_api.DEFAULT_MODEL)
        finally:
            QApplication.restoreOverrideCursor()
        self.ai_status.setText(msg)
        self.ai_status.setStyleSheet("color: #1b7f3a;" if ok else "color: #c0392b;")


def _swatch(color: QColor) -> QIcon:
    pm = QPixmap(16, 16)
    pm.fill(color)
    return QIcon(pm)


def _fill_swatch(rgb, opacity) -> QIcon:
    """Swatch for the Fill button: a checkerboard shows through translucent /
    no-fill states so 'transparent' is visually distinct from 'white cover'."""
    from PySide6.QtGui import QPainter, QColor as _QC
    pm = QPixmap(16, 16)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    # grey checkerboard backdrop
    for i in range(0, 16, 4):
        for j in range(0, 16, 4):
            shade = 200 if ((i + j) // 4) % 2 == 0 else 235
            p.fillRect(i, j, 4, 4, _QC(shade, shade, shade))
    if rgb is not None and opacity > 0:
        a = int(max(0.0, min(1.0, opacity)) * 255)
        p.fillRect(0, 0, 16, 16,
                   _QC(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), a))
    p.setPen(_QC(120, 120, 120))
    p.drawRect(0, 0, 15, 15)
    p.end()
    return QIcon(pm)


class FillDialog(QDialog):
    """Pick an interior fill: a color plus a plain-language opacity slider
    (clearer than a raw alpha channel), or 'No fill'."""

    def __init__(self, color, opacity, parent=None, title="Fill"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._color = tuple(color) if color else (1.0, 1.0, 1.0)
        lay = QVBoxLayout(self)

        self.none_cb = QCheckBox("No fill (transparent)")
        self.none_cb.setChecked(color is None)
        self.none_cb.toggled.connect(self._on_none_toggled)
        lay.addWidget(self.none_cb)

        crow = QHBoxLayout()
        self.color_btn = QPushButton("Color…")
        self.color_btn.clicked.connect(self._pick_color)
        crow.addWidget(self.color_btn)
        self.swatch = QLabel()
        self.swatch.setFixedSize(48, 20)
        crow.addWidget(self.swatch)
        crow.addStretch(1)
        lay.addLayout(crow)

        srow = QHBoxLayout()
        srow.addWidget(QLabel("Opacity:"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(round(max(0.0, min(1.0, opacity)) * 100)))
        self.slider.valueChanged.connect(self._on_slider)
        srow.addWidget(self.slider, 1)
        self.pct = QLabel(f"{self.slider.value()}%")
        self.pct.setFixedWidth(40)
        srow.addWidget(self.pct)
        lay.addLayout(srow)

        hint = QLabel("0% = transparent · 100% = opaque cover")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(hint)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._on_none_toggled(self.none_cb.isChecked())
        self._update_swatch()

    def _on_none_toggled(self, none_on: bool):
        for w in (self.color_btn, self.slider, self.pct):
            w.setEnabled(not none_on)
        self._update_swatch()

    def _on_slider(self, v: int):
        self.pct.setText(f"{v}%")
        self._update_swatch()

    def _pick_color(self):
        rgb = self._color
        col = QColorDialog.getColor(
            QColor(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)),
            self, "Fill color")           # no alpha channel — opacity is the slider
        if col.isValid():
            self._color = (col.redF(), col.greenF(), col.blueF())
            self._update_swatch()

    def _update_swatch(self):
        if self.none_cb.isChecked():
            self.swatch.setPixmap(_fill_swatch(None, 0.0).pixmap(20, 20))
        else:
            self.swatch.setPixmap(
                _fill_swatch(self._color, self.slider.value() / 100.0).pixmap(20, 20))

    def result_fill(self):
        """Return (color_tuple_or_None, opacity_float)."""
        if self.none_cb.isChecked() or self.slider.value() <= 0:
            return None, 1.0
        return self._color, self.slider.value() / 100.0

    @staticmethod
    def ask(parent, color, opacity, title="Fill"):
        """Show the dialog; return (accepted, color_or_None, opacity)."""
        dlg = FillDialog(color, opacity, parent, title)
        if dlg.exec() == QDialog.Accepted:
            c, o = dlg.result_fill()
            return True, c, o
        return False, color, opacity


# --- main window ------------------------------------------------------------


# Bumped whenever the dock set/layout handling changes so QMainWindow
# .restoreState() rejects (and we fall back to the default arrangement) layouts
# saved by an older build — e.g. the earlier QTabWidget central widget, or a
# pre-fix build whose saved layout left the main panes un-tabbed.
_UI_STATE_VERSION = 3


class _MainDocks:
    """A thin ``QTabWidget``-compatible facade over the tabified main dock
    widgets (Viewer / TODO / Wire Numbers / Component Labels / PDF Tools).

    The five main panes used to live in a ``QTabWidget`` central widget. They
    now live in floatable, dockable ``QDockWidget``s — like the Comments /
    Navigation panels — so any tab can be pulled into its own window or docked
    elsewhere. This shim lets the rest of the window keep calling
    ``tabs.setCurrentWidget(w)`` / ``tabs.currentWidget()`` unchanged, and
    tracks which pane is "current" by watching the docks' visibility.
    """

    def __init__(self, window):
        self._window = window
        self._docks = {}          # panel widget -> QDockWidget
        self._order = []          # panel widgets, in tab order
        self._current = None

    def add(self, widget, title, object_name):
        dock = QDockWidget(title, self._window)
        dock.setObjectName(object_name)
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.visibilityChanged.connect(
            lambda vis, w=widget: self._on_visibility(w, vis))
        self._docks[widget] = dock
        self._order.append(widget)
        if self._current is None:
            self._current = widget
        return dock

    def _on_visibility(self, widget, visible):
        # A dock reports visible when it becomes the raised tab (or is floated /
        # revealed). Track that as the "current" pane so currentWidget() follows
        # the user clicking between tabs, not just explicit setCurrentWidget().
        if visible:
            self._current = widget

    def dock_for(self, widget):
        return self._docks.get(widget)

    def setCurrentWidget(self, widget):
        dock = self._docks.get(widget)
        if dock is None:
            return
        self._current = widget
        dock.show()
        dock.raise_()

    def currentWidget(self):
        # Return the tracked pane unless it's been closed/hidden (e.g. a floated
        # pane the user closed with its ✕) — then fall back to a live pane so
        # callers never treat a closed pane as the active one. isHidden() is used
        # rather than isVisible() so this is correct before the window is shown
        # (headless, nothing is "visible" yet) as well as after.
        cur = self._current
        dock = self._docks.get(cur)
        if dock is not None and not dock.isHidden():
            return cur
        for w in self._order:
            d = self._docks.get(w)
            if d is not None and not d.isHidden():
                return w
        return self._order[0] if self._order else None


class MainWindow(QMainWindow):
    def __init__(self, on_progress=None):
        super().__init__()
        self._progress = on_progress or (lambda *a, **k: None)
        self.setWindowTitle(__app_name__)
        self.setWindowIcon(app_icon())
        self.resize(1320, 880)
        self.setAcceptDrops(True)   # drop a PDF anywhere to open it
        # Visual-Studio-style dockable panels: drag a pane's title bar to snap it
        # to any edge (left/right/top/bottom), split panes side-by-side, tab them
        # together, or float a pane out into its own window (and drag it back).
        # GroupedDragging is deliberately OFF: it enables Qt's floating tab-group
        # windows, and dragging one floating window onto another to merge them is
        # a known Qt hang. Without it, panes tab in the main window and float out
        # individually, but two floating windows won't merge — so no hang.
        self.setDockOptions(
            QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks
            | QMainWindow.AllowTabbedDocks)
        # Put the pane tabs on TOP (like the old QTabWidget) instead of Qt's
        # default bottom position for tabified docks.
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)
        self.config = AppConfig()
        self.document = None
        self._print_include_marks = True   # print the app's markups by default

        self._progress("Preparing the canvas…", 62)
        self.view = PdfView(self)
        self.view.config = self.config
        self.view.requestCommentEdit.connect(self._edit_comment)
        self.view.requestTextEdit.connect(self._edit_textbox)
        self.view.requestFillEdit.connect(self._edit_fill)
        self.view.pageChanged.connect(self._on_page_changed)
        self.view.requestTool.connect(self._activate_tool)
        self.view.requestOpen.connect(self.load_document)   # drag/drop a PDF
        self.view.requestReveal.connect(self._reveal_in_panel)   # PDF mark -> panel
        # synchronous prompt used when *creating* a new comment / text box
        self.view.new_text_prompt = self._prompt_new_text
        # synchronous prompt when a drawing tool clicks an existing mark
        self.view.existing_mark_prompt = self._prompt_existing_mark

        self._progress("Setting up the wire-number engine…", 75)
        self.todo_panel = TodoPanel()
        self.wire_panel = WirePanel()
        self.component_panel = ComponentPanel()
        self.tools_panel = ToolsPanel(self)

        self.todo_panel.activated.connect(self._jump_to)
        self.todo_panel.authorEditRequested.connect(self._edit_author)
        self.wire_panel.activated.connect(self._jump_to)        # double-click → drawing
        self.component_panel.activated.connect(self._jump_to)

        self._progress("Building the comment & TODO panels…", 85)
        # navigation dock (pages + bookmarks) on the left
        self.nav_panel = NavPanel()
        self.nav_panel.pageActivated.connect(self._nav_to_page)
        nav_dock = QDockWidget("Navigation", self)
        nav_dock.setObjectName("NavDock")
        nav_dock.setWidget(self.nav_panel)
        nav_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.addDockWidget(Qt.LeftDockWidgetArea, nav_dock)
        self.nav_dock = nav_dock

        # comment dock
        self.comment_panel = CommentPanel()
        self.comment_panel.activated.connect(self._jump_to)
        self.comment_panel.deleteRequested.connect(self._delete_annotation)
        self.comment_panel.authorEditRequested.connect(self._edit_author)
        dock = QDockWidget("Comments", self)
        dock.setObjectName("CommentDock")
        dock.setWidget(self.comment_panel)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.comment_dock = dock

        # Optional second viewer of the SAME document — a read-only reference
        # pane for keeping a legend, TOC or cover sheet in view while you work
        # on another page. It scrolls/zooms/rotates independently; because both
        # views listen to the one AnnotationStore, marks made in the main viewer
        # appear here live. Hidden until asked for (View ▸ Reference viewer).
        self.ref_view = PdfView(read_only=True)
        self.ref_view.config = self.config
        self.ref_view.requestOpen.connect(self.load_document)   # drag/drop a PDF
        ref_dock = QDockWidget("Reference viewer", self)
        ref_dock.setObjectName("RefViewDock")
        ref_dock.setWidget(self.ref_view)
        ref_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.addDockWidget(Qt.RightDockWidgetArea, ref_dock)
        ref_dock.hide()
        self.ref_dock = ref_dock

        # The five main panes (Viewer / TODO / Wire Numbers / Component Labels /
        # PDF Tools) live in tabified, floatable dock widgets — like the
        # Comments / Navigation panels — so any tab can be dragged into its own
        # standalone window or docked elsewhere on screen. A zero-size, hidden
        # central widget keeps QMainWindow satisfied while the docks fill the
        # frame; ``self.tabs`` is a QTabWidget-compatible facade over them.
        central = QWidget()
        central.setMaximumSize(0, 0)
        self.setCentralWidget(central)
        self._central_stub = central

        self.tabs = _MainDocks(self)
        view_dock = self.tabs.add(self.view, "Viewer", "ViewerDock")
        todo_dock = self.tabs.add(self.todo_panel, "TODO", "TodoDock")
        wire_dock = self.tabs.add(self.wire_panel, "Wire Numbers", "WireDock")
        comp_dock = self.tabs.add(self.component_panel, "Component Labels",
                                  "ComponentDock")
        tools_dock = self.tabs.add(self.tools_panel, "PDF Tools", "PdfToolsDock")
        # Lay them out as one tab group between the Navigation (left) and
        # Comments (right) docks: [nav | main-tabs | comments]. Both horizontal
        # splits must happen *before* the tabify loop — splitDockWidget against
        # an already-tabbed dock adds a new tab instead of a neighbour, so we
        # carve out view_dock's column (and re-home the Comments dock beside it)
        # while it's still a lone dock, then tab the other panes onto it.
        self.splitDockWidget(nav_dock, view_dock, Qt.Horizontal)
        self.splitDockWidget(view_dock, self.comment_dock, Qt.Horizontal)
        for d in (todo_dock, wire_dock, comp_dock, tools_dock):
            self.tabifyDockWidget(view_dock, d)
        self.main_docks = [view_dock, todo_dock, wire_dock, comp_dock, tools_dock]
        self.tabs.setCurrentWidget(self.view)   # Viewer is the default tab

        self._progress("Assembling the toolbar…", 92)
        self.setStatusBar(QStatusBar())
        self._build_menu()
        self._build_toolbar()
        self._update_actions_enabled(False)

        # Remember the freshly-built default arrangement (for "Reset panel
        # layout"), then apply whatever layout the user left last session.
        self._default_state = self.saveState(_UI_STATE_VERSION)
        self._restore_ui_state()

    # -- menu / toolbar ------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()
        m_file = mb.addMenu("&File")
        self.act_open = m_file.addAction("&Open PDF…", self.open_pdf, QKeySequence.Open)
        self.act_save = m_file.addAction("&Save markup", self.save_markup, QKeySequence.Save)
        self.act_save_as = m_file.addAction(
            "Save &As… (fork working file)", self.save_as_fork,
            QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.setToolTip(
            "Copy this file's markup into a new working file and switch to it; "
            "the original stays untouched.")
        self.act_export_pdf = m_file.addAction(
            "Export annotated PDF…", self.export_pdf, QKeySequence("Ctrl+Shift+E"))
        self.act_export_flat = m_file.addAction(
            "Export flattened PDF (for sharing)…", self.export_flat)
        self.act_export_flat.setToolTip(
            "Bake the marks into the page so they render in every viewer "
            "(browsers, Preview, thumbnails). Not re-editable — keep your "
            "working file for edits.")
        m_file.addSeparator()
        self.act_print = m_file.addAction(
            "&Print…", self.print_document, QKeySequence.Print)   # Ctrl+P
        self.act_print.setToolTip(
            "Print the drawing (with its marks) to any installed printer via the "
            "system print dialog.")
        self.act_print_preview = m_file.addAction(
            "Print pre&view…", self.print_preview)
        self.act_print_preview.setToolTip(
            "See the pages before printing, then print from the preview.")
        m_file.addSeparator()
        m_file.addAction("Settings…", self.open_settings)
        m_file.addSeparator()
        m_file.addAction("Quit", self.close, QKeySequence.Quit)

        m_edit = mb.addMenu("&Edit")
        undo = self.view.undo_stack.createUndoAction(self, "Undo")
        undo.setShortcut(QKeySequence.Undo)
        redo = self.view.undo_stack.createRedoAction(self, "Redo")
        redo.setShortcut(QKeySequence.Redo)
        m_edit.addAction(undo)
        m_edit.addAction(redo)

        m_view = mb.addMenu("&View")
        m_view.addAction("Fit width", self.view.fit_width)
        m_view.addAction("Fit page", self.view.fit_page)
        m_view.addAction("Zoom in", self.view.zoom_in, QKeySequence.ZoomIn)
        m_view.addAction("Zoom out", self.view.zoom_out, QKeySequence.ZoomOut)
        m_view.addSeparator()
        m_view.addAction("Find…", self.view.show_search, QKeySequence.Find)
        m_view.addSeparator()
        act_cmt = m_view.addAction(
            "Toggle comment sidebar",
            lambda: self.comment_dock.setVisible(not self.comment_dock.isVisible()))
        act_cmt.setShortcut("F10")
        act_nav = m_view.addAction(
            "Toggle navigation panel",
            lambda: self.nav_dock.setVisible(not self.nav_dock.isVisible()))
        act_nav.setShortcut("F9")
        act_ref = m_view.addAction(
            "Reference viewer (second view)",
            lambda: self._toggle_reference_view())
        act_ref.setShortcut("F8")
        act_ref.setToolTip(
            "A second, read-only view of the same PDF — keep a legend, TOC or "
            "cover sheet in view while you work on another page.")
        self.act_ref_view = act_ref
        # Show/hide (and re-open a closed) main pane. Each dock has a close
        # button, so these bring one back after it's been closed or floated away.
        m_panes = m_view.addMenu("Panes")
        for d in self.main_docks:
            m_panes.addAction(d.toggleViewAction())
        m_view.addSeparator()
        m_view.addAction("Reset panel layout", self.reset_layout)

        m_tools = mb.addMenu("&Tools")
        m_tools.addAction("Extract pages (visual)…", lambda: self.tools_panel.show_operation("extract"))
        m_tools.addAction("Split into ranges…", lambda: self.tools_panel.show_operation("split"))
        m_tools.addAction("Delete pages (visual)…", lambda: self.tools_panel.show_operation("delete"))
        m_tools.addAction("Rotate pages (visual)…", lambda: self.tools_panel.show_operation("rotate"))
        m_tools.addSeparator()
        m_tools.addAction("Split by sheet number… (wizard)", lambda: self.tools_panel.start_sheet_wizard())
        m_tools.addSeparator()
        m_tools.addAction("Combine PDFs…", lambda: self.tools_panel.open_combine())
        m_tools.addAction("Insert PDF…", lambda: self.tools_panel.open_insert())
        m_tools.addAction("Swap a page…", lambda: self.tools_panel.open_swap())
        m_tools.addSeparator()
        m_tools.addAction("PDF → Word…", lambda: self.tools_panel.open_convert())
        m_tools.addAction("Crop / extract… (wizard)", lambda: self.tools_panel.start_crop_wizard())

        m_help = mb.addMenu("&Help")
        m_help.addAction("User Manual", self._show_help, QKeySequence.HelpContents)
        m_help.addAction("About " + __app_name__, self._show_about)

    def _show_help(self):
        from .help import HelpWindow
        # keep a reference so the window isn't garbage-collected
        self._help_window = HelpWindow(self)
        self._help_window.show()
        self._help_window.raise_()

    def _show_about(self):
        QMessageBox.about(
            self, "About " + __app_name__,
            f"<h3>{__app_name__}</h3>"
            f"<p>Version {__version__}</p>"
            f"<p>PDF markup &amp; wire-number extraction for AutoCAD "
            f"Electrical drawing sets.</p>"
            f"<p>{__copyright__}</p>",
        )

    def _build_toolbar(self):
        tb = QToolBar("Tools")
        tb.setObjectName("MainToolBar")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)
        # tools grouped by purpose; None marks a separator between groups
        tool_defs = [
            (T.TOOL_SELECT, "Select"),
            None,                                            # -- freehand markup
            (T.TOOL_HIGHLIGHT, "Highlight"), (T.TOOL_PEN, "Pen"),
            (T.TOOL_ERASER, "Eraser"),
            None,                                            # -- text / notes
            (T.TOOL_COMMENT, "Comment"), (T.TOOL_TEXTBOX, "Text box"),
            (T.TOOL_CALLOUT, "Callout"),
            None,                                            # -- shapes
            (T.TOOL_RECT, "Rectangle"), (T.TOOL_ARROW, "Arrow"),
            (T.TOOL_CLOUD, "Cloud"),
        ]
        tool_tips = {
            T.TOOL_CALLOUT: "Callout: drag a box, type the note, then drag the "
                            "orange tip to point at the target",
            T.TOOL_CLOUD: "Revision cloud: drag freehand, Shift+drag for a "
                          "rectangle, or click corners and double-click / Enter "
                          "to close",
        }
        self._tool_actions = {}
        n = 0
        for entry in tool_defs:
            if entry is None:
                tb.addSeparator()
                continue
            tool, label = entry
            act = QAction(label, self, checkable=True)
            act.setData(tool)
            # Ctrl+1..Ctrl+9 then Ctrl+0 select tools in toolbar order
            n += 1
            if n <= 10:
                digit = 0 if n == 10 else n
                key = QKeySequence(f"Ctrl+{digit}")
                act.setShortcut(key)
                tip = tool_tips.get(tool, label)
                act.setToolTip(f"{tip}  (Ctrl+{digit})")
                act.setStatusTip(act.toolTip())
            elif tool in tool_tips:
                act.setToolTip(tool_tips[tool])
                act.setStatusTip(tool_tips[tool])
            act.triggered.connect(lambda _=False, t=tool: self._activate_tool(t))
            self.tool_group.addAction(act)
            tb.addAction(act)
            self._tool_actions[tool] = act
            if tool == T.TOOL_SELECT:
                act.setChecked(True)
        tb.addSeparator()

        # color + widths
        self.color_btn = QPushButton("Color")
        self.color_btn.clicked.connect(self._pick_color)
        tb.addWidget(self.color_btn)
        self.fill_btn = QPushButton("Fill")
        self.fill_btn.setToolTip(
            "Interior fill for rectangles & text boxes — pick a color and "
            "opacity (drag alpha to 0 for no fill, 100% for an opaque cover)")
        self.fill_btn.clicked.connect(self._pick_fill)
        tb.addWidget(self.fill_btn)
        tb.addWidget(QLabel(" Pen "))
        self.pen_width = QDoubleSpinBox(); self.pen_width.setRange(0.5, 20); self.pen_width.setValue(2.0)
        self.pen_width.valueChanged.connect(lambda v: setattr(self.view.tool, "pen_width", v))
        tb.addWidget(self.pen_width)
        tb.addWidget(QLabel(" Font "))
        self.font_size = QSpinBox(); self.font_size.setRange(4, 96); self.font_size.setValue(12)
        self.font_size.valueChanged.connect(lambda v: setattr(self.view.tool, "font_size", float(v)))
        tb.addWidget(self.font_size)
        self.bold = QCheckBox("B"); self.bold.toggled.connect(lambda v: setattr(self.view.tool, "bold", v))
        self.italic = QCheckBox("I"); self.italic.toggled.connect(lambda v: setattr(self.view.tool, "italic", v))
        tb.addWidget(self.bold); tb.addWidget(self.italic)
        tb.addSeparator()

        # rotate whole document (permanent — writes a rotated copy)
        act_ccw = tb.addAction("↺", lambda: self.rotate_all_pages(270))
        act_ccw.setToolTip("Rotate the view 90° counter-clockwise (in memory; marks rotate too)")
        act_cw = tb.addAction("↻", lambda: self.rotate_all_pages(90))
        act_cw.setToolTip("Rotate the view 90° clockwise (in memory; marks rotate too)")
        tb.addSeparator()

        # zoom (− / editable % / +) + fit
        tb.addAction("−", self.view.zoom_out)
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setInsertPolicy(QComboBox.NoInsert)
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%", "400%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setFixedWidth(72)
        self.zoom_combo.lineEdit().setAlignment(Qt.AlignCenter)
        self.zoom_combo.setToolTip("Zoom level — pick a preset or type a percentage")
        self.zoom_combo.textActivated.connect(self._apply_zoom_text)
        self.zoom_combo.lineEdit().returnPressed.connect(
            lambda: self._apply_zoom_text(self.zoom_combo.currentText()))
        tb.addWidget(self.zoom_combo)
        tb.addAction("+", self.view.zoom_in)
        tb.addAction("Fit W", self.view.fit_width)
        tb.addAction("Fit P", self.view.fit_page)
        self.view.zoomChanged.connect(self._on_zoom_changed)
        tb.addWidget(QLabel("  Page "))
        self.page_spin = QSpinBox(); self.page_spin.setRange(1, 1)
        self.page_spin.valueChanged.connect(lambda v: self.view.go_to_page(v - 1))
        tb.addWidget(self.page_spin)
        self.page_total = QLabel(" / 0")
        tb.addWidget(self.page_total)
        self._update_color_btn()
        self._update_fill_btn()

    # -- zoom % readout ------------------------------------------------------

    def _on_zoom_changed(self, zoom: float):
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(f"{round(zoom * 100)}%")
        self.zoom_combo.blockSignals(False)

    def _apply_zoom_text(self, text: str):
        t = (text or "").strip().rstrip("%").strip()
        try:
            pct = float(t)
        except ValueError:
            self._on_zoom_changed(self.view._zoom)   # revert to the real value
            return
        if pct > 0:
            self.view.set_zoom(pct / 100.0)

    # -- rotate whole document (in the viewer, in memory) --------------------

    def rotate_all_pages(self, angle: int):
        """Rotate the whole document in the viewer by ``angle`` degrees. This is
        an **in-memory view rotation only** — nothing is written to disk. Marks,
        comments and highlights rotate with their page and snap back exactly when
        rotated the other way."""
        if self.document is None:
            QMessageBox.information(self, "No document", "Open a PDF first.")
            return
        self.tabs.setCurrentWidget(self.view)   # rotation is a Viewer action
        self.view.rotate_view(angle)

    # -- tool handling -------------------------------------------------------

    def _set_tool(self, tool):
        from PySide6.QtWidgets import QGraphicsView, QGraphicsItem
        # abandon a half-drawn revision-cloud polygon when switching away
        if getattr(self.view, "_cloud_pts", None) is not None:
            self.view._cloud_cancel()
        self.view._suppress_existing_prompt = False
        self.view.tool.current = tool
        self.view.setDragMode(
            QGraphicsView.RubberBandDrag if tool == T.TOOL_SELECT
            else QGraphicsView.NoDrag)
        select = tool == T.TOOL_SELECT
        for it in self.view._item_by_ann.values():
            if it is None:
                continue
            it.setFlag(QGraphicsItem.ItemIsMovable, select)
            it.setFlag(QGraphicsItem.ItemIsSelectable, select)
        self._update_color_btn()
        self._update_fill_btn()

    def _activate_tool(self, tool):
        """Programmatically switch tools and reflect it in the toolbar."""
        for act in self.tool_group.actions():
            if act.data() == tool:
                act.setChecked(True)
        self._set_tool(tool)

    def _prompt_existing_mark(self, ann):
        """Drawing tool clicked an existing mark: edit / draw-new / cancel."""
        box = QMessageBox(self)
        box.setWindowTitle("Existing mark")
        box.setText("You clicked an existing mark.")
        box.setInformativeText("Edit this mark, or draw a new one here?")
        edit_btn = box.addButton("Edit existing", QMessageBox.AcceptRole)
        new_btn = box.addButton("Draw new", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is edit_btn:
            return "edit"
        if clicked is new_btn:
            return "new"
        return "cancel"

    def _active_color_attr(self):
        t = self.view.tool.current
        return {
            T.TOOL_HIGHLIGHT: "highlight_color", T.TOOL_PEN: "pen_color",
            T.TOOL_TEXTBOX: "text_color", T.TOOL_RECT: "shape_color",
            T.TOOL_ARROW: "shape_color", T.TOOL_CALLOUT: "text_color",
            T.TOOL_CLOUD: "shape_color",
        }.get(t, "pen_color")

    def _update_color_btn(self):
        rgb = getattr(self.view.tool, self._active_color_attr())
        self.color_btn.setIcon(_swatch(QColor(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))))

    def _pick_color(self):
        attr = self._active_color_attr()
        rgb = getattr(self.view.tool, attr)
        col = QColorDialog.getColor(QColor(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)), self)
        if col.isValid():
            setattr(self.view.tool, attr, (col.redF(), col.greenF(), col.blueF()))
            self._update_color_btn()

    def _active_fill_attrs(self):
        """(color_attr, opacity_attr) for the fill-capable tool, else (None, None)."""
        t = self.view.tool.current
        if t == T.TOOL_RECT:
            return "shape_fill", "shape_fill_opacity"
        if t in (T.TOOL_TEXTBOX, T.TOOL_CALLOUT):
            return "text_fill", "text_fill_opacity"
        return None, None

    def _update_fill_btn(self):
        c_attr, o_attr = self._active_fill_attrs()
        enabled = c_attr is not None
        self.fill_btn.setEnabled(enabled)
        rgb = getattr(self.view.tool, c_attr) if enabled else None
        op = getattr(self.view.tool, o_attr) if enabled else 0.0
        self.fill_btn.setIcon(_fill_swatch(rgb, op))

    def _pick_fill(self):
        c_attr, o_attr = self._active_fill_attrs()
        if c_attr is None:
            return
        rgb = getattr(self.view.tool, c_attr)
        op = getattr(self.view.tool, o_attr)
        ok, color, opacity = FillDialog.ask(self, rgb, op, "Fill")
        if not ok:
            return
        setattr(self.view.tool, c_attr, color)
        if color is not None:
            setattr(self.view.tool, o_attr, opacity)
        self._update_fill_btn()

    # -- document lifecycle --------------------------------------------------

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF (*.pdf)")
        if path:
            self.load_document(path)

    # -- drag & drop (open a dropped PDF in the viewer) ----------------------

    def dragEnterEvent(self, event):
        if pdf_path_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if pdf_path_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        # if the drop is over the PDF Tools tab, let that panel handle it
        if self.tabs.currentWidget() is self.tools_panel:
            return
        path = pdf_path_from_mime(event.mimeData())
        if path:
            self.load_document(path)
            event.acceptProposedAction()

    def load_document(self, path):
        from .model.storage import sidecar_path

        def _doc_key(p):
            return os.path.normcase(os.path.realpath(sidecar_path(p)))

        # Feature 1: refuse to open the document that's already open. foo.pdf and
        # foo.marked.pdf share a sidecar, so they count as the same document.
        if self.document is not None and _doc_key(path) == _doc_key(self.document.path):
            QMessageBox.information(
                self, "Already open",
                f"“{os.path.basename(path)}” is already open.")
            return
        if self.document is not None:
            try:
                self.document.close()
            except Exception:
                pass
        try:
            doc = Document(path, ignore_patterns=self.config.ignore_patterns())
            doc.load()
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))
            return
        self.document = doc
        # Feature 4: a .marked.pdf was opened but its original markup database
        # couldn't be found, so a new one was started — let the user know.
        if getattr(doc, "sidecar_recreated", False):
            QMessageBox.information(
                self, "New markup database",
                "This .marked.pdf's original markup database wasn't found next to "
                "it, so a new one has been started. Previously saved marks, TODOs "
                "and extractions for this file may not be available.")
        self.view.set_document(doc, self.config)
        # the reference pane shows the same document (read-only), whether or not
        # it's currently visible, so toggling it on is instant
        self.ref_view.set_document(doc, self.config)
        self.comment_panel.set_store(doc.store, self.config)
        self.todo_panel.set_store(doc.store, self.config, doc)
        self.wire_panel.set_document(doc, self.config)
        self.component_panel.set_document(doc, self.config)
        self.nav_panel.set_document(doc)
        self.tools_panel.set_default_pdf(path)
        self.page_spin.setRange(1, max(1, doc.page_count))
        self.page_total.setText(f" / {doc.page_count}")
        self.setWindowTitle(f"{__app_name__} — {os.path.basename(path)}")
        self._update_actions_enabled(True)
        # Edge case: the PDF opened for viewing, but its name can't back a
        # markup database (too long, or unsupported characters), so markup and
        # saving are turned off. Tell the user why and how to fix it.
        if not doc.sidecar_available:
            self._warn_no_sidecar(path)
        self.statusBar().showMessage(
            f"Opened {os.path.basename(path)} ({doc.page_count} pages, "
            f"{len(doc.store.all())} existing marks)", 6000)

    def save_markup(self):
        if self.document is None:
            return
        try:
            out = self.document.save()
            self.statusBar().showMessage(f"Saved {os.path.basename(out)}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Save failed", str(e))

    def save_as_fork(self):
        """Fork the current markup to a new working file and switch to editing it."""
        if self.document is None:
            return
        from .model.storage import original_pdf_path, sidecar_path
        base = os.path.splitext(
            os.path.basename(original_pdf_path(self.document.path)))[0]
        start_dir = os.path.dirname(os.path.abspath(self.document.path))
        suggested = os.path.join(start_dir, f"{base}-copy.pdf")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As — fork to a new working file", suggested, "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        def _key(p):
            return os.path.normcase(os.path.realpath(sidecar_path(p)))
        if _key(path) == _key(self.document.path):
            QMessageBox.information(
                self, "Same file",
                "That's the file you're already working on — choose a new name.")
            return
        try:
            self.document.save_as(path)
        except Exception as e:
            QMessageBox.warning(self, "Save As failed", str(e))
            return
        new_path = self.document.path
        self.tools_panel.set_default_pdf(new_path)
        self.setWindowTitle(f"{__app_name__} — {os.path.basename(new_path)}")
        self.statusBar().showMessage(
            f"Forked to {os.path.basename(new_path)} — now editing the copy", 6000)
        QMessageBox.information(
            self, "Forked to a new working file",
            f"Now working on “{os.path.basename(new_path)}”.\n"
            f"The original file is unchanged.")

    def export_pdf(self):
        if self.document is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export annotated PDF",
                                              "annotated.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            self.document.export_annotated_pdf(path)
            self.statusBar().showMessage(f"Exported {os.path.basename(path)}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def export_flat(self):
        if self.document is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export flattened PDF",
                                              "flattened.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            baked = self.document.export_flattened_pdf(path)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        if baked:
            self.statusBar().showMessage(
                f"Exported flattened {os.path.basename(path)}", 5000)
        else:
            QMessageBox.information(
                self, "Exported (not flattened)",
                "This PyMuPDF build can't flatten annotations, so an annotated "
                "copy was written instead.")

    def _new_printer(self):
        """Create a QPrinter for printing the drawing.

        Built in **ScreenResolution** mode on purpose: HighResolution queries the
        default printer's capabilities at construction, which on Windows pops a
        blocking "contacting printer…" dialog (and hangs on a slow/offline
        network printer) before the user can do anything. ScreenResolution
        doesn't contact the printer; we then raise the logical DPI so the output
        still prints at a decent resolution.
        """
        from PySide6.QtPrintSupport import QPrinter
        printer = QPrinter(QPrinter.ScreenResolution)
        printer.setResolution(300)
        printer.setDocName(os.path.basename(self.document.path))
        return printer

    def print_document(self):
        """Print the drawing (with its marks) straight through the system print
        dialog — the standard Windows printer popup: pick the printer, copies,
        orientation and page range, then print. (Use Print preview… to see the
        pages first.)"""
        if self.document is None:
            return
        from PySide6.QtPrintSupport import QPrintDialog
        printer = self._new_printer()
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("Print")
        if self.document.page_count:
            dlg.setMinMax(1, self.document.page_count)
            dlg.setOption(QPrintDialog.PrintPageRange, True)
        if dlg.exec() != QPrintDialog.Accepted:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._print_to(printer)
            self.statusBar().showMessage(
                f"Sent to {printer.printerName() or 'printer'}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Print failed", str(e))
        finally:
            QApplication.restoreOverrideCursor()

    def print_preview(self):
        """Optional: show the pages in a preview window, then print from there."""
        if self.document is None:
            return
        from PySide6.QtPrintSupport import QPrintPreviewDialog
        try:
            printer = self._new_printer()
            preview = QPrintPreviewDialog(printer, self)
            preview.setWindowTitle("Print preview")
            preview.resize(1000, 800)
            preview.paintRequested.connect(self._print_to)
            self._add_markups_toggle(preview)
            preview.exec()
        except Exception as e:
            QMessageBox.warning(self, "Print failed", str(e))

    def _add_markups_toggle(self, preview):
        """Add an 'Include markups' checkbox to the print-preview toolbar so the
        user can print the clean drawing or the drawing with the app's marks.
        Defaults to on (marks included)."""
        from PySide6.QtWidgets import QToolBar
        from PySide6.QtPrintSupport import QPrintPreviewWidget
        tb = preview.findChild(QToolBar)
        if tb is None:
            return
        act = tb.addAction("Include markups")
        act.setCheckable(True)
        act.setChecked(self._print_include_marks)
        act.setToolTip("Print the marks/notes you added on top of the drawing; "
                       "uncheck to print the clean drawing.")

        def _toggle(on):
            self._print_include_marks = on
            pv = preview.findChild(QPrintPreviewWidget)
            if pv is not None:
                pv.updatePreview()   # re-render with/without marks

        act.toggled.connect(_toggle)

    def _print_to(self, printer):
        """Paint each requested page onto ``printer``, fitted and centred on the
        sheet. Includes the app's markups unless ``_print_include_marks`` is off
        (the print-preview toggle). Kept separate from the dialog so it can be
        unit-tested against a PDF-output printer."""
        from PySide6.QtGui import QPainter
        work = self.document.annotated_fitz(
            with_marks=getattr(self, "_print_include_marks", True))
        try:
            first = printer.fromPage() or 1
            last = printer.toPage() or work.page_count
            first = max(1, first)
            last = min(work.page_count, last)
            painter = QPainter(printer)
            try:
                for n, i in enumerate(range(first - 1, last)):
                    if n:
                        printer.newPage()
                    img = self._render_print_image(work[i], printer)
                    target = painter.viewport()
                    scaled = img.scaled(target.width(), target.height(),
                                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    x = (target.width() - scaled.width()) // 2
                    y = (target.height() - scaled.height()) // 2
                    painter.drawImage(x, y, scaled)
            finally:
                painter.end()
        finally:
            work.close()

    @staticmethod
    def _render_print_image(page, printer, max_dpi: float = 200.0):
        """Rasterise one fitz page (with baked annotations) to a QImage, capped
        at ``max_dpi`` so a full-size E sheet stays a sane bitmap."""
        import fitz
        from PySide6.QtGui import QImage
        dpi = min(float(printer.resolution()), max_dpi)
        zoom = dpi / 72.0
        pm = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, annots=True)
        img = QImage(pm.samples, pm.width, pm.height, pm.stride,
                     QImage.Format_RGB888)
        return img.copy()   # detach from the pixmap buffer before it's freed

    def open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply()
            self.view.config = self.config
            self.ref_view.config = self.config
            if self.document is not None:
                self.document.ignore_patterns = self.config.ignore_patterns()
                self.comment_panel.refresh()
                self.todo_panel.refresh()
                self.view.rebuild_all_items()
                # keep the reference pane in step (e.g. "Show ignored" changes
                # which marks are drawn) — it renders the same marks
                self.ref_view.rebuild_all_items()
                # Bug 8: re-flag already-extracted component labels against the
                # (possibly edited) family codes / widths — no re-extract needed.
                if self.document.components:
                    from .extraction.component_parser import reclassify
                    reclassify(self.document.components, self.config.component_config())
                    self.document.set_components(self.document.components)
                    self.component_panel.set_document(self.document, self.config)

    # -- edit hooks ----------------------------------------------------------

    def _prompt_new_text(self, ann: Annotation, is_textbox: bool):
        """Synchronous prompt for a *new* comment/text box.

        Returns ``(accepted, text, todo)``; a cancel returns ``accepted=False``
        so the view discards the unplaced mark (never added to the document).
        """
        dlg = TextEditDialog(ann, self, is_textbox=is_textbox)
        if dlg.exec() == QDialog.Accepted:
            text, todo = dlg.values()
            fv = dlg.font_values()
            _apply_font(ann, fv)
            self._remember_text_style(fv)   # sticky style for the next new mark
            return True, text, todo
        return False, "", False

    def _remember_text_style(self, fv) -> None:
        """Feed a just-created text box / callout's colour, font and fill back into
        the tool defaults, so the next new one inherits them (never the text)."""
        if not fv:
            return
        t = self.view.tool
        t.text_color = tuple(fv["color"])
        t.font_size = fv["font_size"]
        t.bold = fv["bold"]
        t.italic = fv["italic"]
        if "fill_color" in fv:
            t.text_fill = tuple(fv["fill_color"]) if fv["fill_color"] else None
            t.text_fill_opacity = fv["fill_opacity"]
        # reflect the remembered values in the toolbar controls
        for w, val in ((self.font_size, int(t.font_size)),):
            w.blockSignals(True); w.setValue(val); w.blockSignals(False)
        for w, val in ((self.bold, t.bold), (self.italic, t.italic)):
            w.blockSignals(True); w.setChecked(val); w.blockSignals(False)
        self._update_color_btn()
        self._update_fill_btn()

    def _delete_annotation(self, ann: Annotation):
        """Delete a mark (already user-confirmed) via the undo stack."""
        self.view.push_command(RemoveAnnotationCommand(self.view, ann, "Delete comment"))

    def _edit_comment(self, ann: Annotation):
        self._edit_text(ann, is_textbox=False)

    def _edit_textbox(self, ann: Annotation):
        self._edit_text(ann, is_textbox=True)

    def _edit_text(self, ann: Annotation, is_textbox: bool):
        before = capture(ann)
        was_todo = ann.is_todo
        dlg = TextEditDialog(ann, self, is_textbox=is_textbox)
        if dlg.exec() == QDialog.Accepted:
            text, todo = dlg.values()
            ann.text = text
            ann.is_todo = todo
            _apply_font(ann, dlg.font_values())  # font size/color/bold/italic
            after = capture(ann)
            if after != before:
                self.view.push_command(
                    ModifyAnnotationCommand(self.view, ann, before, after,
                                            "Edit text"))
            elif todo != was_todo:
                self.document.store.update(ann)

    def _edit_fill(self, ann: Annotation):
        """Edit a rectangle's fill color + opacity (color + opacity slider)."""
        before = capture(ann)
        ok, color, opacity = FillDialog.ask(self, ann.fill_color, ann.fill_opacity,
                                            "Rectangle fill")
        if not ok:
            return
        ann.fill_color = color
        if color is not None:
            ann.fill_opacity = opacity
        after = capture(ann)
        if after != before:
            self.view.push_command(
                ModifyAnnotationCommand(self.view, ann, before, after, "Edit fill"))

    def _edit_author(self, ann: Annotation):
        """Change who a mark is by (double-clicking the By / Commenter column):
        confirm first, then edit the name.  Undoable; offers to rename every mark
        by that person when more than one shares the name."""
        from PySide6.QtWidgets import QInputDialog
        if self.document is None:
            return
        current = ann.author or ""
        same = [a for a in self.document.store.all() if (a.author or "") == current]
        scope_all = False
        if current and len(same) > 1:
            box = QMessageBox(self)
            box.setWindowTitle("Change commenter")
            box.setIcon(QMessageBox.Question)
            box.setText(f"Change the commenter name?\n\nCurrently “{current}”.")
            one_btn = box.addButton("This mark only", QMessageBox.AcceptRole)
            all_btn = box.addButton(f"All {len(same)} by “{current}”",
                                    QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            clicked = box.clickedButton()
            if clicked not in (one_btn, all_btn):
                return
            scope_all = clicked is all_btn
        else:
            resp = QMessageBox.question(
                self, "Change commenter",
                f"Change the commenter name for this {ann.kind}?\n\n"
                f"Currently “{current or '(none)'}”.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if resp != QMessageBox.Yes:
                return
        new, ok = QInputDialog.getText(self, "Commenter name", "Name:", text=current)
        if not ok:
            return
        new = new.strip()
        if new == current:
            return
        targets = same if scope_all else [ann]
        self.view.undo_stack.beginMacro("Change commenter")
        try:
            for a in targets:
                before = capture(a)
                a.author = new
                after = capture(a)
                if after != before:
                    self.view.push_command(ModifyAnnotationCommand(
                        self.view, a, before, after, "Change commenter"))
        finally:
            self.view.undo_stack.endMacro()

    # -- navigation ----------------------------------------------------------

    def _jump_to(self, obj):
        # obj is an Annotation, or a WireNumber / ComponentLabel (which carry a
        # page + x/y of their FIRST occurrence after dedupe).
        ann = obj if isinstance(obj, Annotation) else None
        if ann is not None:
            self.tabs.setCurrentWidget(self.view)
            self.view.flash_annotation(ann)
            return
        page = getattr(obj, "page", None)
        if page is None:
            return
        self.tabs.setCurrentWidget(self.view)
        x, y = getattr(obj, "x", None), getattr(obj, "y", None)
        if x is not None and y is not None and (x or y):
            self.view.go_to_location(int(page), float(x), float(y))
        else:
            self.view.go_to_page(int(page))

    def _nav_to_page(self, page_no):
        """Picking a page/bookmark in the Navigation pane jumps the Viewer to it
        — switching to the Viewer tab first if the user is on another tab."""
        self.tabs.setCurrentWidget(self.view)
        self.view.go_to_page(page_no)

    def _reveal_in_panel(self, ann, target):
        """Jump from a PDF mark to its row in the TODO list or comment sidebar."""
        if target == "todo":
            self.tabs.setCurrentWidget(self.todo_panel)
            self.todo_panel.reveal(ann)
        else:
            self.comment_dock.setVisible(True)
            self.comment_dock.raise_()
            self.comment_panel.reveal(ann)

    def _on_page_changed(self, page_no):
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page_no + 1)
        self.page_spin.blockSignals(False)

    def _update_actions_enabled(self, on: bool):
        # Markup + persistence need a working sidecar. When a document is open
        # but its filename can't back one, keep view/find/nav (and PDF tools)
        # alive but grey out saving, exporting and the drawing tools.
        avail = (getattr(self.document, "sidecar_available", True)
                 if self.document is not None else True)
        markup = on and avail
        for a in (self.act_save, self.act_save_as, self.act_export_pdf,
                  self.act_export_flat):
            a.setEnabled(markup)
        # Printing is a view operation (it just rasterises the pages + marks), so
        # it stays available even when the file has no sidecar.
        self.act_print.setEnabled(on)
        self.act_print_preview.setEnabled(on)
        # Only *block* the tools when a document is open without a sidecar;
        # otherwise leave them as-is (startup with no document keeps them ready).
        self._set_markup_tools_enabled(not (on and not avail))

    def _set_markup_tools_enabled(self, enabled: bool):
        """Enable/disable the drawing tools and their styling widgets. The
        Select tool always stays available so the user can still click marks."""
        for tool, act in getattr(self, "_tool_actions", {}).items():
            act.setEnabled(enabled or tool == T.TOOL_SELECT)
        for w in (self.color_btn, self.fill_btn, self.pen_width, self.font_size,
                  self.bold, self.italic):
            w.setEnabled(enabled)
        if not enabled:
            self._activate_tool(T.TOOL_SELECT)   # snap off any drawing tool

    def _warn_no_sidecar(self, path):
        """Explain why markup is greyed out for a file whose name can't back a
        markup-database sidecar, and how to fix it."""
        from .model.storage import sidecar_path
        sc_name = os.path.basename(sidecar_path(path))
        QMessageBox.warning(
            self, "Markup turned off for this file",
            f"“{os.path.basename(path)}” opened for viewing, but its markup "
            f"tools are turned off.\n\n"
            f"Its filename is too long or contains characters that can't be "
            f"used to create the markup database it needs "
            f"(“{sc_name}”), so drawing marks, notes, TODOs, wire/component "
            f"caching and saving aren't available.\n\n"
            f"You can still view, search, navigate and use the PDF tools.\n\n"
            f"To turn markup back on, rename the file to something shorter and "
            f"simpler — avoid very long names and the characters "
            f"\\ / : * ? \" < > | — then open it again.")

    def showEvent(self, event):
        super().showEvent(event)
        # Force the dock layout to settle once the window is on screen so the
        # nav/comment separators are draggable from the start (otherwise the
        # splitter only becomes active after the dock is hidden and reshown).
        # Skip the default sizing when a saved layout was restored.
        if not getattr(self, "_docks_sized", False):
            self._docks_sized = True
            if not getattr(self, "_state_restored", False):
                QTimer.singleShot(0, self._init_dock_sizes)

    def _init_dock_sizes(self):
        try:
            self.resizeDocks([self.nav_dock, self.comment_dock], [260, 320],
                             Qt.Horizontal)
        except Exception:
            pass

    # -- dock layout persistence (Visual-Studio-style) ----------------------

    def _restore_ui_state(self):
        """Apply the window geometry + dock layout saved last session."""
        self._state_restored = False
        try:
            geo = self.config.s.value("ui/geometry")
            state = self.config.s.value("ui/window_state")
            if geo:
                self.restoreGeometry(geo)
            if state and self.restoreState(state, _UI_STATE_VERSION):
                self._state_restored = True
        except Exception:
            self._state_restored = False

    def _save_ui_state(self):
        try:
            self.config.s.setValue("ui/geometry", self.saveGeometry())
            self.config.s.setValue("ui/window_state",
                                   self.saveState(_UI_STATE_VERSION))
            self.config.s.sync()
        except Exception:
            pass

    def _toggle_reference_view(self):
        """Show/hide the read-only second view of the current document."""
        showing = not self.ref_dock.isVisible()
        if showing:
            # catch up if a document was opened while the pane was hidden
            if self.document is not None and self.ref_view.document is not self.document:
                self.ref_view.set_document(self.document, self.config)
            self.ref_dock.show()
            self.ref_dock.raise_()
        else:
            self.ref_dock.hide()

    def reset_layout(self):
        """Restore the panes to their default docked arrangement — re-docking
        any floated tab or sidebar and re-tabbing the main panes together."""
        if getattr(self, "_default_state", None) is not None:
            self.restoreState(self._default_state, _UI_STATE_VERSION)
        for d in [self.nav_dock, self.comment_dock] + getattr(self, "main_docks", []):
            d.setFloating(False)
            d.show()
        self.tabs.setCurrentWidget(self.view)
        self._init_dock_sizes()

    def closeEvent(self, event):
        self._save_ui_state()            # remember the dock layout + geometry
        try:
            self.wire_panel.shutdown()   # stop any running extraction thread
        except Exception:
            pass
        try:
            self.component_panel.shutdown()
        except Exception:
            pass
        try:
            self.tools_panel.grid.close_doc()
        except Exception:
            pass
        if self.document is not None:
            try:
                self.document.close()
            except Exception:
                pass
        super().closeEvent(event)
