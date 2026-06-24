"""Main window: Viewer | TODO | Wire Numbers tabs, toolbar, comment dock,
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
    QApplication,
)

from . import __app_name__, __version__, __copyright__, app_icon
from .config import AppConfig
from .model.document import Document
from .model.annotations import Annotation
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
        self.setWindowTitle("Edit text box" if is_textbox else "Edit comment")
        lay = QVBoxLayout(self)
        self.edit = QPlainTextEdit(ann.text or "")
        self.edit.setMinimumSize(320, 120)
        self.edit.installEventFilter(self)  # Ctrl/Shift+Enter -> OK
        lay.addWidget(self.edit)

        # font styling — only meaningful for on-page text boxes
        if is_textbox:
            frow = QHBoxLayout()
            self.size_spin = QSpinBox(); self.size_spin.setRange(4, 96)
            self.size_spin.setValue(int(ann.font_size))
            self.bold_cb = QCheckBox("B"); self.bold_cb.setChecked(ann.bold)
            self.italic_cb = QCheckBox("I"); self.italic_cb.setChecked(ann.italic)
            self.color_btn = QPushButton("Font color")
            self.color_btn.clicked.connect(self._pick_color)
            self._update_color_swatch()
            frow.addWidget(QLabel("Size:")); frow.addWidget(self.size_spin)
            frow.addWidget(self.bold_cb); frow.addWidget(self.italic_cb)
            frow.addWidget(self.color_btn); frow.addStretch(1)
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
        }


def _apply_font(ann: Annotation, fv) -> None:
    if not fv:
        return
    ann.font_size = fv["font_size"]
    ann.bold = fv["bold"]
    ann.italic = fv["italic"]
    ann.color = tuple(fv["color"])


# --- settings dialog --------------------------------------------------------


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.resize(520, 560)
        lay = QVBoxLayout(self)

        # identity
        gb_id = QGroupBox("Identity")
        f = QFormLayout(gb_id)
        self.name = QLineEdit(config.your_name)
        f.addRow("Your name (commenter):", self.name)
        lay.addWidget(gb_id)

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
        fw.addRow("Sheet width:", self.sheet_w)
        fw.addRow("Rung width:", self.rung_w)
        fw.addRow("Wire-index width:", self.wire_w)
        fw.addRow(self.zero_pad)
        fw.addRow("Full-label regex:", self.regex)
        fw.addRow(self.cross_check)
        lay.addWidget(gb_w)

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
        lay.addWidget(gb_cmp)

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
        lay.addWidget(gb_e)

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
        lay.addWidget(gb_c)

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
        lay.addWidget(gb_a)
        self._on_ai_toggled(self.ai.isChecked())
        self._refresh_api_status()

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


# --- main window ------------------------------------------------------------


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
        # together, or float them out of the window.
        self.setDockOptions(
            QMainWindow.AnimatedDocks | QMainWindow.AllowNestedDocks
            | QMainWindow.AllowTabbedDocks | QMainWindow.GroupedDragging)
        self.config = AppConfig()
        self.document = None

        self._progress("Preparing the canvas…", 62)
        self.view = PdfView(self)
        self.view.config = self.config
        self.view.requestCommentEdit.connect(self._edit_comment)
        self.view.requestTextEdit.connect(self._edit_textbox)
        self.view.pageChanged.connect(self._on_page_changed)
        self.view.requestTool.connect(self._activate_tool)
        self.view.requestOpen.connect(self.load_document)   # drag/drop a PDF
        # synchronous prompt used when *creating* a new comment / text box
        self.view.new_text_prompt = self._prompt_new_text
        # synchronous prompt when a drawing tool clicks an existing mark
        self.view.existing_mark_prompt = self._prompt_existing_mark

        self._progress("Setting up the wire-number engine…", 75)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.view, "Viewer")
        self.todo_panel = TodoPanel()
        self.wire_panel = WirePanel()
        self.component_panel = ComponentPanel()
        self.tools_panel = ToolsPanel(self)
        self.tabs.addTab(self.todo_panel, "TODO")
        self.tabs.addTab(self.wire_panel, "Wire Numbers")
        self.tabs.addTab(self.component_panel, "Component Labels")
        self.tabs.addTab(self.tools_panel, "PDF Tools")
        self.setCentralWidget(self.tabs)

        self.todo_panel.activated.connect(self._jump_to)
        self.component_panel.activated.connect(self._jump_to)

        self._progress("Building the comment & TODO panels…", 85)
        # navigation dock (pages + bookmarks) on the left
        self.nav_panel = NavPanel()
        self.nav_panel.pageActivated.connect(self.view.go_to_page)
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
        dock = QDockWidget("Comments", self)
        dock.setObjectName("CommentDock")
        dock.setWidget(self.comment_panel)
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.comment_dock = dock

        self._progress("Assembling the toolbar…", 92)
        self.setStatusBar(QStatusBar())
        self._build_menu()
        self._build_toolbar()
        self._update_actions_enabled(False)

        # Remember the freshly-built default arrangement (for "Reset panel
        # layout"), then apply whatever layout the user left last session.
        self._default_state = self.saveState()
        self._restore_ui_state()

    # -- menu / toolbar ------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()
        m_file = mb.addMenu("&File")
        self.act_open = m_file.addAction("&Open PDF…", self.open_pdf, QKeySequence.Open)
        self.act_save = m_file.addAction("&Save markup", self.save_markup, QKeySequence.Save)
        self.act_export_pdf = m_file.addAction("Export annotated PDF…", self.export_pdf)
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
        tool_defs = [
            (T.TOOL_SELECT, "Select"), (T.TOOL_HIGHLIGHT, "Highlight"),
            (T.TOOL_PEN, "Pen"), (T.TOOL_ERASER, "Eraser"),
            (T.TOOL_COMMENT, "Comment"), (T.TOOL_TEXTBOX, "Text box"),
            (T.TOOL_RECT, "Rectangle"), (T.TOOL_ARROW, "Arrow"),
        ]
        for tool, label in tool_defs:
            act = QAction(label, self, checkable=True)
            act.setData(tool)
            act.triggered.connect(lambda _=False, t=tool: self._set_tool(t))
            self.tool_group.addAction(act)
            tb.addAction(act)
            if tool == T.TOOL_SELECT:
                act.setChecked(True)
        tb.addSeparator()

        # color + widths
        self.color_btn = QPushButton("Color")
        self.color_btn.clicked.connect(self._pick_color)
        tb.addWidget(self.color_btn)
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

        # zoom / page nav
        tb.addAction("−", self.view.zoom_out)
        tb.addAction("+", self.view.zoom_in)
        tb.addAction("Fit W", self.view.fit_width)
        tb.addAction("Fit P", self.view.fit_page)
        tb.addWidget(QLabel("  Page "))
        self.page_spin = QSpinBox(); self.page_spin.setRange(1, 1)
        self.page_spin.valueChanged.connect(lambda v: self.view.go_to_page(v - 1))
        tb.addWidget(self.page_spin)
        self.page_total = QLabel(" / 0")
        tb.addWidget(self.page_total)
        self._update_color_btn()

    # -- tool handling -------------------------------------------------------

    def _set_tool(self, tool):
        from PySide6.QtWidgets import QGraphicsView, QGraphicsItem
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
            T.TOOL_ARROW: "shape_color",
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
        self.view.set_document(doc, self.config)
        self.comment_panel.set_store(doc.store, self.config)
        self.todo_panel.set_store(doc.store, self.config)
        self.wire_panel.set_document(doc, self.config)
        self.component_panel.set_document(doc, self.config)
        self.nav_panel.set_document(doc)
        self.tools_panel.set_default_pdf(path)
        self.page_spin.setRange(1, max(1, doc.page_count))
        self.page_total.setText(f" / {doc.page_count}")
        self.setWindowTitle(f"{__app_name__} — {os.path.basename(path)}")
        self._update_actions_enabled(True)
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

    def open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec() == QDialog.Accepted:
            dlg.apply()
            self.view.config = self.config
            if self.document is not None:
                self.document.ignore_patterns = self.config.ignore_patterns()
                self.comment_panel.refresh()
                self.todo_panel.refresh()
                self.view.rebuild_all_items()

    # -- edit hooks ----------------------------------------------------------

    def _prompt_new_text(self, ann: Annotation, is_textbox: bool):
        """Synchronous prompt for a *new* comment/text box.

        Returns ``(accepted, text, todo)``; a cancel returns ``accepted=False``
        so the view discards the unplaced mark (never added to the document).
        """
        dlg = TextEditDialog(ann, self, is_textbox=is_textbox)
        if dlg.exec() == QDialog.Accepted:
            text, todo = dlg.values()
            _apply_font(ann, dlg.font_values())
            return True, text, todo
        return False, "", False

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

    # -- navigation ----------------------------------------------------------

    def _jump_to(self, obj):
        # obj is an Annotation or a WireNumber
        ann = obj if isinstance(obj, Annotation) else None
        if ann is not None:
            self.tabs.setCurrentWidget(self.view)
            self.view.flash_annotation(ann)
        else:
            page = getattr(obj, "page", None)
            if page is not None:
                self.tabs.setCurrentWidget(self.view)
                self.view.go_to_page(page)

    def _on_page_changed(self, page_no):
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page_no + 1)
        self.page_spin.blockSignals(False)

    def _update_actions_enabled(self, on: bool):
        for a in (self.act_save, self.act_export_pdf):
            a.setEnabled(on)

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
            if state and self.restoreState(state):
                self._state_restored = True
        except Exception:
            self._state_restored = False

    def _save_ui_state(self):
        try:
            self.config.s.setValue("ui/geometry", self.saveGeometry())
            self.config.s.setValue("ui/window_state", self.saveState())
            self.config.s.sync()
        except Exception:
            pass

    def reset_layout(self):
        """Restore the panes to their default docked arrangement."""
        if getattr(self, "_default_state", None) is not None:
            self.restoreState(self._default_state)
        for d in (self.nav_dock, self.comment_dock):
            d.setFloating(False)
            d.show()
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
