"""Wire Numbers tab (Phase 6 + 7).

Runs the extract -> parse -> classify pipeline, shows a spot-checkable table
(sheet, rung, wire-idx, label, type, page, count, source), and drives the
xlsx/csv exports in both per-sheet and single-file modes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QLineEdit, QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QHeaderView, QAbstractItemView,
)

from ..extraction.text_extract import collect_tokens
from ..extraction.wire_parser import (
    WireParser, dedupe, TYPE_CONFORMING, TYPE_FIXED, TYPE_JUMPER,
    FLAG_SHEET_MISMATCH,
)
from ..export.wire_export import (
    export_single_file, export_per_sheet, WireExportOptions,
    SORT_IN_ORDER, SORT_NUMERICAL, SORT_BY_SHEET,
)

_COLS = ["✓", "Label", "Sheet", "Rung", "Idx", "Type", "Pg", "Count", "Source", "Flags"]
_TYPE_COLORS = {
    TYPE_CONFORMING: "#1b7f3a",
    TYPE_FIXED: "#b8860b",
    TYPE_JUMPER: "#8a8a8a",
}


class WirePanel(QWidget):
    activated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = None
        self.config = None
        self.wires = []
        self._build_ui()

    # -- ui ------------------------------------------------------------------

    def _build_ui(self):
        lay = QVBoxLayout(self)

        # extraction row
        top = QHBoxLayout()
        self.btn_extract = QPushButton("Extract wire numbers")
        self.btn_extract.clicked.connect(self.extract)
        self.status = QLabel("Open a PDF, then extract.")
        top.addWidget(self.btn_extract)
        top.addWidget(self.status, 1)
        lay.addLayout(top)

        # filter row
        filt = QHBoxLayout()
        self.search = QLineEdit(placeholderText="Search label…")
        self.search.textChanged.connect(self._apply_filter)
        self.show_conforming = QCheckBox("Conforming"); self.show_conforming.setChecked(True)
        self.show_fixed = QCheckBox("Fixed/OEM"); self.show_fixed.setChecked(True)
        self.show_jumpers = QCheckBox("Jumpers"); self.show_jumpers.setChecked(False)
        for cb in (self.show_conforming, self.show_fixed, self.show_jumpers):
            cb.stateChanged.connect(self._apply_filter)
        filt.addWidget(QLabel("Show:"))
        filt.addWidget(self.show_conforming)
        filt.addWidget(self.show_fixed)
        filt.addWidget(self.show_jumpers)
        filt.addWidget(self.search, 1)
        lay.addLayout(filt)

        # table
        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_double)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        lay.addWidget(self.table, 1)

        # export row
        exp = QHBoxLayout()
        self.mode = QComboBox(); self.mode.addItems(["Single file (~sheet~)", "Per-sheet files"])
        self.fmt = QComboBox(); self.fmt.addItems(["xlsx", "csv"])
        self.sort = QComboBox(); self.sort.addItems(["Numerical", "In drawing order", "By sheet"])
        self.labels_per = QSpinBox(); self.labels_per.setRange(1, 99); self.labels_per.setValue(2)
        self.dedupe = QCheckBox("Dedupe"); self.dedupe.setChecked(True)
        self.labels_only = QCheckBox("Labels only"); self.labels_only.setTristate(False)
        self.btn_export = QPushButton("Export…")
        self.btn_export.clicked.connect(self.export)
        exp.addWidget(QLabel("Mode:")); exp.addWidget(self.mode)
        exp.addWidget(QLabel("Fmt:")); exp.addWidget(self.fmt)
        exp.addWidget(QLabel("Sort:")); exp.addWidget(self.sort)
        exp.addWidget(QLabel("Labels/wire:")); exp.addWidget(self.labels_per)
        exp.addWidget(self.dedupe)
        exp.addWidget(self.labels_only)
        exp.addStretch(1)
        exp.addWidget(self.btn_export)
        lay.addLayout(exp)

    # -- wiring --------------------------------------------------------------

    def set_document(self, document, config=None):
        self.document = document
        self.config = config
        self.wires = list(getattr(document, "wires", []) or [])
        if self.wires:
            self._populate()
            self.status.setText(f"{len(self.wires)} cached wire numbers (re-extract to refresh).")
        else:
            self.table.setRowCount(0)
            self.status.setText("Open a PDF, then extract.")

    # -- extraction ----------------------------------------------------------

    def extract(self):
        if self.document is None:
            QMessageBox.information(self, "No document", "Open a PDF first.")
            return
        cfg = self.config.wire_config() if self.config else None
        ocr_enabled = bool(self.config and self.config.ocr_enabled)
        self.status.setText("Extracting…")
        self.btn_extract.setEnabled(False)
        try:
            tokens = collect_tokens(self.document.fitz_doc, ocr_enabled=ocr_enabled,
                                    ocr_zoom=3.0)
            parser = WireParser(cfg)
            occurrences = parser.parse(tokens)
            self.wires = dedupe(occurrences)
            self.document.set_wires(self.wires)
            self._populate()
            n_conf = sum(1 for w in self.wires if w.wire_type == TYPE_CONFORMING)
            n_fix = sum(1 for w in self.wires if w.wire_type == TYPE_FIXED)
            n_jmp = sum(1 for w in self.wires if w.wire_type == TYPE_JUMPER)
            self.status.setText(
                f"{len(self.wires)} unique labels — "
                f"{n_conf} conforming, {n_fix} fixed/OEM, {n_jmp} jumpers "
                f"({len(tokens)} tokens scanned).")
        except Exception as e:
            QMessageBox.warning(self, "Extraction failed", str(e))
            self.status.setText("Extraction failed.")
        finally:
            self.btn_extract.setEnabled(True)

    # -- table ---------------------------------------------------------------

    def _populate(self):
        self.table.setSortingEnabled(False)
        self.table.itemChanged.disconnect(self._on_item_changed)
        self.table.setRowCount(0)
        for w in self.wires:
            r = self.table.rowCount()
            self.table.insertRow(r)
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Checked if w.included else Qt.Unchecked)
            chk.setData(Qt.UserRole, w)
            self.table.setItem(r, 0, chk)
            vals = [w.label, _i(w.sheet), _i(w.rung), _i(w.wire_index), w.wire_type,
                    str(w.page + 1), str(w.count), w.source,
                    "mismatch" if FLAG_SHEET_MISMATCH in w.flags else ""]
            for c, v in enumerate(vals, start=1):
                it = QTableWidgetItem(v)
                if c == 5:  # type col
                    from PySide6.QtGui import QColor
                    it.setForeground(QColor(_TYPE_COLORS.get(w.wire_type, "#000")))
                # numeric sort for sheet/rung/idx/page/count
                if c in (2, 3, 4, 6, 7):
                    try:
                        it.setData(Qt.EditRole, int(v))
                    except (ValueError, TypeError):
                        pass
                self.table.setItem(r, c, it)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setSortingEnabled(True)
        self._apply_filter()

    def _apply_filter(self):
        needle = self.search.text().lower().strip()
        allowed = set()
        if self.show_conforming.isChecked():
            allowed.add(TYPE_CONFORMING)
        if self.show_fixed.isChecked():
            allowed.add(TYPE_FIXED)
        if self.show_jumpers.isChecked():
            allowed.add(TYPE_JUMPER)
        for r in range(self.table.rowCount()):
            w = self.table.item(r, 0).data(Qt.UserRole)
            show = w.wire_type in allowed and (not needle or needle in w.label.lower())
            self.table.setRowHidden(r, not show)

    def _on_item_changed(self, item):
        if item.column() != 0:
            return
        w = item.data(Qt.UserRole)
        if w is not None:
            w.included = item.checkState() == Qt.Checked

    def _on_double(self, row, _col):
        w = self.table.item(row, 0).data(Qt.UserRole)
        if w is not None:
            self.activated.emit(w)

    # -- export --------------------------------------------------------------

    def _build_options(self) -> WireExportOptions:
        sort = {0: SORT_NUMERICAL, 1: SORT_IN_ORDER, 2: SORT_BY_SHEET}[self.sort.currentIndex()]
        return WireExportOptions(
            fmt=self.fmt.currentText(),
            labels_per_wire=self.labels_per.value(),
            sort=sort,
            include_fixed=self.show_fixed.isChecked(),
            include_jumpers=self.show_jumpers.isChecked(),
            dedupe=self.dedupe.isChecked(),
            only_included=True,
            labels_only=self.labels_only.isChecked() or None,
        )

    def export(self):
        if not self.wires:
            QMessageBox.information(self, "Nothing to export", "Extract wire numbers first.")
            return
        opts = self._build_options()
        single = self.mode.currentIndex() == 0
        try:
            if single:
                ext = "xlsx" if opts.fmt == "xlsx" else "csv"
                path, _ = QFileDialog.getSaveFileName(
                    self, "Export wire numbers", f"wires.{ext}",
                    f"Spreadsheet (*.{ext})")
                if not path:
                    return
                export_single_file(self.wires, path, opts)
                QMessageBox.information(self, "Exported", f"Wrote {path}")
            else:
                out_dir = QFileDialog.getExistingDirectory(self, "Choose output folder")
                if not out_dir:
                    return
                paths = export_per_sheet(self.wires, out_dir, opts)
                QMessageBox.information(self, "Exported",
                                        f"Wrote {len(paths)} file(s) to {out_dir}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))


def _i(v):
    return "" if v is None else str(v)
