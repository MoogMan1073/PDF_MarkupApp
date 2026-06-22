# PDF Markup + Wire-Number Extractor

A lightweight, fast desktop app for reviewing AutoCAD Electrical drawing sets
(industrial-controls prints). It feels like the Chrome PDF viewer — clean
continuous vertical scroll, minimal chrome — and adds markup tools, a
comment/TODO workflow, and a **wire-number extraction & export engine**.

Built with Python + PySide6 + PyMuPDF. Fully functional offline; AI is optional.

---

## Features

- **Viewer** — open a PDF, continuous vertical scroll with page shadows, Ctrl+scroll
  zoom, fit-width / fit-page, space/middle-drag pan, page navigation. Pages render
  lazily and re-render crisper as you zoom in.
- **Markup tools** — select/move/resize, highlight, freehand pen, eraser, sticky-note
  comments, on-page text boxes, plus rectangle & arrow shapes. Full undo/redo
  (`Ctrl+Z` / `Ctrl+Shift+Z`). Every mark records its author and timestamp.
- **Hybrid storage** — marks are saved as standard PDF annotations into a
  `*.marked.pdf` copy (the original is **never** overwritten), while app-only state
  (TODO status, tags, wire cache) lives in a `*.markup.db` SQLite sidecar. Existing
  PDF annotations (e.g. a colleague's markup) are imported with their real authors.
- **SHX / AutoCAD junk filter** — nuisance "SHX font could not be displayed" export
  comments are hidden (not deleted) and excluded from counts. Toggle "Show ignored"
  to reveal them. The pattern list is editable in Settings.
- **Comment sidebar** — dockable, filterable, sortable list of all comments; click to
  scroll to and flash the mark.
- **TODO tab** — flag any comment/text box as a TODO; check off, edit inline, group by
  sheet/commenter, and export to **Markdown** (GitHub task list) or **DOCX** (table
  with ☐/☑ glyphs).
- **Wire Numbers tab** — extract, classify, spot-check and export wire numbers.
- **Wire export** — `.xlsx` / `.csv`, single-file (`~sheet~` separators, labels-only)
  or one-file-per-sheet (full columns), configurable labels-per-wire, and multiple
  sort/filter modes.

---

## Wire-number encoding

Each wire label is a self-describing numeric string:

```
[ S S S ][ R R ][ W ]
  sheet    rung   wire-index-on-rung (0-based)
```

Default field widths are **sheet = 3, rung = 2, wire = 1** (6 digits total), all
configurable in Settings. Example: the **second** wire on **rung 14** of **sheet 432**
→ `432141` (the index is 0-based, so the first wire is `432140`). The sheet number
always comes from the label's own first digits — never from PDF page order.

Classification:

- **conforming** — parses cleanly to the configured field layout.
- **fixed / OEM** — a wire-ish token that doesn't follow the rule (legacy/OEM sets);
  still captured and labelled so you can include or exclude it.
- **jumper** — tokens on a layer whose name contains "jumper" (excluded by default).
  Jumper handling is silently skipped when the PDF exposes no layer data.

---

## Install

Requires **Python 3.11+**.

```bash
pip install -r requirements.txt
```

### Tesseract (optional — only for scanned/raster pages)

OCR fallback needs the Tesseract system binary in addition to the `pytesseract`
Python wrapper:

- **Ubuntu/Debian:** `sudo apt install tesseract-ocr`
- **macOS:** `brew install tesseract`
- **Windows:** install from the [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki)
  and ensure it's on your `PATH`.

If Tesseract isn't present, the app still works — it just relies on the PDF text
layer (which is all that's needed for vector AutoCAD plots).

### Claude AI assist (optional — opt-in)

For OCR'ing/disambiguating wire numbers on scanned regions you can enable Claude
vision in Settings. Set an API key first:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

The app is **fully functional with no key** — AI is never required.

---

## Run

```bash
python main.py            # then File ▸ Open PDF…
python main.py drawings.pdf   # or open a file directly
```

---

## A quick tour

| Tab | What it does |
|-----|--------------|
| **Viewer** | Read and mark up the drawing. Pick a tool from the toolbar, choose a color/width, and draw. The **Comments** dock on the right lists every note. |
| **TODO** | Everything flagged as a TODO. Check items off, edit text inline, group by sheet/commenter, and export to Markdown or DOCX. |
| **Wire Numbers** | Click **Extract wire numbers** to scan the set. Review the table (label, sheet, rung, index, type, page, count, source), untick any you don't want, then **Export…**. |

### Saving

- **File ▸ Save markup** writes `<name>.marked.pdf` + syncs the `<name>.markup.db`
  sidecar. The original PDF is untouched.
- **File ▸ Export annotated PDF…** writes a standalone annotated copy anywhere.

### Settings

Your name (commenter), wire field widths & zero-padding, full-label regex override,
labels-per-wire, the SHX/junk ignore-pattern list, "treat all comments as TODO",
OCR/AI toggles, and export defaults — all persisted between sessions.

---

## Project layout

```
main.py                      QApplication entry
app/
  main_window.py             Window: Viewer | TODO | Wire Numbers, toolbar, Settings
  config.py                  Persisted settings (QSettings) + defaults
  viewer/                    Continuous-scroll canvas, annotation items, tools, undo
  model/                     Document, annotation model, PDF+SQLite storage
  panels/                    Comment sidebar, TODO tab, Wire Numbers tab
  extraction/                Text extraction, OCR, wire parser/classifier, Claude assist
  export/                    TODO (md/docx) and wire (xlsx/csv) exporters
tests/                       Unit tests for the extraction/export/storage core
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests
```

The pure-logic core (wire parsing/classification, both export modes, the PDF
annotation round-trip and SHX filter, TODO export) is covered by the suite.
