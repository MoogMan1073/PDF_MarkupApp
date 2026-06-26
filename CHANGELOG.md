# Changelog

All notable changes to **DSI Redline** are documented here. Versions are tagged
`vX.Y.Z`; each tag triggers the Windows build that publishes the installer and a
portable zip to the matching GitHub release.

## v1.0.3

Bug fixes (found in pre-beta testing):

- **Rotate grip works again.** Clicking a mark's resize/rotate grip now performs
  that action instead of starting a text selection — including the rotate grip,
  which sits just above the mark, and grips that overlap nearby text.
- **Ctrl+F re-searches stale text.** Reopening Find (or pressing Enter) with text
  already in the box re-runs the search and re-highlights the matches.
- **Delete key confirms.** Pressing `Delete` on a mark now shows the same "are
  you sure?" prompt as right-click / trash-bin delete (one prompt for a
  multi-selection).
- **Sheet auto-fill** now also reads the **bottom-right corner** of the title
  block (the lesser of the two numbers there) for drawings whose `THIS SHEET:`
  label isn't in the text layer. Still best-effort; the Sheet column stays
  editable.
- **TODO rows no longer drag-reorder** (filter + sort cover it; avoids accidental
  nesting).
- **Wire / Component double-click** now jumps to the label's spot on the drawing
  (the first occurrence for labels that repeat) with a brief pulse marker.
- **More known family codes:** `CBL, DV, EN, DN, GND, PDB, PRS, PW, SCR, SE, X`.
- **Family-code edits take effect immediately** — changing the known codes (or
  widths) in Settings re-flags already-extracted component labels without a
  re-extract.

New features:

- **Opening an already-open PDF** is blocked with a notice (a file and its
  `.marked.pdf` count as the same document).
- **Export hotkey:** `Ctrl+Shift+E` exports the annotated PDF.
- **One markup database, one `.marked.pdf`.** Opening a `.marked.pdf` reuses the
  original's single `.markup.db` (never a second one), and saving always updates
  the same `.marked.pdf` (never `.marked.marked.pdf`). If the original markup
  database is missing, a new one is started and you're told.
- **TODO filter** now matches across **all** columns (text, page, sheet,
  commenter, tags).

## v1.0.2

- **Viewer rotate is now in-memory and non-destructive.** The ribbon **↺ / ↻**
  rotate the whole document in the viewer only — nothing is written to disk, and
  rotating back (or a full turn) restores everything exactly. Markups, comments
  and highlights rotate with their page and stay correctly placed. (To bake a
  rotation into a saved file, use the **Rotate** tool in PDF Tools.)
- **Navigation pane jumps to the Viewer.** Selecting a page thumbnail or
  bookmark while on another tab now switches back to the Viewer and shows it.

## v1.0.1

- **Open PDFs with DSI Redline.** The Windows installer registers the app so it
  appears in the right-click **"Open with"** list and the **Default apps**
  picker; opening a PDF that way loads it into the Viewer and PDF Tools tabs.
  (Non-destructive — it never hijacks your current default handler.)
- **TODO tab:** double-click now edits the cell (Text / Sheet / Tag); the page
  cell stays read-only and jumps to the mark (also via right-click). Right-click
  a mark on the PDF to **reveal it in the TODO list / Comments**.
- **Sheet numbers:** grouping renamed Sheet → **Page**; added a real **Group:
  Sheet** plus an editable per-page **Sheet** column, auto-detected from the
  title block on searchable PDFs.
- **Viewer ribbon:** editable **zoom %** box.
- **Settings** organised into tabs; **Wire Numbers** gained a scanned-page
  AI/OCR engine picker.
- Crop/extract reconstructs tables best-effort from OCR geometry when no AI key
  is set.

## v1.0.0

- First stable release: continuous-scroll PDF viewer with markup, a
  comment/TODO workflow, wire-number and component-label extraction/export, PDF
  page tools, viewer text search, and the crop/extract wizard.
