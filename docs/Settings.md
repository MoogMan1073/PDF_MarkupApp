---
tags: [settings, reference]
---

# Settings

Open with **File ▸ Settings…**. Everything here persists between sessions. The
dialog is split into tabs — **General**, **Wire numbers**, **Component labels**
and **OCR / AI** — so it stays compact on any screen.

## General
- **Your name** — stamped as the commenter on every new mark.
- **Export defaults** and **Comments & junk filter** (below).

## Wire number fields
- **Sheet / Rung / Wire-index width** and **Zero-pad** — define the label layout
  ([[Wire Encoding]]).
- **Full-label regex** — optional override of the detection pattern (e.g. `^\d{6}$`).
- **Cross-check sheet** — flag labels whose sheet differs from a title-block
  reading (off by default to avoid false flags on multi-sheet pages).
- **Scanned-page method** — default engine (**AI assist** or **OCR**) for pages
  with no text layer. You can also switch it per run from the Wire Numbers tab.

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
