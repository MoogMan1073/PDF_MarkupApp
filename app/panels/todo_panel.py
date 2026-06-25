"""TODO tab (Phase 5).

Top-level tab listing every TODO-flagged mark with a done/undone checkbox,
inline-editable text, page, commenter, date and tag, plus group-by, filter,
sort, drag-reorder and Markdown / DOCX export.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,
    QAbstractItemView,
)

from ..model.annotations import Annotation
from ..export.todo_export import (
    export_markdown, export_docx, GROUP_SHEET, GROUP_COMMENTER, GROUP_NONE,
)

_DATE = lambda iso: (iso or "")[:16].replace("T", " ")


class TodoPanel(QWidget):
    activated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = None
        self.config = None
        self._loading = False
        self._sort_col = None                  # None -> natural (order, page)
        self._sort_order = Qt.AscendingOrder
        self._done_width_user = None           # honoured if the user resizes col 0
        self._setting_done_width = False
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.group_by = QComboBox()
        self.group_by.addItems(["Group: Sheet", "Group: Commenter", "No grouping"])
        self.group_by.currentIndexChanged.connect(self.refresh)
        self.search = QLineEdit(placeholderText="Filter…")
        self.search.textChanged.connect(self.refresh)
        self.hide_done = QPushButton("Hide done")
        self.hide_done.setCheckable(True)
        self.hide_done.toggled.connect(self.refresh)
        self.btn_md = QPushButton("Export Markdown…")
        self.btn_md.clicked.connect(self._export_md)
        self.btn_docx = QPushButton("Export DOCX…")
        self.btn_docx.clicked.connect(self._export_docx)
        bar.addWidget(self.group_by)
        bar.addWidget(self.search, 1)
        bar.addWidget(self.hide_done)
        bar.addWidget(self.btn_md)
        bar.addWidget(self.btn_docx)
        lay.addLayout(bar)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["Done", "Text", "Pg", "Commenter", "Date", "Tag"])
        self.tree.setRootIsDecorated(self.group_by.currentIndex() < 2)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(self._on_double)
        self.tree.setColumnWidth(0, 44)
        self.tree.setColumnWidth(1, 320)
        # clickable headers sort items within each group (grouping stays primary)
        hdr = self.tree.header()
        hdr.setSectionsClickable(True)
        hdr.setSortIndicatorShown(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        hdr.sectionResized.connect(self._on_section_resized)
        lay.addWidget(self.tree, 1)

        self.count_label = QLabel("")
        lay.addWidget(self.count_label)

    # -- wiring --------------------------------------------------------------

    def set_store(self, store, config=None):
        self.store = store
        self.config = config
        store.add_listener(lambda *_: QTimer.singleShot(0, self.refresh))
        self.refresh()

    def _group_mode(self):
        return [GROUP_SHEET, GROUP_COMMENTER, GROUP_NONE][self.group_by.currentIndex()]

    # column -> sort key over an Annotation
    _SORT_KEYS = {
        0: lambda a: (a.todo_done,),
        1: lambda a: ((a.text or "").lower(),),
        2: lambda a: (a.page,),
        3: lambda a: ((a.author or "").lower(),),
        4: lambda a: (a.created,),
        5: lambda a: (",".join(a.tags).lower(),),
    }

    def _on_header_clicked(self, col):
        if col == self._sort_col:
            self._sort_order = (Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder
                                else Qt.AscendingOrder)
        else:
            self._sort_col = col
            self._sort_order = Qt.AscendingOrder
        self.tree.header().setSortIndicator(self._sort_col, self._sort_order)
        self.refresh()

    def _sort_within_group(self, items):
        """Apply the active column sort to one group's items (grouping is primary)."""
        if self._sort_col is None:
            return items
        key = self._SORT_KEYS.get(self._sort_col)
        if key is None:
            return items
        return sorted(items, key=key,
                      reverse=self._sort_order == Qt.DescendingOrder)

    def _todos(self):
        if self.store is None:
            return []
        show_ignored = bool(self.config and self.config.show_ignored)
        items = self.store.todos(show_ignored)
        needle = self.search.text().lower().strip()
        if needle:
            items = [a for a in items if needle in (a.text or "").lower()]
        if self.hide_done.isChecked():
            items = [a for a in items if not a.todo_done]
        items.sort(key=lambda a: (a.order, a.page, a.created))
        return items

    def refresh(self):
        if self.store is None:
            return
        self._loading = True
        self.tree.clear()
        todos = self._todos()
        mode = self._group_mode()
        self.tree.setRootIsDecorated(mode != GROUP_NONE)

        groups = {}
        order = []
        for a in todos:
            if mode == GROUP_SHEET:
                k = f"Sheet {a.page + 1}"
            elif mode == GROUP_COMMENTER:
                k = a.author or "(unknown)"
            else:
                k = None
            if k not in groups:
                groups[k] = []
                order.append(k)
            groups[k].append(a)

        for k in order:
            parent = self.tree
            if k is not None:
                node = QTreeWidgetItem([k])
                node.setFirstColumnSpanned(True)
                node.setFlags(Qt.ItemIsEnabled)
                self.tree.addTopLevelItem(node)
                node.setExpanded(True)
                parent = node
            for a in self._sort_within_group(groups[k]):
                self._make_row(parent, a)

        self.count_label.setText(
            f"{sum(len(v) for v in groups.values())} TODO(s), "
            f"{sum(1 for a in todos if a.todo_done)} done")
        self._adjust_done_width([k for k in order if k is not None])
        self._loading = False

    # -- "Done" column auto-width (fits group names) -------------------------

    def _on_section_resized(self, idx, _old, new):
        if idx == 0 and not self._setting_done_width:
            self._done_width_user = new  # remember a manual adjustment

    def _adjust_done_width(self, group_names):
        from PySide6.QtGui import QFontMetrics
        if group_names:
            fm = QFontMetrics(self.tree.font())
            text_w = max(fm.horizontalAdvance(str(n)) for n in group_names)
            min_w = text_w + self.tree.indentation() + 28
        else:
            min_w = 44  # checkbox-only width when not grouping
        target = max(int(min_w), self._done_width_user or 0)
        self._setting_done_width = True
        self.tree.setColumnWidth(0, target)
        self._setting_done_width = False

    def _make_row(self, parent, a: Annotation):
        it = QTreeWidgetItem(["", a.text or a.snippet(), str(a.page + 1),
                              a.author or "", _DATE(a.created),
                              ",".join(a.tags)])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
        it.setCheckState(0, Qt.Checked if a.todo_done else Qt.Unchecked)
        it.setData(0, Qt.UserRole, a)
        if isinstance(parent, QTreeWidget):
            parent.addTopLevelItem(it)
        else:
            parent.addChild(it)

    # -- interaction ---------------------------------------------------------

    def _on_item_changed(self, item, col):
        if self._loading:
            return
        a = item.data(0, Qt.UserRole)
        if a is None:
            return
        changed = False
        done = item.checkState(0) == Qt.Checked
        if done != a.todo_done:
            a.todo_done = done
            changed = True
        new_text = item.text(1)
        if col == 1 and new_text != a.text:
            a.text = new_text
            changed = True
        new_tags = [t.strip() for t in item.text(5).split(",") if t.strip()]
        if col == 5 and new_tags != a.tags:
            a.tags = new_tags
            changed = True
        if changed:
            self.store.update(a)

    def _on_double(self, item, col):
        if col == 1:
            return  # editing
        a = item.data(0, Qt.UserRole)
        if a is not None:
            self.activated.emit(a)

    # -- export --------------------------------------------------------------

    def _export_md(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export TODO (Markdown)",
                                              "todo.md", "Markdown (*.md)")
        if not path:
            return
        try:
            export_markdown(self._todos(), path, group_by=self._group_mode())
            QMessageBox.information(self, "Exported", f"Wrote {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _export_docx(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export TODO (DOCX)",
                                              "todo.docx", "Word (*.docx)")
        if not path:
            return
        try:
            export_docx(self._todos(), path, group_by=self._group_mode())
            QMessageBox.information(self, "Exported", f"Wrote {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
