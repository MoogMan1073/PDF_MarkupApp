---
tags: [storage, files, reference]
---

# Storage and Files

DSI Redline uses a **hybrid** model so your marks are both portable and lossless.

## What gets written

Next to your PDF (`drawing.pdf`):

- **`drawing.marked.pdf`** — a copy with every mark written as a **standard PDF
  annotation**. Open it in Adobe, Chrome, etc. Sticky-note comments carry a real
  popup. Your **original PDF is never modified**.
- **`drawing.markup.db`** — a SQLite **sidecar** holding app-only state: TODO
  status, tags, extra styling, rotation, and the cached wire numbers. This is the
  source of truth for marks this app created.

Save with **File ▸ Save markup** (`Ctrl+S`). Use **Export annotated PDF…** to
write a copy anywhere.

## Opening a marked-up PDF from someone else

When you open a PDF, DSI Redline imports any annotations already inside it
(highlights, notes, text boxes) **with their original authors and dates**, so
received markups show up correctly in the [[Comments Sidebar]].

## SHX / AutoCAD junk filter

AutoCAD's PDF export often injects "SHX font could not be displayed" notices.
These match the **ignore patterns** in [[Settings]] and are **hidden, never
deleted** — excluded from the sidebar, TODO and counts. Toggle **Show ignored**
to see them.

#storage #reference
