"""OCR fallback for scanned/raster pages (Phase 8).

Uses Tesseract via ``pytesseract``.  Optional: if the binary or the Python
wrapper is missing the module degrades gracefully (``available()`` returns
False) and the app continues with the text-layer pipeline only.
"""

from __future__ import annotations

from typing import Optional

import fitz  # PyMuPDF

from .wire_parser import Token, SOURCE_OCR

# Render scanned pages at a higher DPI so small wire numbers survive OCR.
DEFAULT_OCR_ZOOM = 3.0
# pytesseract confidence is 0..100; below this we treat a word as low-confidence
# (a candidate for AI disambiguation).
LOW_CONF = 55.0


def available() -> bool:
    """True when both ``pytesseract`` and the Tesseract binary are usable."""
    try:
        import pytesseract  # noqa: F401
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_page(page: "fitz.Page", page_index: int,
             zoom: float = DEFAULT_OCR_ZOOM,
             min_conf: float = 0.0) -> list:
    """OCR a single page and return word-level :class:`Token` objects.

    Token coordinates are mapped back to PDF points (so they line up with the
    text-layer pipeline and the spatial reading-order sort).  Returns an empty
    list when OCR is unavailable.
    """
    if not available():
        return []
    import pytesseract
    from PIL import Image
    import io

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    tokens: list = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf < min_conf:
            continue
        # pixel -> PDF point
        x = data["left"][i] / zoom
        y = data["top"][i] / zoom
        tokens.append(Token(
            text=text, x=float(x), y=float(y), page=page_index,
            layer=None, source=SOURCE_OCR,
            confidence=max(0.0, conf) / 100.0,
        ))
    return tokens


def is_low_confidence(token: Token) -> bool:
    return token.source == SOURCE_OCR and token.confidence * 100.0 < LOW_CONF
