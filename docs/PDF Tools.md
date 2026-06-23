---
tags: [tools, pdf, basics]
---

# PDF Tools

The **PDF Tools** tab (and the **Tools** menu) bundle common PDF-set chores.
Every operation runs in the background with a progress bar and never overwrites
your input — you always choose an output file or folder.

## Organize

- **Split into pages** — one file per page, named by page number.
- **Combine PDFs** — merge several PDFs into one; add files and **drag to
  reorder**, or add a whole folder (sorted by the number in each filename).
- **Insert PDF** — drop one PDF into another before a chosen page.
- **Swap a page** — replace a single page with a one-page PDF.
- **Delete pages** — remove pages by range, e.g. `1,3,5-7`.
- **Rotate** — rotate all pages, or a subset (`2,4-6`), by 90/180/270°.

## Sheet-number split (wizard)

Splits a set into one file per page **named by the drawing's sheet number**
instead of the page number — driven by a guided wizard so it works on any title
block:

1. You're prompted to drag a box around the **sheet number on page 1**.
2. A preview shows the text it read and lets you pick the rule (first number /
   smaller of two / exact text) with a live result.
3. Choose **same box for all pages**, or **add boxes** for other title-block
   styles. For extra boxes, navigate with the **Pages/Bookmarks** panel or
   scroll, draw the box, and say which pages it applies to (this page / to the
   end / through page N).
4. Pick an output folder and split. Pages whose box reads nothing fall back to
   page-number naming and are reported so you can adjust.

Scanned pages without text are read with **OCR or Claude** when enabled
([[AI Assist]], [[OCR]]).

## Convert & extract

- **PDF → Word** — convert a PDF to an editable `.docx`.
- **Crop / extract (wizard)** — box one or more regions across pages and export
  them as **PNGs**. Optionally, the app sends those crops to **Claude** to build
  a **TAG / DESCRIPTION** table (xlsx) automatically — handy for turning device
  labels into a tag list. Requires AI enabled + an API key ([[AI Assist]]).

Related: [[Viewer]] · [[Settings]] · [[Wire Numbers]]

#tools
