"""Graphics items for each annotation kind (Phase 2).

Items are children of a :class:`PageItem`, so their local coordinates are PDF
points in page space.  A model :class:`Annotation` is the single source of
truth; items sync geometry/style back to it and push undo commands on edit.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import (
    QColor, QPen, QBrush, QPainterPath, QFont, QPolygonF, QPainterPathStroker,
)
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsPathItem, QGraphicsObject,
    QStyle,
)

from ..model.annotations import (
    Annotation, KIND_HIGHLIGHT, KIND_PEN, KIND_COMMENT, KIND_TEXTBOX,
    KIND_RECT, KIND_ARROW,
)
from .command_stack import ModifyAnnotationCommand, capture

HANDLE = 7.0  # handle size in points


def qcolor(rgb, alpha=255) -> QColor:
    r, g, b = rgb
    return QColor(int(r * 255), int(g * 255), int(b * 255), alpha)


# --- selectable / movable base ---------------------------------------------


class _BaseMixin:
    """Shared selection, move-undo and model-sync behaviour."""

    def init_base(self, ann: Annotation, view):
        self.ann = ann
        self.view = view
        self._press_snap = None
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def _selectable(self) -> bool:
        return getattr(self.view, "select_mode", True)

    def mousePressEvent(self, event):
        self._press_snap = capture(self.ann)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self._press_snap is not None:
            self.write_geometry_to_model()
            after = capture(self.ann)
            if after != self._press_snap:
                self.view.push_command(
                    ModifyAnnotationCommand(self.view, self.ann,
                                            self._press_snap, after, "Move"))
            self._press_snap = None

    # subclasses override
    def write_geometry_to_model(self):
        pass

    def sync_from_model(self):
        pass


# --- rect-based, resizable --------------------------------------------------


class _HandleItem(QGraphicsRectItem):
    """A small resize grip living on a resizable parent."""

    def __init__(self, parent, role):
        super().__init__(-HANDLE / 2, -HANDLE / 2, HANDLE, HANDLE, parent)
        self.role = role  # 'nw','ne','sw','se'
        self.setBrush(QBrush(QColor(30, 120, 230)))
        self.setPen(QPen(QColor("white"), 0))
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, False)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setZValue(50)
        self.setVisible(False)

    def mousePressEvent(self, event):
        self.parentItem()._begin_resize()
        event.accept()

    def mouseMoveEvent(self, event):
        self.parentItem()._resize_to(self.role, event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event):
        self.parentItem()._end_resize()
        event.accept()


class ResizableRectItem(_BaseMixin, QGraphicsRectItem):
    """Base for highlight / textbox / rect marks with corner handles."""

    def __init__(self, ann: Annotation, view):
        super().__init__()
        self.init_base(ann, view)
        self._handles = {r: _HandleItem(self, r) for r in ("nw", "ne", "sw", "se")}
        self._resize_snap = None
        self.sync_from_model()

    # geometry --------------------------------------------------------------

    def sync_from_model(self):
        x0, y0, x1, y1 = self.ann.rect
        w, h = abs(x1 - x0), abs(y1 - y0)
        self.setPos(min(x0, x1), min(y0, y1))
        self.setRect(0, 0, max(w, 1.0), max(h, 1.0))
        self._place_handles()
        self.update()

    def write_geometry_to_model(self):
        p = self.pos()
        r = self.rect()
        self.ann.rect = (p.x(), p.y(), p.x() + r.width(), p.y() + r.height())

    def _place_handles(self):
        r = self.rect()
        pts = {"nw": r.topLeft(), "ne": r.topRight(),
               "sw": r.bottomLeft(), "se": r.bottomRight()}
        for role, h in self._handles.items():
            h.setPos(pts[role])

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            for h in self._handles.values():
                h.setVisible(bool(value))
        return super().itemChange(change, value)

    # resize ----------------------------------------------------------------

    def _begin_resize(self):
        self._resize_snap = capture(self.ann)

    def _resize_to(self, role, scene_pos):
        local = self.mapFromScene(scene_pos)
        r = self.rect()
        if role == "nw":
            r.setTopLeft(local)
        elif role == "ne":
            r.setTopRight(local)
        elif role == "sw":
            r.setBottomLeft(local)
        elif role == "se":
            r.setBottomRight(local)
        r = r.normalized()
        # keep position anchored: convert to absolute coords
        new_top_left = self.mapToParent(r.topLeft())
        self.setPos(new_top_left)
        self.setRect(0, 0, max(r.width(), 4.0), max(r.height(), 4.0))
        self._place_handles()

    def _end_resize(self):
        self.write_geometry_to_model()
        after = capture(self.ann)
        if self._resize_snap is not None and after != self._resize_snap:
            self.view.push_command(
                ModifyAnnotationCommand(self.view, self.ann,
                                        self._resize_snap, after, "Resize"))
        self._resize_snap = None
        self.view.store.update(self.ann)


class HighlightItem(ResizableRectItem):
    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(qcolor(self.ann.color, int(self.ann.opacity * 255))))
        painter.drawRect(self.rect())
        if self.isSelected():
            painter.setPen(QPen(QColor(30, 120, 230), 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect())


class RectShapeItem(ResizableRectItem):
    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        painter.setPen(QPen(qcolor(self.ann.color), self.ann.width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())
        if self.isSelected():
            painter.setPen(QPen(QColor(30, 120, 230), 0, Qt.DashLine))
            painter.drawRect(self.rect())


class TextBoxItem(ResizableRectItem):
    """FreeText-style mark: renders its text directly on the page."""

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        font = QFont("Helvetica", max(4, int(self.ann.font_size)))
        font.setBold(self.ann.bold)
        font.setItalic(self.ann.italic)
        painter.setFont(font)
        painter.setPen(QPen(qcolor(self.ann.color)))
        painter.drawText(self.rect().adjusted(2, 2, -2, -2),
                         Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
                         self.ann.text or "")
        border = QColor(120, 120, 120, 120) if not self.isSelected() else QColor(30, 120, 230)
        painter.setPen(QPen(border, 0, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect())

    def mouseDoubleClickEvent(self, event):
        self.view.edit_text_annotation(self.ann)
        event.accept()


# --- pen stroke -------------------------------------------------------------


class PenItem(_BaseMixin, QGraphicsPathItem):
    def __init__(self, ann: Annotation, view):
        super().__init__()
        self.init_base(ann, view)
        self.sync_from_model()

    def sync_from_model(self):
        path = QPainterPath()
        pts = self.ann.points
        if pts:
            path.moveTo(*pts[0])
            if len(pts) == 1:
                path.lineTo(pts[0][0] + 0.1, pts[0][1] + 0.1)
            else:
                # smooth with quadratics through midpoints
                for i in range(1, len(pts)):
                    x0, y0 = pts[i - 1]
                    x1, y1 = pts[i]
                    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                    path.quadTo(x0, y0, mx, my)
                path.lineTo(*pts[-1])
        self.setPath(path)
        pen = QPen(qcolor(self.ann.color), self.ann.width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        # position is encoded in the points themselves
        self.setPos(0, 0)

    def write_geometry_to_model(self):
        # translate points by the item's accumulated offset, then reset pos
        dx, dy = self.pos().x(), self.pos().y()
        if dx or dy:
            self.ann.points = [(x + dx, y + dy) for x, y in self.ann.points]
            self.setPos(0, 0)
            self.sync_from_model()

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.ann.width, 6.0))
        return stroker.createStroke(self.path())

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(QColor(30, 120, 230), 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())


# --- arrow ------------------------------------------------------------------


class ArrowItem(_BaseMixin, QGraphicsPathItem):
    def __init__(self, ann: Annotation, view):
        super().__init__()
        self.init_base(ann, view)
        self.sync_from_model()

    def sync_from_model(self):
        import math
        x0, y0, x1, y1 = self.ann.rect
        path = QPainterPath()
        path.moveTo(x0, y0)
        path.lineTo(x1, y1)
        ang = math.atan2(y1 - y0, x1 - x0)
        ah = 10.0
        for da in (math.radians(150), math.radians(-150)):
            path.moveTo(x1, y1)
            path.lineTo(x1 + ah * math.cos(ang + da), y1 + ah * math.sin(ang + da))
        self.setPath(path)
        pen = QPen(qcolor(self.ann.color), self.ann.width)
        pen.setCapStyle(Qt.RoundCap)
        self.setPen(pen)
        self.setPos(0, 0)

    def write_geometry_to_model(self):
        dx, dy = self.pos().x(), self.pos().y()
        if dx or dy:
            x0, y0, x1, y1 = self.ann.rect
            self.ann.rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            self.setPos(0, 0)
            self.sync_from_model()


# --- comment (sticky note bubble) ------------------------------------------


class CommentItem(_BaseMixin, QGraphicsObject):
    SIZE = 18.0

    def __init__(self, ann: Annotation, view):
        super().__init__()
        self.init_base(ann, view)
        self.sync_from_model()

    def sync_from_model(self):
        x0, y0, _, _ = self.ann.rect
        self.setPos(x0, y0)
        self.update()

    def write_geometry_to_model(self):
        p = self.pos()
        s = self.SIZE
        self.ann.rect = (p.x(), p.y(), p.x() + s, p.y() + s)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.SIZE, self.SIZE + 5)

    def paint(self, painter, option, widget=None):
        s = self.SIZE
        body = QColor(255, 209, 71) if not self.ann.is_todo else QColor(120, 190, 255)
        if self.ann.todo_done:
            body = QColor(150, 220, 150)
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setBrush(QBrush(body))
        painter.setPen(QPen(QColor(90, 70, 0), 1.0))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, s, s), 4, 4)
        # little tail
        tail = QPolygonF([QPointF(4, s - 1), QPointF(4, s + 5), QPointF(10, s - 1)])
        path.addPolygon(tail)
        painter.drawPath(path.simplified())
        # speech lines
        painter.setPen(QPen(QColor(90, 70, 0), 1.0))
        for i, yy in enumerate((6, 9, 12)):
            painter.drawLine(QPointF(4, yy), QPointF(s - 4 - i, yy))
        if self.isSelected():
            painter.setPen(QPen(QColor(30, 120, 230), 0, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    def mouseDoubleClickEvent(self, event):
        self.view.edit_comment_annotation(self.ann)
        event.accept()


# --- factory ----------------------------------------------------------------

_FACTORY = {
    KIND_HIGHLIGHT: HighlightItem,
    KIND_PEN: PenItem,
    KIND_COMMENT: CommentItem,
    KIND_TEXTBOX: TextBoxItem,
    KIND_RECT: RectShapeItem,
    KIND_ARROW: ArrowItem,
}


def make_item(ann: Annotation, view):
    cls = _FACTORY.get(ann.kind)
    if cls is None:
        return None
    return cls(ann, view)
