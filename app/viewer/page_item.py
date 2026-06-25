"""One page on the canvas.

Coordinate convention for the whole viewer: **scene units == PDF points**.
A :class:`PageItem` is a rect of the page's point-size positioned at its vertical
offset in the continuous scroll.  The rendered bitmap is a child pixmap scaled to
fit, so zoom is handled purely by the view transform and annotation items can use
plain PDF-point coordinates.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap, QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsPixmapItem

import fitz


def pixmap_to_qimage(pix: "fitz.Pixmap") -> QImage:
    """Convert a PyMuPDF pixmap to a (deep-copied) QImage."""
    fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
    img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
    return img.copy()  # detach from the pixmap's buffer


class PageItem(QGraphicsRectItem):
    """A page background (white + subtle shadow) hosting its rendered bitmap."""

    SHADOW = 4  # points

    def __init__(self, document, page_no: int, top: float):
        self.doc = document
        self.page_no = page_no
        rect = document.page_rect(page_no)
        self.pdf_w = float(rect.width)
        self.pdf_h = float(rect.height)
        super().__init__(0.0, 0.0, self.pdf_w, self.pdf_h)
        self.setPos(0.0, top)
        self.setBrush(QBrush(QColor("white")))
        self.setPen(QPen(QColor(200, 200, 200), 0))
        self.setZValue(0)

        # subtle drop shadow drawn behind the page
        self._shadow = QGraphicsRectItem(
            self.SHADOW, self.SHADOW, self.pdf_w, self.pdf_h, self)
        self._shadow.setBrush(QBrush(QColor(0, 0, 0, 40)))
        self._shadow.setPen(QPen(Qt.NoPen))
        self._shadow.setZValue(-1)

        self._pixmap_item = QGraphicsPixmapItem(self)
        self._pixmap_item.setZValue(1)
        self._pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        self._render_scale = 0.0  # not yet rendered

    # -- rendering -----------------------------------------------------------

    def is_rendered(self) -> bool:
        return self._render_scale > 0.0

    def render(self, scale: float) -> None:
        """Render (or re-render) the bitmap at the given DPI scale."""
        scale = max(0.5, min(float(scale), 6.0))
        # avoid needless re-renders for tiny zoom changes
        if self._render_scale and abs(scale - self._render_scale) / self._render_scale < 0.35:
            return
        pix = self.doc.get_pixmap(self.page_no, zoom=scale)
        qpix = QPixmap.fromImage(pixmap_to_qimage(pix))
        self._pixmap_item.setPixmap(qpix)
        # scale the (scale*W x scale*H) bitmap back down to W x H points
        self._pixmap_item.setScale(1.0 / scale)
        self._render_scale = scale

    def clear_render(self) -> None:
        self._pixmap_item.setPixmap(QPixmap())
        self._render_scale = 0.0

    # -- geometry helpers ----------------------------------------------------

    def scene_top(self) -> float:
        return self.pos().y()

    def scene_bottom(self) -> float:
        return self.pos().y() + self.pdf_h
