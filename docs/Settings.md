---
tags: [settings, reference]
---

# Settings

Open with **File ▸ Settings…**. Everything here persists between sessions.

## Identity
- **Your name** — stamped as the commenter on every new mark.

## Wire number fields
- **Sheet / Rung / Wire-index width** and **Zero-pad** — define the label layout
  ([[Wire Encoding]]).
- **Full-label regex** — optional override of the detection pattern (e.g. `^\d{6}$`).
- **Cross-check sheet** — flag labels whose sheet differs from a title-block
  reading (off by default to avoid false flags on multi-sheet pages).

## Export defaults
- **Labels per wire**, **default mode** (single / per-sheet), **default format**
  (xlsx / csv). See [[Wire Export]].

## Comments & junk filter
- **Treat all comments as TODO** — new comments start flagged ([[TODO]]).
- **Show ignored** — reveal SHX/AutoCAD junk that's hidden by default.
- **Ignore patterns** — one regex per line; matching annotations are hidden, not
  deleted. See [[Storage and Files]].

## OCR & AI assist
- **Enable OCR fallback** — use Tesseract on scanned pages ([[OCR]]).
- **Enable Claude vision assist**, **API key**, **Check API status**,
  **AI model**, **AI region size** — see [[AI Assist]].

#settings #reference
