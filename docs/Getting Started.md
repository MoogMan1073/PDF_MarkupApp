---
tags: [basics, install]
---

# Getting Started

## Install

DSI Redline needs **Python 3.11+**. From the app folder:

```bash
pip install -r requirements.txt
python main.py
```

You can also open a file directly: `python main.py drawings.pdf`.

Optional extras:
- **Tesseract** — only for scanned/raster pages. See [[OCR]].
- **Anthropic API key** — only for AI assist. See [[AI Assist]].

The app is fully functional offline with neither of these.

## Open a PDF

**File ▸ Open PDF…** (`Ctrl+O`). The drawing loads in the [[Viewer]] with
continuous vertical scroll. Any annotations already in the PDF (for example a
colleague's markup) are imported with their original authors — see
[[Storage and Files]].

## Three tabs

DSI Redline is organised into three tabs:

1. **Viewer** — read and mark up the drawing. See [[Viewer]] and [[Markup Tools]].
2. **TODO** — your action items. See [[TODO]].
3. **Wire Numbers** — extract and export wire labels. See [[Wire Numbers]].

The **Comments** panel docks on the right of the Viewer — see
[[Comments Sidebar]].

## Save your work

- **File ▸ Save markup** (`Ctrl+S`) writes `<name>.marked.pdf` plus a
  `<name>.markup.db` sidecar. Your original PDF is never modified.
- **File ▸ Export annotated PDF…** writes a standalone annotated copy anywhere.

Full detail in [[Storage and Files]].

#basics
