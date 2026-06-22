"""QUndoStack commands for every annotation edit (Phase 2).

Commands operate on the :class:`AnnotationStore` (the model) and ask the view to
re-sync the affected graphics item.  Create / delete / move / resize / style /
text edits are all undoable via Ctrl+Z / Ctrl+Shift+Z.
"""

from __future__ import annotations

import copy
from typing import Optional

from PySide6.QtGui import QUndoCommand, QUndoStack  # noqa: F401 (re-export)

from ..model.annotations import Annotation


class AddAnnotationCommand(QUndoCommand):
    def __init__(self, view, ann: Annotation, text: str = "Add"):
        super().__init__(text)
        self.view = view
        self.ann = ann

    def redo(self):
        self.view.store.add(self.ann)

    def undo(self):
        self.view.store.remove(self.ann.id)


class RemoveAnnotationCommand(QUndoCommand):
    def __init__(self, view, ann: Annotation, text: str = "Delete"):
        super().__init__(text)
        self.view = view
        self.ann = ann

    def redo(self):
        self.view.store.remove(self.ann.id)

    def undo(self):
        self.view.store.add(self.ann)


def _snapshot(ann: Annotation) -> dict:
    return {
        "rect": tuple(ann.rect),
        "points": list(ann.points),
        "color": tuple(ann.color),
        "width": ann.width,
        "font_size": ann.font_size,
        "bold": ann.bold,
        "italic": ann.italic,
        "text": ann.text,
        "opacity": ann.opacity,
    }


def _restore(ann: Annotation, snap: dict) -> None:
    ann.rect = tuple(snap["rect"])
    ann.points = list(snap["points"])
    ann.color = tuple(snap["color"])
    ann.width = snap["width"]
    ann.font_size = snap["font_size"]
    ann.bold = snap["bold"]
    ann.italic = snap["italic"]
    ann.text = snap["text"]
    ann.opacity = snap["opacity"]


class ModifyAnnotationCommand(QUndoCommand):
    """Generic geometry/style/text change captured as before/after snapshots."""

    def __init__(self, view, ann: Annotation, before: dict, after: dict,
                 text: str = "Edit"):
        super().__init__(text)
        self.view = view
        self.ann = ann
        self.before = copy.deepcopy(before)
        self.after = copy.deepcopy(after)
        self._first = True

    def redo(self):
        _restore(self.ann, self.after)
        self.view.store.update(self.ann)

    def undo(self):
        _restore(self.ann, self.before)
        self.view.store.update(self.ann)


def capture(ann: Annotation) -> dict:
    """Public helper - snapshot an annotation's editable state."""
    return _snapshot(ann)
