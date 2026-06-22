---
tags: [wire, extraction]
---

# Wire Numbers

The **Wire Numbers** tab finds the wire labels in your drawing set, classifies
them, and lets you spot-check before exporting. For the numbering scheme see
[[Wire Encoding]].

## Extract

Click **Extract wire numbers**. DSI Redline reads the text layer of every page
(and, if enabled, OCRs scanned pages — see [[OCR]]). It then parses and
classifies every candidate and de-duplicates identical labels, keeping a count.

The status line reports totals, e.g.
*"247 unique labels — 247 conforming, 0 fixed/OEM, 0 jumpers."*

## The table

Columns: include ✓ · Label · Sheet · Rung · Idx · Type · Pg · Count · Source ·
Flags. **Click a header to sort**; **drag column borders to resize** them.

Types are color-coded:
- **conforming** — parses cleanly to the field layout.
- **fixed/OEM** — a wire-ish token that doesn't follow the rule; still captured.
- **jumper** — on a "jumper" layer (excluded by default; only when the PDF
  exposes layers).

A **mismatch** flag appears when a label's sheet differs from a cross-checked
title-block sheet (only if you enable that in [[Settings]]).

`Source` is `text`, `ocr` or `ai` depending on how the label was read.

## Spot-check before export

- The **✓** column controls whether a row is exported. Untick anything you
  don't want (e.g. legend examples on a notes page).
- **Show** checkboxes filter the visible rows by type; the search box filters by
  label.
- **Check all / Uncheck all** toggle every *visible* row at once.
- Select multiple rows with **Shift/Ctrl-click**, then toggle one checkbox to
  apply the same state to the whole selection.
- **Double-click** a row to jump to that page in the [[Viewer]].

When you're happy, see [[Wire Export]].

#wire
