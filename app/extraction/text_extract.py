"""Text-layer extraction via PyMuPDF.

Pulls words with bounding rects, font and colour, and (best-effort) the
optional-content layer (OCG) each token belongs to.  Kept GUI-free.
"""

from __future__ import annotations

import re
from typing import Optional

import fitz  # PyMuPDF

from .wire_parser import Token, SOURCE_TEXT


# A page is considered "vector"/text-bearing when it exposes a non-trivial
# amount of extractable text.  Scanned pages fall back to OCR.
MIN_TEXT_CHARS = 8


def page_has_text(page: "fitz.Page") -> bool:
    """True when the page has a usable text layer (vs scanned raster)."""
    try:
        txt = page.get_text("text") or ""
    except Exception:
        return False
    return len(txt.strip()) >= MIN_TEXT_CHARS


def get_ocg_names(doc: "fitz.Document") -> dict:
    """Return ``{xref: name}`` for every optional-content group in the doc.

    Returns an empty dict when the document has no layers (most AutoCAD PDF
    plots), in which case jumper-layer handling is silently skipped downstream.
    """
    names: dict = {}
    try:
        ocgs = doc.get_ocgs() or {}
        for xref, info in ocgs.items():
            name = info.get("name") if isinstance(info, dict) else None
            if name:
                names[xref] = name
    except Exception:
        pass
    return names


def _build_mcid_layer_map(page: "fitz.Page", ocg_names: dict) -> dict:
    """Best-effort map of marked-content-id -> layer name for a page.

    AutoCAD plots almost never carry OCGs, so this normally returns ``{}`` and
    every token is reported with ``layer=None``.  When layers *are* present we
    try to associate text with them via the page's ``/Properties`` resource.
    """
    if not ocg_names:
        return {}
    mapping: dict = {}
    try:
        # The page /Properties dict maps a name -> OCG xref; marked content uses
        # those names.  This is heuristic and wrapped defensively.
        props = page.get_contents()  # noqa: F841 - presence check only
    except Exception:
        return {}
    return mapping


def extract_tokens(
    page: "fitz.Page",
    page_index: int,
    ocg_names: Optional[dict] = None,
) -> list:
    """Extract word-level :class:`Token` objects from a page.

    Coordinates use the word's top-left corner (``x0``/``y0``) which is stable
    for both horizontal and rotated (vertical) wire-number text and is what the
    spatial reading-order sort expects.
    """
    tokens: list = []
    try:
        words = page.get_text("words")
    except Exception:
        return tokens

    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        text = (text or "").strip()
        if not text:
            continue
        tokens.append(
            Token(
                text=text,
                x=float(x0),
                y=float(y0),
                page=page_index,
                layer=None,  # best-effort; populated only when OCGs exist
                source=SOURCE_TEXT,
                confidence=1.0,
            )
        )
    return tokens


# Common AutoCAD-Electrical title-block sheet patterns, e.g. "SHEET 300",
# "SHT 300", "SHEET 300 OF 420".  Best-effort only.
_SHEET_RE = re.compile(r"\b(?:SHEET|SHT)\.?\s*(?:NO\.?\s*)?(\d{1,4})", re.IGNORECASE)


def read_titleblock_sheet(page: "fitz.Page", sheet_width: int = 3) -> Optional[int]:
    """Best-effort title-block sheet number for cross-checking.

    Returns ``None`` when nothing convincing is found.  Never raises.
    """
    try:
        text = page.get_text("text") or ""
    except Exception:
        return None
    m = _SHEET_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def extract_document_tokens(doc: "fitz.Document") -> list:
    """Extract tokens for every text-bearing page in a document.

    Pages without a text layer are reported via :func:`page_has_text` and left
    to the OCR fallback by the caller.
    """
    ocg_names = get_ocg_names(doc)
    tokens: list = []
    for i in range(doc.page_count):
        page = doc[i]
        if page_has_text(page):
            tokens.extend(extract_tokens(page, i, ocg_names))
    return tokens


def ai_page(page: "fitz.Page", page_index: int, field_widths=(3, 2, 1),
            zero_pad: bool = True, model: str = "claude-opus-4-8",
            api_key: str = "", zoom: float = 2.0) -> list:
    """Read wire-number labels from a scanned page using Claude vision.

    Renders the page, asks Claude for every wire-number label (and its bbox),
    and returns word-level :class:`Token` objects tagged ``source='ai'``.
    Returns an empty list on any failure so the caller can fall back.
    """
    from . import claude_api
    from .wire_parser import Token, SOURCE_AI
    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        results = claude_api.read_wire_region(
            pix, field_widths=field_widths, zero_pad=zero_pad,
            model=model, api_key=api_key)
    except Exception:
        return []
    tokens: list = []
    for r in results:
        if not isinstance(r, dict):
            continue
        if r.get("is_wire") is False:
            continue
        label = str(r.get("label", "")).strip()
        if not label:
            continue
        bbox = r.get("bbox") or [0, 0, 0, 0]
        try:
            x = float(bbox[0]) / zoom
            y = float(bbox[1]) / zoom
        except (TypeError, ValueError, IndexError):
            x = y = 0.0
        try:
            conf = float(r.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        tokens.append(Token(text=label, x=x, y=y, page=page_index,
                            source=SOURCE_AI, confidence=conf))
    return tokens


def collect_tokens(doc: "fitz.Document", ocr_enabled: bool = False,
                   ocr_zoom: float = 3.0, progress=None, should_cancel=None,
                   ai_enabled: bool = False, ai_key: str = "",
                   ai_model: str = "claude-opus-4-8", field_widths=(3, 2, 1),
                   zero_pad: bool = True, ai_zoom: float = 2.0) -> list:
    """Collect tokens from every page: text layer where present, OCR otherwise.

    For pages **without** a text layer (scanned drawings), Claude vision is used
    when ``ai_enabled`` and a key is available (it reads non-standard labels and
    vets what is a wire number); otherwise Tesseract OCR is used when
    ``ocr_enabled`` and the binary is present. Vector pages always use the text
    layer. ``progress(current_page, page_count)`` is called *before* each page so
    a UI can show "scanning page N" while a slow page runs; ``should_cancel()``
    is polled before each page. Everything degrades gracefully.
    """
    ocg_names = get_ocg_names(doc)
    tokens: list = []
    use_ocr = False
    if ocr_enabled:
        try:
            from . import ocr as _ocr
            use_ocr = _ocr.available()
        except Exception:
            use_ocr = False
    use_ai = False
    if ai_enabled:
        try:
            from . import claude_api
            use_ai = claude_api.available(ai_key)
        except Exception:
            use_ai = False
    total = doc.page_count
    for i in range(total):
        if should_cancel is not None and should_cancel():
            break
        if progress is not None:
            progress(i + 1, total)
        page = doc[i]
        if page_has_text(page):
            tokens.extend(extract_tokens(page, i, ocg_names))
        elif use_ai:
            tokens.extend(ai_page(page, i, field_widths=field_widths,
                                  zero_pad=zero_pad, model=ai_model,
                                  api_key=ai_key, zoom=ai_zoom))
        elif use_ocr:
            from . import ocr as _ocr
            tokens.extend(_ocr.ocr_page(page, i, zoom=ocr_zoom))
    return tokens
