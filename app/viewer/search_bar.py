"""A Chrome-style in-document search bar.

A small floating panel shown over the viewer on Ctrl+F.  It stays visible after
being summoned (until closed with the ✕ or Esc), searches as you type
(debounced), shows an *i/n* match count, and navigates with Enter / Shift+Enter
or the ▲/▼ buttons.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLineEdit, QLabel, QToolButton,
)


class SearchBar(QFrame):
    queryChanged = Signal(str)   # debounced (or forced) query text
    nextRequested = Signal()
    prevRequested = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchBar")
        self.setFrameShape(QFrame.StyledPanel)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(
            lambda: self.queryChanged.emit(self.input.text()))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(4)

        self.input = QLineEdit()
        self.input.setObjectName("SearchInput")
        self.input.setPlaceholderText("Find in document")
        self.input.setMinimumWidth(210)
        self.input.setClearButtonEnabled(True)
        self.input.textChanged.connect(lambda *_: self._debounce.start())
        self.input.returnPressed.connect(self._on_return)
        self.input.installEventFilter(self)

        self.count = QLabel("0/0")
        self.count.setObjectName("SearchCount")
        self.count.setMinimumWidth(46)
        self.count.setAlignment(Qt.AlignCenter)

        self.btn_prev = self._tool("▲", "Previous match (Shift+Enter)", self.prevRequested)
        self.btn_next = self._tool("▼", "Next match (Enter)", self.nextRequested)
        self.btn_close = self._tool("✕", "Close (Esc)", self.closed)

        for w in (self.input, self.count, self.btn_prev, self.btn_next, self.btn_close):
            lay.addWidget(w)

        self.setStyleSheet("""
            QFrame#SearchBar {
                background: #fbfbfb; border: 1px solid #b4b4b4; border-radius: 7px;
            }
            QLineEdit#SearchInput {
                border: 1px solid #cfcfcf; border-radius: 4px; padding: 3px 6px;
                background: white; color: #1d1d1d;
            }
            QLabel#SearchCount { color: #6a6a6a; }
            QToolButton { border: none; padding: 2px 6px; color: #2a2a2a; font-size: 13px; }
            QToolButton:hover { background: #e7e7e7; border-radius: 4px; }
        """)
        self.adjustSize()

    def _tool(self, text, tip, signal):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.clicked.connect(lambda: signal.emit())
        return b

    # -- public API ----------------------------------------------------------

    def focus_input(self):
        self.input.setFocus()
        self.input.selectAll()

    def set_count(self, index: int, total: int):
        self.count.setText(f"{index}/{total}")
        empty = total == 0 and bool(self.input.text())
        self.count.setStyleSheet("color:#c0392b;" if empty else "color:#6a6a6a;")

    # -- behaviour -----------------------------------------------------------

    def _on_return(self):
        # If the query changed and hasn't been searched yet, search it now
        # (lands on the first match); otherwise advance to the next match.
        if self._debounce.isActive():
            self._debounce.stop()
            self.queryChanged.emit(self.input.text())
        else:
            self.nextRequested.emit()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.closed.emit()
                return True
            if (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                    and (event.modifiers() & Qt.ShiftModifier)):
                self.prevRequested.emit()
                return True
        return super().eventFilter(obj, event)
