# Changelog

All notable changes to **DSI Redline** are documented here. Versions are tagged
`vX.Y.Z`; each tag triggers the Windows build that publishes the installer and a
portable zip to the matching GitHub release.

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
