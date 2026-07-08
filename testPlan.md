---
title: DSI Redline v1.1.0 — UI Test Plan
tags: [qa, checklist, v1.1.0]
version: "1.1.0"
---

# DSI Redline v1.1.0 — UI Test Plan

Hands-on checks for the **v1.1.0 feature sprint** (notes on any mark, fills,
callouts, revision clouds, TODO-audit strikethrough, Save As), plus a
**regression** pass on the areas those changes touched. Tick each box; note
`❌ <detail>` on any failure.

> [!note] Prepare
> - [ ] A **vector** AutoCAD-Electrical PDF (real text layer, a title block).
> - [ ] A **scanned / image-only** PDF.
> - [ ] Somewhere to open the exported `*.marked.pdf` **outside** DSI Redline
>       (Adobe Reader, Chrome or Edge) to confirm portability.

---

## A. New markup

### A1 — Notes on any mark
- [ ] Draw a **highlight**, a **pen** stroke, a **rectangle** and an **arrow**.
- [ ] Right-click each → **Add note…**; type a note; save. The menu now reads **Edit note…**.
- [ ] Each noted mark shows a small **orange corner badge**.
- [ ] Open the **Comments** sidebar → the noted rectangle and arrow now appear (they don't before they're noted).
- [ ] The **type filter** offers **Rectangle**, **Arrow** and **Callout**; picking one narrows the list.
- [ ] Right-click a noted mark ▸ **Reveal in Comments** selects its row.
- [ ] **Save markup**, then open the `*.marked.pdf` in Adobe/Chrome → each note shows as a **sticky-note comment** (a comment icon you can click), and reopening the file here shows **no duplicate** comments.

### A2 — Opaque text box & rectangle (Fill + opacity)
- [ ] Select the **Rectangle** tool → the toolbar **Fill** button is **enabled**; select **Pen** → it's **disabled**.
- [ ] Click **Fill** → the dialog shows a **colour picker + an opacity slider** (not a raw alpha channel); "No fill" is an explicit checkbox.
- [ ] Pick a colour, set opacity to **100%**, draw a rectangle → it's a **solid cover** (hides what's beneath).
- [ ] Set Fill opacity to ~**40%** and draw another → a **translucent** shaded box.
- [ ] Right-click an existing rectangle ▸ **Fill…** → change its fill; the change sticks and is undoable.
- [ ] With the **Text box** tool, set a **white 100% Fill**, draw a box over text, type a label → the text sits on an **opaque white cover**.
- [ ] Double-click a text box ▸ its editor has a **Fill** button that changes the background.
- [ ] **Save** and reopen in DSI Redline → fills and opacities persist.

### A3 — Callout tool
- [ ] Pick **Callout**, drag a box, type the note.
- [ ] An **orange tip** grip appears; **drag it** so the leader arrow points at a target on the drawing.
- [ ] The box still **moves, resizes and edits** (double-click) like a text box; give it a **Fill** if you like.
- [ ] **Save** → open the `*.marked.pdf` in Adobe/Chrome → it shows as a **text callout with a leader arrow**.

### A4 — Revision-cloud tool
- [ ] Pick **Cloud**. **Drag** across an area → a **freehand** scalloped cloud (outline only).
- [ ] **Shift+drag** → a **rectangular** scalloped cloud.
- [ ] Pick **Cloud** again. **Click** several corners, then **double-click** (or press **Enter**) → the polygon **closes** into a cloud.
- [ ] While mid-polygon, press **Esc** → it cancels (no mark left behind).
- [ ] A cloud needs at least **3 points** — a couple of stray clicks don't make one.
- [ ] Select / move / **erase** / **undo** a cloud like any other mark.
- [ ] **Save** → the `*.marked.pdf` shows a **polygon with a cloudy border** in Adobe/Chrome.

---

## B. Workflow

