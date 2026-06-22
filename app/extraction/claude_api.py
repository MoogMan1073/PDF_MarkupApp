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


def resolve_key(explicit: Optional[str] = None) -> str:
    """Return the API key to use: an explicit key wins, else the env var."""
    key = (explicit or "").strip()
    if key:
        return key
    return (os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def sdk_installed() -> bool:
    try:
        import anthropic  # noqa: F401
        return True
    except Exception:
        return False


def available(api_key: Optional[str] = None) -> bool:
    """True when the SDK is importable and an API key is present."""
    return sdk_installed() and bool(resolve_key(api_key))


def status(api_key: Optional[str] = None) -> tuple:
    """Quick, network-free status: ``(state, message)``.

    state is one of: "no_sdk", "missing", "present".  Use :func:`validate_key`
    for an authoritative (network) check.
    """
    if not sdk_installed():
        return ("no_sdk", "anthropic SDK not installed (pip install anthropic)")
    key = resolve_key(api_key)
    if not key:
        return ("missing", "No API key set")
    if not key.startswith("sk-"):
        return ("present", "Key set (format looks unusual)")
    return ("present", "Key set (not yet verified)")


def validate_key(api_key: Optional[str] = None, model: str = DEFAULT_MODEL) -> tuple:
    """Authoritative check via a minimal API call. Returns ``(valid, message)``.

    Never raises; returns ``(False, reason)`` on any error.
    """
    if not sdk_installed():
        return (False, "anthropic SDK not installed")
    key = resolve_key(api_key)
    if not key:
        return (False, "No API key set")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(
            model=model, max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
        return (True, "Key is valid")
    except Exception as e:
        name = type(e).__name__
        msg = str(e)
        if "auth" in msg.lower() or "401" in msg or "AuthenticationError" in name:
            return (False, "Invalid API key (authentication failed)")
        return (False, f"Could not verify key: {name}")


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
                     max_tokens: int = 1024,
                     api_key: Optional[str] = None) -> list:
    """Send a rendered region to Claude and return parsed wire dicts.

    ``pix`` is a :class:`fitz.Pixmap`.  Returns ``[]`` on any failure so callers
    can always fall back to Tesseract + rules.
    """
    key = resolve_key(api_key)
    if not (sdk_installed() and key):
        return []
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
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
