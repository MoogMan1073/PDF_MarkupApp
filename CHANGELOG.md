# Changelog

All notable changes to **DSI Redline** are documented here. Versions are tagged
`vX.Y.Z`; each tag triggers the Windows build that publishes the installer and a
portable zip to the matching GitHub release.

## v1.2.0

- **Copy & paste marks.** Text boxes, callouts, rectangles, arrows and clouds can
  be copied (**`Ctrl+C`** or right-click ▸ **Copy**) and pasted (**`Ctrl+V`**, or
  right-click empty canvas ▸ **Paste … here**). Multi-select copies together;
  repeated pastes cascade so they don't stack; pasted marks land selected and are
  undoable as one step.
- **Format painter.** Right-click ▸ **Copy formatting** then **Paste formatting**
  onto another mark **of the same type** to transfer its colour, opacity, fill,
  border width and font — without touching the target's text or geometry.
- **Sticky styles.** Setting a colour, opacity, fill or font on a new text box or
  callout is remembered as the default for the next one, so styles don't have to
  be re-declared for every mark (the text content is never carried over).

## v1.1.0

Feature release from the user-group feedback sprint.

New markup:

- **Notes on any mark.** Any mark — highlight, pen, rectangle, arrow, cloud — can
  carry a free note, not just comments and text boxes. Right-click a mark ▸ **Add
  note… / Edit note…**; noted marks get a small orange corner badge, appear in
  the Comments sidebar (now with **Rectangle / Arrow / Callout / Cloud** filters),
  and on export each note also becomes a **standalone sticky-note comment** so
  it's visible in any viewer (Adobe, browsers, Preview).
- **Fill & opacity for rectangles and text boxes.** The new toolbar **Fill**
  button opens a color picker with a plain **opacity slider** (0% = no fill →
  100% = an opaque white **cover** that redacts what's beneath). Text boxes get a
  fill control in their editor; rectangles expose **Fill…** on right-click. Fills
  render on screen and in the exported PDF.
- **Callout tool.** Draw a text box with a leader arrow: drag the box, type the
  note, then drag the orange tip to point at the target. Exports as a genuine
  PDF FreeText callout.
- **Revision-cloud tool.** Mark areas with a scalloped cloud (outline only).
  **Drag** to draw freehand, **Shift+drag** for a rectangle, or **click** corners
  and **double-click / Enter** to close (Esc cancels). Exports as a PDF polygon
  with the standard cloud border effect.
- **Tool shortcuts.** `Ctrl+1`…`Ctrl+0` pick tools in toolbar order (Select →
  Cloud).
- **Export flattened PDF (for sharing).** Bakes the marks into the page so they
  render in **every** viewer — including ones that ignore annotations (some
  built-in previews, file thumbnails). The working file stays editable.

Workflow:

- **TODO audit strikethrough.** Checking a TODO off strikes it through both on
  the sheet (a line across the mark) and in the TODO list (a struck-out,
  dimmed row).
- **Save As — fork to a new working file** (`Ctrl+Shift+S`). Copies the current
  markup into a brand-new working file and switches to editing it; the original
  is left untouched.
- **Toolbar reorganised** into logical groups: select · highlight / pen / eraser
  · comment / text box / callout · rectangle / arrow / cloud.

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
