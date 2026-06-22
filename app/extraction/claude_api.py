"""Optional Claude vision assist (Phase 8) - strictly opt-in.

Used only to OCR/parse wire numbers on scanned regions and to disambiguate
low-confidence candidates ("is this a wire number or a terminal/part number?").
The app is fully functional without an API key: every entry point degrades
gracefully when ``anthropic`` or ``ANTHROPIC_API_KEY`` is missing.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
from typing import Optional

DEFAULT_MODEL = "claude-opus-4-8"


def available() -> bool:
    """True when the SDK is importable and an API key is present."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def _pixmap_to_png_b64(pix) -> str:
    return base64.b64encode(pix.tobytes("png")).decode("ascii")


def _build_prompt(field_widths: tuple, zero_pad: bool) -> str:
    sw, rw, ww = field_widths
    return (
        "You are reading wire-number labels from a region of an AutoCAD "
        "Electrical drawing. A wire number encodes, left to right: "
        f"sheet ({sw} digits), rung ({rw} digits, "
        f"{'zero-padded' if zero_pad else 'not zero-padded'}), and a 0-based "
        f"wire index on the rung ({ww} digit). For example 432141 = sheet 432, "
        "rung 14, wire index 1 (the second wire on that rung).\n\n"
        "Return ONLY a JSON array. Each element: "
        '{"label": str, "sheet": int|null, "rung": int|null, '
        '"wire_index": int|null, "is_wire": bool, "confidence": 0..1, '
        '"bbox": [x0,y0,x1,y1]}. '
        "Set is_wire=false for terminal numbers, part numbers or other text. "
        "No prose, no markdown fences."
    )


def _extract_json(text: str):
    """Pull a JSON array out of a model response, defensively."""
    text = text.strip()
    # strip code fences if present
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return []
    return []


def read_wire_region(pix, field_widths: tuple = (3, 2, 1),
                     zero_pad: bool = True,
                     model: str = DEFAULT_MODEL,
                     max_tokens: int = 1024) -> list:
    """Send a rendered region to Claude and return parsed wire dicts.

    ``pix`` is a :class:`fitz.Pixmap`.  Returns ``[]`` on any failure so callers
    can always fall back to Tesseract + rules.
    """
    if not available():
        return []
    try:
        import anthropic
        client = anthropic.Anthropic()
        b64 = _pixmap_to_png_b64(pix)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": _build_prompt(field_widths, zero_pad)},
                ],
            }],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return _extract_json("".join(parts))
    except Exception:
        return []
