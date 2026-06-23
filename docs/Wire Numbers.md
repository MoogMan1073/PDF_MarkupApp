---
tags: [wire, extraction]
---

# Wire Numbers

The **Wire Numbers** tab finds the wire labels in your drawing set, classifies
them, and lets you spot-check before exporting. For the numbering scheme see
[[Wire Encoding]].

## Extract

Click **Extract wire numbers**. DSI Redline reads the text layer of every page;
for **scanned pages with no text** it uses **Claude vision** (if enabled — see
[[AI Assist]]) or **Tesseract OCR** (see [[OCR]]). It then parses, classifies and
de-duplicates the candidates.

A **progress bar** shows it scanning page-by-page, with a **Cancel** button —
important for scanned sets, where reading can take a while. The work runs in the
background so the app never freezes.

The status line reports totals, e.g.
*"247 unique labels — 247 conforming, 0 fixed/OEM, 0 jumpers."* If a set is
scanned and neither AI nor OCR is on, it tells you so — enable one in
[[Settings]] and extract again.

> **Non-standard sets:** AI reads labels even when they don't match the
> configured width (e.g. 5-digit codes). Those come through as **fixed/OEM** so
> you still capture them; adjust the field widths in [[Settings]] to make them
> *conforming*.

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
