"""The "PDF Tools" tab: a launcher for the merged PDF utilities.

Grouped cards open modern dialogs (file→file ops) or viewer-driven wizards
(sheet-number split, crop/extract).  The same launch methods back the Tools
menu in the main window.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QGridLayout, QLabel,
    QPushButton, QScrollArea,
)

from ..tools import dialogs as dlg
from ..tools.wizards import SheetNumberWizard, CropWizard


class ToolsPanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._wizard = None
        self._build_ui()

    # tool catalog: (group, label, description, handler-attr)
    def _catalog(self):
        return [
            ("Organize", [
                ("Split into pages", "One file per page (named by page number).", self.open_split_pages),
                ("Combine PDFs", "Merge several PDFs into one (drag to order).", self.open_combine),
                ("Insert PDF", "Insert one PDF into another at a position.", self.open_insert),
                ("Swap a page", "Replace a single page with another PDF page.", self.open_swap),
                ("Delete pages", "Remove pages by range (e.g. 1,3,5-7).", self.open_delete),
                ("Rotate", "Rotate all or selected pages 90/180/270°.", self.open_rotate),
            ]),
            ("Sheet numbers", [
                ("Split by sheet number…", "Guided wizard: box the title-block sheet "
                 "number and split, naming each file by its sheet.", self.start_sheet_wizard),
            ]),
            ("Convert & extract", [
                ("PDF → Word", "Convert a PDF to an editable .docx.", self.open_convert),
                ("Crop / extract…", "Box regions → PNGs, and optionally a TAG/"
                 "DESCRIPTION table via Claude.", self.start_crop_wizard),
            ]),
        ]

    def _build_ui(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        for group, items in self._catalog():
            gb = QGroupBox(group)
            grid = QGridLayout(gb)
            grid.setColumnStretch(1, 1)
            for r, (label, desc, handler) in enumerate(items):
                btn = QPushButton(label)
                btn.setMinimumWidth(190)
                btn.clicked.connect(handler)
                d = QLabel(desc); d.setWordWrap(True); d.setStyleSheet("color: gray;")
                grid.addWidget(btn, r, 0)
                grid.addWidget(d, r, 1)
            lay.addWidget(gb)
        lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # -- helpers -------------------------------------------------------------

    def _default_pdf(self):
        doc = getattr(self.window, "document", None)
        return doc.path if doc is not None else ""

    # -- file→file dialogs ---------------------------------------------------

    def open_split_pages(self):
        dlg.SplitPagesDialog("Split into pages", self.window, self._default_pdf()).exec()

    def open_combine(self):
        dlg.CombineDialog("Combine PDFs", self.window, self._default_pdf()).exec()

    def open_insert(self):
        dlg.InsertDialog("Insert PDF", self.window, self._default_pdf()).exec()

    def open_swap(self):
        dlg.SwapDialog("Swap a page", self.window, self._default_pdf()).exec()

    def open_delete(self):
        dlg.DeleteDialog("Delete pages", self.window, self._default_pdf()).exec()

    def open_rotate(self):
        dlg.RotateDialog("Rotate", self.window, self._default_pdf()).exec()

    def open_convert(self):
        dlg.ConvertDialog("PDF → Word", self.window, self._default_pdf()).exec()

    # -- wizards (need the open document + viewer) ---------------------------

    def start_sheet_wizard(self):
        self._wizard = SheetNumberWizard(self.window)
        self._wizard.start()

    def start_crop_wizard(self):
        self._wizard = CropWizard(self.window)
        self._wizard.start()
