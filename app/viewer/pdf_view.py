"""Continuous-scroll PDF canvas (Phase 1 + 2).

A :class:`QGraphicsView` that lays every page vertically (Chrome-style), renders
lazily for visible/near pages, supports Ctrl+scroll zoom, space/middle-drag pan,
fit-width / fit-page, page navigation, and hosts the markup tools.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QBrush, QKeySequence, QShortcut
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem

from ..model.annotations import (
    Annotation, AnnotationStore,
    KIND_HIGHLIGHT, KIND_PEN, KIND_COMMENT, KIND_TEXTBOX, KIND_RECT, KIND_ARROW,
)
from .page_item import PageItem
from .annotation_items import make_item
from .command_stack import (
    QUndoStack, AddAnnotationCommand, RemoveAnnotationCommand,
)
from . import tools as T

PAGE_GAP = 14.0   # points between pages in the scroll


class PdfView(QGraphicsView):
    selectionInfo = Signal(str)
    pageChanged = Signal(int)
    requestCommentEdit = Signal(object)   # Annotation
    requestTextEdit = Signal(object)      # Annotation
    annotationActivated = Signal(object)  # Annotation (from a panel jump)
    requestTool = Signal(str)             # ask the window to switch tools
    regionPicked = Signal(int, object)    # page_index, QRectF (page points)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QBrush(QColor(82, 86, 89)))
        self.setScene(self._scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.document = None
        self.store: Optional[AnnotationStore] = None
        self.config = None
        self.undo_stack = QUndoStack(self)
        self.tool = T.ToolState()

        self._page_items: list = []
        self._item_by_ann: dict = {}     # ann.id -> graphics item
        self._zoom = 1.0
        self._panning = False
        self._space_down = False
        self._pan_start = QPointF()

        # interactive draft state
        self._draft = None
        self._draft_page = None
        self._draft_start = None
        self._erasing = False
        self._erase_macro_open = False
        # synchronous prompt for *new* comment/text-box text, set by the window.
        # signature: prompt(ann, is_textbox) -> (accepted: bool, text, todo)
        self.new_text_prompt = None
        # prompt when a drawing tool clicks an existing mark, set by the window.
        # signature: prompt(ann) -> "edit" | "new" | "cancel"
        self.existing_mark_prompt = None
        # region-pick mode (for the sheet-number / crop wizards)
        self._region_pick = False
        self._region_item = None
        self._region_page = None
        self._region_start = None

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(60)
        self._render_timer.timeout.connect(self._render_visible)

        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    # -- properties ----------------------------------------------------------

    @property
    def select_mode(self) -> bool:
        return self.tool.is_select()

    def push_command(self, cmd) -> None:
        self.undo_stack.push(cmd)

    # -- document lifecycle --------------------------------------------------

    def set_document(self, document, config=None) -> None:
        self.document = document
        self.store = document.store
        self.config = config
        self._scene.clear()
        self._page_items = []
        self._item_by_ann = {}
        self.undo_stack.clear()

        top = 0.0
        max_w = 0.0
        for pno in range(document.page_count):
            item = PageItem(document, pno, top)
            self._scene.addItem(item)
            self._page_items.append(item)
            top += item.pdf_h + PAGE_GAP
            max_w = max(max_w, item.pdf_w)
        self._scene.setSceneRect(0, 0, max_w, max(top - PAGE_GAP, 1.0))

        # build items for pre-loaded annotations
        for ann in self.store.all():
            self._add_item_for(ann)
        self.store.add_listener(self._on_store_event)

        QTimer.singleShot(0, self.fit_width)
        QTimer.singleShot(0, self._render_visible)

    # -- rendering -----------------------------------------------------------

    def _visible_scene_rect(self) -> QRectF:
        return self.mapToScene(self.viewport().rect()).boundingRect()

    def _render_visible(self) -> None:
        if not self._page_items:
            return
        vis = self._visible_scene_rect()
        margin = vis.height()  # render one screenful above/below
        lo, hi = vis.top() - margin, vis.bottom() + margin
        scale = max(1.0, min(self._zoom, 4.0))
        for item in self._page_items:
            if item.scene_bottom() >= lo and item.scene_top() <= hi:
                item.render(scale)
            elif item.is_rendered() and (item.scene_bottom() < vis.top() - 4 * margin
                                         or item.scene_top() > vis.bottom() + 4 * margin):
                item.clear_render()
        self._emit_current_page()

    def _on_scroll(self, *_):
        self._render_timer.start()

    def _emit_current_page(self) -> None:
        vis = self._visible_scene_rect()
        mid = vis.center().y()
        for i, item in enumerate(self._page_items):
            if item.scene_top() <= mid <= item.scene_bottom():
                self.pageChanged.emit(i)
                return

    # -- zoom / fit ----------------------------------------------------------

    def set_zoom(self, zoom: float) -> None:
        zoom = max(0.1, min(zoom, 8.0))
        self._zoom = zoom
        self.resetTransform()
        self.scale(zoom, zoom)
        self._render_timer.start()

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.25)

    def fit_width(self):
        if not self._page_items:
            return
        page_w = self._page_items[0].pdf_w
        avail = self.viewport().width() - 24
        if page_w > 0:
            self.set_zoom(avail / page_w)

    def fit_page(self):
        if not self._page_items:
            return
        page = self._page_items[0]
        aw = self.viewport().width() - 24
        ah = self.viewport().height() - 24
        self.set_zoom(min(aw / page.pdf_w, ah / page.pdf_h))

    def go_to_page(self, page_no: int):
        if 0 <= page_no < len(self._page_items):
            item = self._page_items[page_no]
            self.centerOn(item.pdf_w / 2, item.scene_top() + 20)
            self._render_timer.start()

    # -- events --------------------------------------------------------------

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
            self.set_zoom(self._zoom * factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_down = True
            self.setCursor(Qt.OpenHandCursor)
        elif event.key() == Qt.Key_Delete:
            self.delete_selected()
        elif event.key() == Qt.Key_Escape:
            self.cancel_action()
        super().keyPressEvent(event)

    def cancel_action(self):
        """Abort an in-progress draw/erase/region-pick and drop any preview."""
        if self._region_pick or self._region_item is not None:
            self.cancel_region_pick()
        if self._draft is not None:
            self._draft = None
            self._clear_preview()
        if self._erasing:
            self._end_erase()
        self._scene.clearSelection()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_down = False
            self.unsetCursor()
        super().keyReleaseEvent(event)

    def _page_at_scene(self, scene_pt: QPointF):
        for i, item in enumerate(self._page_items):
            if item.scene_top() <= scene_pt.y() <= item.scene_bottom():
                return i, item
        return None, None

    # -- region pick (wizards) ----------------------------------------------

    def start_region_pick(self):
        """Enter a mode where the next left-drag selects a rectangular region
        (emitted via ``regionPicked``) instead of creating a mark.  Panning and
        scrolling stay available for navigation."""
        self._region_pick = True
        self.viewport().setCursor(Qt.CrossCursor)

    def cancel_region_pick(self):
        self._region_pick = False
        self.viewport().unsetCursor()
        if self._region_item is not None:
            self._scene.removeItem(self._region_item)
            self._region_item = None
        self._region_page = None
        self._region_start = None

    def _region_begin(self, scene_pt):
        from PySide6.QtWidgets import QGraphicsRectItem
        from PySide6.QtGui import QPen, QColor
        pno, page = self._page_at_scene(scene_pt)
        if page is None:
            return False
        self._region_page = (pno, page)
        self._region_start = (scene_pt.x() - page.pos().x(), scene_pt.y() - page.pos().y())
        self._region_item = QGraphicsRectItem(page)
        self._region_item.setZValue(60)
        pen = QPen(QColor(30, 120, 230), 0, Qt.DashLine)
        self._region_item.setPen(pen)
        from PySide6.QtGui import QBrush
        self._region_item.setBrush(QBrush(QColor(30, 120, 230, 40)))
        return True

    def _region_update(self, scene_pt):
        if self._region_item is None:
            return
        _, page = self._region_page
        lx, ly = scene_pt.x() - page.pos().x(), scene_pt.y() - page.pos().y()
        sx, sy = self._region_start
        self._region_item.setRect(min(sx, lx), min(sy, ly), abs(lx - sx), abs(ly - sy))

    def _region_finish(self):
        from PySide6.QtCore import QRectF
        if self._region_item is None:
            return
        r = self._region_item.rect()
        pno = self._region_page[0]
        self._scene.removeItem(self._region_item)
        self._region_item = None
        self._region_pick = False
        self.viewport().unsetCursor()
        if r.width() >= 4 and r.height() >= 4:
            self.regionPicked.emit(pno, QRectF(r))

    def mousePressEvent(self, event):
        # pan with middle button or space-drag
        if event.button() == Qt.MiddleButton or (self._space_down and event.button() == Qt.LeftButton):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if self._region_pick and event.button() == Qt.LeftButton:
            scene_pt = self.mapToScene(event.position().toPoint())
            if self._region_begin(scene_pt):
                event.accept()
                return

        if event.button() == Qt.LeftButton and not self.tool.is_select():
            scene_pt = self.mapToScene(event.position().toPoint())
            if self._begin_draft(scene_pt):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(
                int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
            return
        if self._region_item is not None and (event.buttons() & Qt.LeftButton):
            self._region_update(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._erasing and (event.buttons() & Qt.LeftButton):
            self._erase_at(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._draft is not None:
            scene_pt = self.mapToScene(event.position().toPoint())
            self._update_draft(scene_pt)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.setCursor(Qt.OpenHandCursor if self._space_down else Qt.ArrowCursor)
            event.accept()
            return
        if self._region_item is not None:
            self._region_finish()
            event.accept()
            return
        if self._erasing:
            self._end_erase()
            event.accept()
            return
        if self._draft is not None:
            self._finish_draft()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -- draft creation ------------------------------------------------------

    def _annotation_item_at(self, scene_pt: QPointF):
        """Return the topmost existing annotation item under a scene point."""
        for it in self._scene.items(scene_pt):
            ann = getattr(it, "ann", None)
            if ann is not None:
                return it
        return None

    def _begin_draft(self, scene_pt: QPointF) -> bool:
        pno, page = self._page_at_scene(scene_pt)
        if page is None:
            return False
        lx, ly = scene_pt.x() - page.pos().x(), scene_pt.y() - page.pos().y()
        self._draft_page = (pno, page)
        self._draft_start = (lx, ly)
        author = self.config.your_name if self.config else ""
        tool = self.tool.current

        # Clicking an existing mark with a drawing tool: ask edit vs draw-new.
        if tool != T.TOOL_ERASER:
            existing = self._annotation_item_at(scene_pt)
            if existing is not None:
                choice = "new"
                if self.existing_mark_prompt is not None:
                    choice = self.existing_mark_prompt(existing.ann)
                if choice == "cancel":
                    return True
                if choice == "edit":
                    self.requestTool.emit(T.TOOL_SELECT)
                    existing.setSelected(True)
                    return True
                # choice == "new": fall through and draw a new mark

        if tool == T.TOOL_COMMENT:
            ann = Annotation(page=pno, kind=KIND_COMMENT, rect=(lx, ly, lx + 18, ly + 18),
                             author=author, is_todo=self._default_todo())
            if self.new_text_prompt is not None:
                ok, text, todo = self.new_text_prompt(ann, False)
                if not ok:
                    return True  # cancelled -> never added to the document
                ann.text = text
                ann.is_todo = todo
            self._commit_new(ann)
            return True
        if tool == T.TOOL_PEN:
            self._draft = Annotation(page=pno, kind=KIND_PEN, points=[(lx, ly)],
                                     color=self.tool.pen_color, width=self.tool.pen_width,
                                     author=author)
            return True
        if tool in (T.TOOL_HIGHLIGHT, T.TOOL_RECT, T.TOOL_ARROW, T.TOOL_TEXTBOX):
            kind = {T.TOOL_HIGHLIGHT: KIND_HIGHLIGHT, T.TOOL_RECT: KIND_RECT,
                    T.TOOL_ARROW: KIND_ARROW, T.TOOL_TEXTBOX: KIND_TEXTBOX}[tool]
            color = (self.tool.highlight_color if kind == KIND_HIGHLIGHT else
                     self.tool.text_color if kind == KIND_TEXTBOX else self.tool.shape_color)
            self._draft = Annotation(page=pno, kind=kind, rect=(lx, ly, lx, ly),
                                     color=color, author=author,
                                     width=self.tool.shape_width,
                                     font_size=self.tool.font_size,
                                     bold=self.tool.bold, italic=self.tool.italic,
                                     opacity=self.tool.highlight_opacity)
            return True
        if tool == T.TOOL_ERASER:
            self._erasing = True
            self._erase_macro_open = False
            self._erase_at(scene_pt)
            return True
        return False

    def _update_draft(self, scene_pt: QPointF):
        if self._draft is None:
            return
        _, page = self._draft_page
        lx, ly = scene_pt.x() - page.pos().x(), scene_pt.y() - page.pos().y()
        if self._draft.kind == KIND_PEN:
            self._draft.points.append((lx, ly))
        else:
            sx, sy = self._draft_start
            self._draft.rect = (sx, sy, lx, ly)
        self._refresh_preview()

    def _refresh_preview(self):
        # cheap live preview: rebuild the draft item (drawn above the page)
        self._clear_preview()
        item = make_item(self._draft, self)
        if item is not None:
            _, page = self._draft_page
            item.setParentItem(page)
            item.setZValue(12)
            item.setOpacity(0.7)
            self._item_by_ann["__draft__"] = item

    def _clear_preview(self):
        prev = self._item_by_ann.pop("__draft__", None)
        if prev is not None:
            self._scene.removeItem(prev)

    def _finish_draft(self):
        draft = self._draft
        self._draft = None
        if draft is None:
            self._clear_preview()
            return
        # discard degenerate marks
        degenerate = draft.kind == KIND_PEN and len(draft.points) < 2
        if draft.kind in (KIND_HIGHLIGHT, KIND_RECT, KIND_ARROW, KIND_TEXTBOX):
            x0, y0, x1, y1 = draft.rect
            if abs(x1 - x0) < 3 and abs(y1 - y0) < 3:
                degenerate = True
            elif draft.kind != KIND_ARROW:
                draft.rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        if degenerate:
            self._clear_preview()
            return

        # text boxes: prompt for text *before* committing (keep the live
        # preview visible meanwhile); a cancel discards the box entirely.
        if draft.kind == KIND_TEXTBOX:
            draft.is_todo = self._default_todo()
            ok, text, todo = (True, "", draft.is_todo)
            if self.new_text_prompt is not None:
                ok, text, todo = self.new_text_prompt(draft, True)
            self._clear_preview()
            if not ok:
                return
            draft.text = text
            draft.is_todo = todo
            self._commit_new(draft)
            return

        self._clear_preview()
        self._commit_new(draft)

    def _default_todo(self) -> bool:
        return bool(self.config and getattr(self.config, "treat_all_as_todo", False))

    def _commit_new(self, ann: Annotation):
        self.push_command(AddAnnotationCommand(self, ann, f"Add {ann.kind}"))

    # -- erasing -------------------------------------------------------------

    def _erase_at(self, scene_pt: QPointF):
        """Remove the whole mark under the point (live), grouping a drag into a
        single undo step.  Removal is a true delete via the model, so erased
        marks are dropped from the saved PDF/sidecar, not merely hidden."""
        existing = self._annotation_item_at(scene_pt)
        if existing is None:
            return
        if not self._erase_macro_open:
            self.undo_stack.beginMacro("Erase")
            self._erase_macro_open = True
        self.push_command(RemoveAnnotationCommand(self, existing.ann, "Erase"))

    def _end_erase(self):
        self._erasing = False
        if self._erase_macro_open:
            self.undo_stack.endMacro()
            self._erase_macro_open = False

    def delete_selected(self):
        for it in list(self._scene.selectedItems()):
            ann = getattr(it, "ann", None)
            if ann is not None:
                self.push_command(RemoveAnnotationCommand(self, ann, "Delete"))

    def request_delete_annotation(self, ann: Annotation):
        """Confirm, then delete a mark from the canvas (undoable)."""
        from PySide6.QtWidgets import QMessageBox
        resp = QMessageBox.question(
            self, "Delete", f"Delete this {ann.kind}?\n\n{ann.snippet(80)}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resp == QMessageBox.Yes:
            self.push_command(RemoveAnnotationCommand(self, ann, "Delete"))

    def show_comment_contents(self, ann: Annotation):
        from PySide6.QtWidgets import QMessageBox
        when = (ann.created or "")[:16].replace("T", " ")
        meta = " · ".join(p for p in (ann.author, when) if p)
        QMessageBox.information(self, "Comment contents",
                                f"{meta}\n\n{ann.text or '(no text)'}")

    # -- store sync ----------------------------------------------------------

    def _on_store_event(self, event: str, ann: Annotation):
        if event == "add":
            self._add_item_for(ann)
        elif event == "remove":
            self._remove_item_for(ann)
        elif event == "update":
            self._refresh_item_for(ann)

    def _add_item_for(self, ann: Annotation):
        if ann.id in self._item_by_ann:
            self._refresh_item_for(ann)
            return
        if ann.ignored and not (self.config and self.config.show_ignored):
            return
        if ann.page < 0 or ann.page >= len(self._page_items):
            return
        item = make_item(ann, self)
        if item is None:
            return
        item.setParentItem(self._page_items[ann.page])
        item.setZValue(10)  # draw marks above the page bitmap (z=1)
        select = self.tool.is_select()
        item.setFlag(QGraphicsItem.ItemIsMovable, select)
        item.setFlag(QGraphicsItem.ItemIsSelectable, select)
        self._item_by_ann[ann.id] = item

    def _remove_item_for(self, ann: Annotation):
        item = self._item_by_ann.pop(ann.id, None)
        if item is not None:
            self._scene.removeItem(item)

    def _refresh_item_for(self, ann: Annotation):
        item = self._item_by_ann.get(ann.id)
        if item is None:
            self._add_item_for(ann)
            return
        if hasattr(item, "sync_from_model"):
            item.sync_from_model()
        item.update()

    def rebuild_all_items(self):
        for item in list(self._item_by_ann.values()):
            self._scene.removeItem(item)
        self._item_by_ann.clear()
        for ann in self.store.all():
            self._add_item_for(ann)

    # -- editing hooks (wired by main window) --------------------------------

    def edit_comment_annotation(self, ann: Annotation):
        self.requestCommentEdit.emit(ann)

    def edit_text_annotation(self, ann: Annotation):
        self.requestTextEdit.emit(ann)

    # -- panel jump ----------------------------------------------------------

    def flash_annotation(self, ann: Annotation):
        self.go_to_page(ann.page)
        x0, y0, x1, y1 = ann.rect
        page = self._page_items[ann.page]
        self.centerOn(page.pos().x() + (x0 + x1) / 2, page.scene_top() + (y0 + y1) / 2)
        item = self._item_by_ann.get(ann.id)
        if item is not None:
            item.setSelected(True)
            self._flash_item = item
            QTimer.singleShot(700, lambda: item.setSelected(False) if item else None)