### B1 — TODO audit strikethrough
- [ ] Flag a mark as **TODO** (comment/text box editor, or the TODO tab).
- [ ] In the **TODO** tab, tick its **Done** box → the row is **struck through** and dimmed; the count shows "… done".
- [ ] On the **sheet**, the same mark now has a **strikethrough line** across it.
- [ ] Untick **Done** → both strikethroughs clear.

### B2 — Save As (fork to a new working file)
- [ ] Open a drawing, add a few marks, **Save**.
- [ ] **File ▸ Save As…** (`Ctrl+Shift+S`); choose a new name (e.g. `drawing-rev.pdf`).
- [ ] The title bar switches to the **new** file; a notice confirms the original is unchanged.
- [ ] On disk you now have `drawing-rev.pdf`, `drawing-rev.marked.pdf` and `drawing-rev.markup.db`, each carrying your marks.
- [ ] Add another mark and **Save** → it goes to the **fork**; reopening the **original** shows it is **untouched** (does not have the new mark).

### B3 — Toolbar reorganised
- [ ] The toolbar reads in groups, separated by dividers: **Select** · Highlight / Pen / Eraser · Comment / Text box / Callout · Rectangle / Arrow / Cloud.
- [ ] Every tool still selects and draws.

### B4 — Tool hotkeys
- [ ] `Ctrl+1`…`Ctrl+9` then `Ctrl+0` select the tools in toolbar order (Select → Cloud); the pressed tool's button highlights.
- [ ] Hovering a tool button shows its shortcut in the tooltip.

---

## C. Regression checks (areas these changes touched)

> [!note] v1.1.0 touched the annotation model, the viewer's draw/mouse handling,
> the comment & TODO panels, PDF export, and save/open — re-verify the neighbours.

### Viewer / marks
- [ ] Create **every** mark type (highlight, pen, comment, text box, rectangle, arrow, **callout**, **cloud**) — all draw and preview live.
- [ ] Move / resize / **rotate** a rectangle, highlight, text box, arrow; **resizing a rotated mark** keeps the opposite corner anchored.
- [ ] **Undo / redo** across create / move / resize / **fill change** / **note edit** / **callout-tip move** / delete.
- [ ] **Eraser** removes each kind, including callouts and clouds.
- [ ] **In-memory rotate (↺/↻)** rotates the view with all marks and snaps back exactly.
- [ ] Text selection + `Ctrl+C` on empty page area still works; **Find** still searches live with correct `i/n`.

### Panels & navigation
- [ ] **Comments sidebar**: click-to-flash, all filters (incl. new ones), sort, delete still work.
- [ ] **TODO**: grouping (Page / Sheet / Commenter / None), header sort, edit Text/Sheet/Tag, Pg double-click jump, "Go to in PDF" still work; **Hide done** still filters.
- [ ] **Reveal in TODO / Comments** from a right-clicked mark still works.
- [ ] **Navigation** thumbnails / bookmarks jump and switch to the Viewer.
- [ ] **Wire / Component** extract (AI/OCR), sort/filter, and export still work.

### Storage round-trips & portability
- [ ] Open original → add each new mark type (noted marks, filled shapes, callout, cloud, TODO) → **Save** → close → **reopen** → everything persists, including notes, fills, tips, cloud vertices, TODO/done state, tags, sheet numbers.
- [ ] Open a **colleague-annotated** PDF → external annotations still import with authors; Save → not duplicated.
- [ ] Open the exported `*.marked.pdf` in **Adobe/Chrome** → highlights, notes-as-popups, filled shapes, freetext callouts and revision clouds all render.
- [ ] **PDF Tools** (split / delete / rotate / combine / insert / swap / convert / crop) still operate and write new files.

---

## Sign-off

| Field | Value |
|-------|-------|
| Tester | |
| Date | |
| Build | `v1.1.0` (installer / portable) |
| OS | Windows ___ |

- [ ] **All v1.1.0 checks pass** and no regressions.
- [ ] Issues logged:

```
1.
2.
```

#qa #checklist #v1.1.0
