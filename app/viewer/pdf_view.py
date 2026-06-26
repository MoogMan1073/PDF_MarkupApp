"""Continuous-scroll PDF canvas (Phase 1 + 2).

A :class:`QGraphicsView` that lays every page vertically (Chrome-style), renders
lazily for visible/near pages, supports Ctrl+scroll zoom, space/middle-drag pan,
fit-width / fit-page, page navigation, and hosts the markup tools.
"""

from __future__ import annotations

from typing import Optional

import fitz

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
    requestOpen = Signal(str)             # a PDF was dropped onto the canvas
    requestReveal = Signal(object, str)   # Annotation, target ("todo" | "comment")
    zoomChanged = Signal(float)           # current zoom factor (1.0 == 100%)

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
        self.setAcceptDrops(True)         # open a dropped PDF

        self.document = None
        self.store: Optional[AnnotationStore] = None
        self.config = None
        self.undo_stack = QUndoStack(self)
        self.tool = T.ToolState()

        self._page_items: list = []
        self._rotation = 0               # whole-document view rotation (0/90/180/270)
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

        # text selection (Chrome-style) in Select mode
        self._text_selecting = False
        self._text_sel_page = None       # (pno, page_item)
        self._text_sel_start = None      # (lx, ly) in page points
        self._text_words = []            # cached words for the page being selected
        self._text_sel_items = []        # highlight QGraphicsRectItems
        self._selected_text = ""

        # in-document search (Ctrl+F)
        self._search_bar = None
        self._search_matches = []        # [(pno, fitz.Rect)]
        self._search_index = -1
        self._search_items = []          # highlight QGraphicsRectItems

        # Ctrl+C copies the current text selection (only when the view has focus)
        copy_sc = QShortcut(QKeySequence.Copy, self)
        copy_sc.setContext(Qt.WidgetWithChildrenShortcut)
        copy_sc.activated.connect(self.copy_selection)
        self._copy_sc = copy_sc

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
        # scene.clear() destroyed any selection/search overlays — reset trackers
        self._text_sel_items = []
        self._selected_text = ""
        self._text_selecting = False
        self._search_items = []
        self._search_matches = []
        self._search_index = -1
        if self._search_bar is not None:
            self._search_bar.hide()

        self._rotation = 0
        for pno in range(document.page_count):
            item = PageItem(document, pno, 0.0)
            self._scene.addItem(item)
            self._page_items.append(item)
        self._layout_pages()

        # build items for pre-loaded annotations
        for ann in self.store.all():
            self._add_item_for(ann)
        self.store.add_listener(self._on_store_event)

        QTimer.singleShot(0, self.fit_width)
        QTimer.singleShot(0, self._render_visible)

    # -- page layout / rotation ---------------------------------------------

    def _page_scene_rect(self, item) -> QRectF:
        """The page's own rect in scene coords (honours its rotation), excluding
        child marks/shadow — used for layout, culling and hit-testing."""
        return item.mapToScene(item.rect()).boundingRect()

    def _layout_pages(self) -> None:
        """Stack pages vertically, applying the current view rotation to each.
        Annotation items are children of their page, so they rotate and stay
        aligned with the page automatically — nothing is written to disk."""
        from PySide6.QtGui import QTransform
        rot = QTransform()
        rot.rotate(self._rotation)
        mapped = [rot.mapRect(QRectF(0, 0, it.pdf_w, it.pdf_h)) for it in self._page_items]
        max_w = max([m.width() for m in mapped], default=1.0)
        top = 0.0
        for item, mr in zip(self._page_items, mapped):
            item.setRotation(self._rotation)
            x = (max_w - mr.width()) / 2.0          # centre pages horizontally
            item.setPos(x - mr.left(), top - mr.top())
            top += mr.height() + PAGE_GAP
        self._scene.setSceneRect(0, 0, max_w, max(top - PAGE_GAP, 1.0))

    def rotate_view(self, delta: int) -> None:
        """Rotate the whole document in the viewer by ``delta`` degrees (in
        memory only — the file on disk is never modified). Marks rotate with
        their page and snap back exactly when rotated the other way."""
        if not self._page_items:
            return
        self._rotation = (self._rotation + int(delta)) % 360
        self._layout_pages()
        self.fit_width()
        self._render_visible()

    @property
    def rotation(self) -> int:
        return self._rotation

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
            r = self._page_scene_rect(item)
            if r.bottom() >= lo and r.top() <= hi:
                item.render(scale)
            elif item.is_rendered() and (r.bottom() < vis.top() - 4 * margin
                                         or r.top() > vis.bottom() + 4 * margin):
                item.clear_render()
        self._emit_current_page()

    def _on_scroll(self, *_):
        self._render_timer.start()

    def _emit_current_page(self) -> None:
        vis = self._visible_scene_rect()
        mid = vis.center().y()
        for i, item in enumerate(self._page_items):
            r = self._page_scene_rect(item)
            if r.top() <= mid <= r.bottom():
                self.pageChanged.emit(i)
                return

    # -- zoom / fit ----------------------------------------------------------

    def set_zoom(self, zoom: float) -> None:
        zoom = max(0.1, min(zoom, 8.0))
        self._zoom = zoom
        self.resetTransform()
        self.scale(zoom, zoom)
        self._render_timer.start()
        self.zoomChanged.emit(zoom)

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.25)

    def fit_width(self):
        if not self._page_items:
            return
        page_w = self._page_scene_rect(self._page_items[0]).width()  # displayed width
        avail = self.viewport().width() - 24
        if page_w > 0:
            self.set_zoom(avail / page_w)

    def fit_page(self):
        if not self._page_items:
            return
        r = self._page_scene_rect(self._page_items[0])  # displayed size (rotated)
        aw = self.viewport().width() - 24
        ah = self.viewport().height() - 24
        if r.width() > 0 and r.height() > 0:
            self.set_zoom(min(aw / r.width(), ah / r.height()))

    def go_to_page(self, page_no: int):
        if 0 <= page_no < len(self._page_items):
            r = self._page_scene_rect(self._page_items[page_no])
            self.centerOn(r.center().x(), r.top() + 20)
            self._render_timer.start()

    def go_to_location(self, page_no: int, x: float, y: float):
        """Centre on a page-local point (PDF points) — used to jump a wire /
        component row to its spot on the drawing, with a brief pulse marker."""
        if not (0 <= page_no < len(self._page_items)):
            return
        page = self._page_items[page_no]
        self.centerOn(page.mapToScene(QPointF(x, y)))
        self._render_timer.start()
        self._pulse_at(page, x, y)

    def _pulse_at(self, page, x: float, y: float):
        """A short-lived ring drawn on the page to draw the eye to a jump target."""
        from PySide6.QtWidgets import QGraphicsEllipseItem
        from PySide6.QtGui import QPen
        old = getattr(self, "_pulse_item", None)
        if old is not None:
            try:
                self._scene.removeItem(old)
            except Exception:
                pass
        ring = QGraphicsEllipseItem(-14, -14, 28, 28, page)
        ring.setPos(x, y)
        ring.setPen(QPen(QColor(232, 119, 46), 2.0))
        ring.setBrush(QBrush(QColor(232, 119, 46, 60)))
        ring.setZValue(80)
        self._pulse_item = ring
        QTimer.singleShot(900, lambda: self._clear_pulse(ring))

    def _clear_pulse(self, ring):
        try:
            self._scene.removeItem(ring)
        except Exception:
            pass
        if getattr(self, "_pulse_item", None) is ring:
            self._pulse_item = None

    # -- events --------------------------------------------------------------

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
            self.set_zoom(self._zoom * factor)
            event.accept()
        else:
            super().wheelEvent(event)

    # -- drag & drop (open a dropped PDF) ------------------------------------

    @staticmethod
    def _dropped_pdf(event) -> str:
        md = event.mimeData()
        if md is not None and md.hasUrls():
            for u in md.urls():
                if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf"):
                    return u.toLocalFile()
        return ""

    def dragEnterEvent(self, event):
        if self._dropped_pdf(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._dropped_pdf(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        path = self._dropped_pdf(event)
        if path:
            self.requestOpen.emit(path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

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
        if self._search_bar is not None and self._search_bar.isVisible():
            self.hide_search()
            return
        if self._region_pick or self._region_item is not None:
            self.cancel_region_pick()
        if self._draft is not None:
            self._draft = None
            self._clear_preview()
        if self._erasing:
            self._end_erase()
        self._clear_text_selection()
        self._scene.clearSelection()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_down = False
            self.unsetCursor()
        super().keyReleaseEvent(event)

    def _page_at_scene(self, scene_pt: QPointF):
        for i, item in enumerate(self._page_items):
            if self._page_scene_rect(item).contains(scene_pt):
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
        _lp = page.mapFromScene(scene_pt)
        self._region_start = (_lp.x(), _lp.y())
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
        _lp = page.mapFromScene(scene_pt); lx, ly = _lp.x(), _lp.y()
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

        # Select tool: drag on empty page area selects text (Chrome-style).
        # But a click on a mark — or on one of its resize/rotate grips (which can
        # sit *outside* the mark's box, e.g. the rotate grip above it) — must act
        # on the mark, never start a text selection that would steal the gesture.
        if event.button() == Qt.LeftButton and self.tool.is_select():
            scene_pt = self.mapToScene(event.position().toPoint())
            on_mark = self._annotation_item_at(scene_pt) is not None
            on_grip = self._grip_item_at(scene_pt)
            if not on_mark and not on_grip:
                pno, page = self._page_at_scene(scene_pt)
                if page is not None:
                    self._scene.clearSelection()
                    _lp = page.mapFromScene(scene_pt)
                    self._begin_text_selection(pno, page, _lp.x(), _lp.y())
                    event.accept()
                    return
            else:
                self._clear_text_selection()
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
        if self._text_selecting and (event.buttons() & Qt.LeftButton):
            scene_pt = self.mapToScene(event.position().toPoint())
            _, page = self._text_sel_page
            _lp = page.mapFromScene(scene_pt); lx, ly = _lp.x(), _lp.y()
            self._update_text_selection(lx, ly)
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
        if self._text_selecting:
            self._text_selecting = False   # keep the highlight + copied text
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

    def _grip_item_at(self, scene_pt: QPointF) -> bool:
        """True if a resize/rotate grip is under the point (so a click there
        should resize/rotate the mark, not start a text selection)."""
        return any(getattr(it, "_is_grip", False)
                   for it in self._scene.items(scene_pt))

    def _begin_draft(self, scene_pt: QPointF) -> bool:
        pno, page = self._page_at_scene(scene_pt)
        if page is None:
            return False
        _lp = page.mapFromScene(scene_pt); lx, ly = _lp.x(), _lp.y()
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
        _lp = page.mapFromScene(scene_pt); lx, ly = _lp.x(), _lp.y()
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
        from PySide6.QtWidgets import QMessageBox
        anns = [a for a in (getattr(it, "ann", None)
                            for it in self._scene.selectedItems()) if a is not None]
        if not anns:
            return
        if len(anns) == 1:
            msg = f"Delete this {anns[0].kind}?\n\n{anns[0].snippet(80)}"
        else:
            msg = f"Delete these {len(anns)} marks?"
        resp = QMessageBox.question(self, "Delete", msg,
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        for ann in anns:
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

    def reveal_in_panel(self, ann: Annotation, target: str):
        """Ask the window to reveal this mark in the TODO list / comment sidebar."""
        self.requestReveal.emit(ann, target)

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
        self.centerOn(page.mapToScene(QPointF((x0 + x1) / 2, (y0 + y1) / 2)))
        item = self._item_by_ann.get(ann.id)
        if item is not None:
            item.setSelected(True)
            self._flash_item = item
            QTimer.singleShot(700, lambda: item.setSelected(False) if item else None)

    # -- text selection (Chrome-style, in Select mode) ----------------------

    def _begin_text_selection(self, pno, page, lx, ly):
        self._clear_text_selection()
        self._text_selecting = True
        self._text_sel_page = (pno, page)
        self._text_sel_start = (lx, ly)
        self._text_words = self._visual_words(pno)

    def _visual_words(self, pno):
        """Page words with bboxes mapped into the viewer's visual coordinate
        system.  PyMuPDF returns word boxes in *unrotated* coords, but the page
        bitmap (and mouse points) are in the rotated/visual system, so we apply
        ``page.rotation_matrix`` to keep highlights aligned on rotated pages."""
        try:
            page = self.document.fitz_doc[pno]
            rm = page.rotation_matrix
            out = []
            for w in page.get_text("words"):
                r = fitz.Rect(w[0], w[1], w[2], w[3]) * rm
                r.normalize()
                out.append((r.x0, r.y0, r.x1, r.y1, w[4], w[5], w[6], w[7]))
            return out
        except Exception:
            return []

    @staticmethod
    def _word_index_at(words, lx, ly):
        """Index of the word under (lx, ly), else the nearest word; -1 if none."""
        if not words:
            return -1
        for i, w in enumerate(words):
            if w[0] <= lx <= w[2] and w[1] <= ly <= w[3]:
                return i
        best, bi = None, -1
        for i, w in enumerate(words):
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            d = (cx - lx) ** 2 + (cy - ly) ** 2
            if best is None or d < best:
                best, bi = d, i
        return bi

    def _update_text_selection(self, lx, ly):
        words = self._text_words
        if not words or self._text_sel_start is None:
            return
        sx, sy = self._text_sel_start
        i0 = self._word_index_at(words, sx, sy)
        i1 = self._word_index_at(words, lx, ly)
        if i0 < 0 or i1 < 0:
            return
        lo, hi = (i0, i1) if i0 <= i1 else (i1, i0)
        selected = words[lo:hi + 1]
        self._draw_text_selection(selected)
        self._selected_text = _words_to_text(selected)

    def _draw_text_selection(self, selected):
        from PySide6.QtWidgets import QGraphicsRectItem
        from PySide6.QtGui import QPen
        self._remove_sel_items()
        _, page = self._text_sel_page
        brush = QBrush(QColor(70, 130, 230, 80))
        for w in selected:
            r = QGraphicsRectItem(w[0], w[1], w[2] - w[0], w[3] - w[1], page)
            r.setBrush(brush)
            r.setPen(QPen(Qt.NoPen))
            r.setZValue(5)  # above the page bitmap (1), below marks (10)
            self._text_sel_items.append(r)

    def _remove_sel_items(self):
        for it in self._text_sel_items:
            self._scene.removeItem(it)
        self._text_sel_items = []

    def _clear_text_selection(self):
        self._remove_sel_items()
        self._selected_text = ""
        self._text_selecting = False
        self._text_sel_page = None
        self._text_sel_start = None

    def copy_selection(self):
        """Copy the current text selection to the clipboard (Ctrl+C)."""
        if self._selected_text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self._selected_text)
            self.selectionInfo.emit(f"Copied {len(self._selected_text)} characters")

    # -- in-document search (Ctrl+F) ----------------------------------------

    def show_search(self):
        if self._search_bar is None:
            from .search_bar import SearchBar
            self._search_bar = SearchBar(self.viewport())
            self._search_bar.queryChanged.connect(self.run_search)
            self._search_bar.nextRequested.connect(self.search_next)
            self._search_bar.prevRequested.connect(self.search_prev)
            self._search_bar.closed.connect(self.hide_search)
        self._position_search_bar()
        self._search_bar.show()
        self._search_bar.raise_()
        self._search_bar.focus_input()
        # Re-run any text left in the box so reopening Ctrl+F re-highlights it
        # (otherwise the stale query sat there with no matches shown).
        text = self._search_bar.input.text().strip()
        if text:
            self.run_search(text)

    def hide_search(self):
        self._clear_search_highlights()
        self._search_matches = []
        self._search_index = -1
        if self._search_bar is not None:
            self._search_bar.hide()
        self.setFocus()

    def _position_search_bar(self):
        if self._search_bar is None:
            return
        bw = self._search_bar.width()
        self._search_bar.move(max(8, self.viewport().width() - bw - 16), 12)

    def run_search(self, query):
        self._clear_search_highlights()
        self._search_matches = []
        self._search_index = -1
        q = (query or "").strip()
        if q and self.document is not None:
            for pno in range(self.document.page_count):
                try:
                    page = self.document.fitz_doc[pno]
                    rm = page.rotation_matrix          # unrotated -> visual coords
                    rects = page.search_for(q)
                except Exception:
                    rects = []
                for r in rects:
                    vr = fitz.Rect(r) * rm
                    vr.normalize()
                    self._search_matches.append((pno, vr))
        if self._search_matches:
            self._draw_search_highlights()
            self._search_index = 0
            self._focus_current_match()
        self._update_search_count()

    def _research_if_stale(self) -> bool:
        """If there are no matches but the box still holds a query, search it
        now (lands on the first match). Returns True when it re-ran."""
        if self._search_matches or self._search_bar is None:
            return False
        q = self._search_bar.input.text().strip()
        if q:
            self.run_search(q)
            return True
        return False

    def search_next(self):
        if not self._search_matches:
            self._research_if_stale()
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        self._focus_current_match()
        self._update_search_count()

    def search_prev(self):
        if not self._search_matches:
            self._research_if_stale()
            return
        self._search_index = (self._search_index - 1) % len(self._search_matches)
        self._focus_current_match()
        self._update_search_count()

    def _draw_search_highlights(self):
        from PySide6.QtWidgets import QGraphicsRectItem
        from PySide6.QtGui import QPen
        self._clear_search_highlights()
        for pno, r in self._search_matches:
            if pno < 0 or pno >= len(self._page_items):
                self._search_items.append(None)
                continue
            page = self._page_items[pno]
            item = QGraphicsRectItem(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0, page)
            item.setBrush(QBrush(QColor(255, 213, 0, 90)))
            item.setPen(QPen(Qt.NoPen))
            item.setZValue(6)
            self._search_items.append(item)

    def _clear_search_highlights(self):
        for it in self._search_items:
            if it is not None:
                self._scene.removeItem(it)
        self._search_items = []

    def _focus_current_match(self):
        if not (0 <= self._search_index < len(self._search_matches)):
            return
        cur = QBrush(QColor(232, 119, 46, 170))   # orange accent
        other = QBrush(QColor(255, 213, 0, 90))    # yellow
        for i, it in enumerate(self._search_items):
            if it is not None:
                it.setBrush(cur if i == self._search_index else other)
        pno, r = self._search_matches[self._search_index]
        if 0 <= pno < len(self._page_items):
            page = self._page_items[pno]
            self.centerOn(page.mapToScene(QPointF((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)))
            self._render_timer.start()

    def _update_search_count(self):
        if self._search_bar is not None:
            n = len(self._search_matches)
            i = self._search_index + 1 if n else 0
            self._search_bar.set_count(i, n)

    # -- keep the floating search bar pinned on resize ----------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._search_bar is not None and self._search_bar.isVisible():
            self._position_search_bar()


def _words_to_text(words) -> str:
    """Join selected ``get_text('words')`` tuples back into text, preserving
    line breaks (words are (x0,y0,x1,y1, text, block, line, word_no))."""
    lines = {}
    order = []
    for w in words:
        key = (w[5], w[6])
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(w[4])
    return "\n".join(" ".join(lines[k]) for k in order)
