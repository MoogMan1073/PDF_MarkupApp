"""Comment sidebar (Phase 4).

A dockable, Chrome-bookmarks-style list of every non-ignored comment / text box
(and optionally highlights & pen strokes) with live filter + sort.  Clicking a
row asks the viewer to scroll to and flash the mark.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QLabel,
    QTreeWidget, QTreeWidgetItem, QCheckBox,
)

from ..model.annotations import (
    Annotation, KIND_COMMENT, KIND_TEXTBOX, KIND_HIGHLIGHT, KIND_PEN,
)

_KIND_ICON = {
    KIND_COMMENT: "💬", KIND_TEXTBOX: "🅣", KIND_HIGHLIGHT: "🖍", KIND_PEN: "✎",
}
_DATE = lambda iso: (iso or "")[:16].replace("T", " ")

SORTS = ["Page", "Commenter", "Datetime", "Type"]


class CommentPanel(QWidget):
    activated = Signal(object)       # Annotation
    todoToggled = Signal(object)     # Annotation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = None
        self.config = None
        self._build_ui()

    # -- ui ------------------------------------------------------------------

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self.search = QLineEdit(placeholderText="Search comments…")
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)

        row = QHBoxLayout()
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All types", "Comment", "Text box", "Highlight", "Pen"])
        self.type_filter.currentIndexChanged.connect(self.refresh)
        self.commenter_filter = QComboBox()
        self.commenter_filter.addItem("All commenters")
        self.commenter_filter.currentIndexChanged.connect(self.refresh)
        row.addWidget(self.type_filter)
        row.addWidget(self.commenter_filter)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        self.sort_by = QComboBox()
        self.sort_by.addItems(SORTS)
        self.sort_by.currentIndexChanged.connect(self.refresh)
        self.sort_desc = QCheckBox("Desc")
        self.sort_desc.stateChanged.connect(self.refresh)
        self.todo_only = QCheckBox("TODO only")
        self.todo_only.stateChanged.connect(self.refresh)
        row2.addWidget(QLabel("Sort:"))
        row2.addWidget(self.sort_by, 1)
        row2.addWidget(self.sort_desc)
        row2.addWidget(self.todo_only)
        lay.addLayout(row2)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["", "Comment", "Pg", "By"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemClicked.connect(self._on_click)
        self.tree.setColumnWidth(0, 26)
        self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 32)
        lay.addWidget(self.tree, 1)

        self.count_label = QLabel("")
        lay.addWidget(self.count_label)

    # -- wiring --------------------------------------------------------------

    def set_store(self, store, config=None):
        self.store = store
        self.config = config
        store.add_listener(self._on_store_event)
        self.refresh()

    def _on_store_event(self, event, ann):
        # debounce-ish: refresh on the event loop
        QTimer.singleShot(0, self.refresh)

    # -- filtering -----------------------------------------------------------

    def _included_kinds(self):
        idx = self.type_filter.currentIndex()
        return {
            0: None,
            1: {KIND_COMMENT}, 2: {KIND_TEXTBOX},
            3: {KIND_HIGHLIGHT}, 4: {KIND_PEN},
        }[idx]

    def _refresh_commenters(self, anns):
        current = self.commenter_filter.currentText()
        names = sorted({a.author for a in anns if a.author})
        self.commenter_filter.blockSignals(True)
        self.commenter_filter.clear()
        self.commenter_filter.addItem("All commenters")
        self.commenter_filter.addItems(names)
        i = self.commenter_filter.findText(current)
        self.commenter_filter.setCurrentIndex(i if i >= 0 else 0)
        self.commenter_filter.blockSignals(False)

    def refresh(self):
        if self.store is None:
            return
        show_ignored = bool(self.config and self.config.show_ignored)
        base = [a for a in self.store.visible(show_ignored)
                if a.kind in (KIND_COMMENT, KIND_TEXTBOX, KIND_HIGHLIGHT, KIND_PEN)]
        self._refresh_commenters(base)

        kinds = self._included_kinds()
        needle = self.search.text().lower().strip()
        commenter = self.commenter_filter.currentText()

        rows = []
        for a in base:
            if kinds is not None and a.kind not in kinds:
                continue
            if self.todo_only.isChecked() and not a.is_todo:
                continue
            if commenter != "All commenters" and a.author != commenter:
                continue
            if needle and needle not in (a.text or "").lower():
                continue
            rows.append(a)

        key = {0: lambda a: a.page, 1: lambda a: a.author.lower(),
               2: lambda a: a.created, 3: lambda a: a.kind}[self.sort_by.currentIndex()]
        rows.sort(key=key, reverse=self.sort_desc.isChecked())

        self.tree.clear()
        for a in rows:
            it = QTreeWidgetItem([
                _KIND_ICON.get(a.kind, "•"),
                a.snippet(48) + ("  ✓" if a.is_todo and a.todo_done else
                                 "  ☐" if a.is_todo else ""),
                str(a.page + 1),
                a.author or "",
            ])
            it.setData(0, Qt.UserRole, a)
            it.setToolTip(1, f"{a.text}\n{a.author} · {_DATE(a.created)}")
            self.tree.addTopLevelItem(it)
        self.count_label.setText(f"{len(rows)} item(s)")

    # -- interaction ---------------------------------------------------------

    def _on_click(self, item, _col):
        ann = item.data(0, Qt.UserRole)
        if ann is not None:
            self.activated.emit(ann)
