---
tags: [viewer]
---

# Viewer

The Viewer renders every page in one continuous vertical scroll, like the
Chrome PDF viewer. Pages render lazily and sharpen as you zoom in.

## Open a PDF

Use **File ▸ Open PDF…**, pass a file on the command line, or simply **drag a
PDF from your file manager and drop it onto the window** — it opens straight
into the Viewer.

## Navigate

| Action | How |
|--------|-----|
| Scroll | Mouse wheel / trackpad |
| Zoom in / out | `Ctrl` + scroll, or the `+` / `−` buttons, or `Ctrl` `+` / `Ctrl` `-` |
| Fit width | **Fit W** button or **View ▸ Fit width** |
| Fit page | **Fit P** button or **View ▸ Fit page** |
| Pan | Hold **Space** and drag, or drag with the **middle mouse button** |
| Go to page | Type a page number in the toolbar **Page** box |

The current page number updates automatically as you scroll. The left
**Navigation** pane (page thumbnails + bookmarks) and the right **Comments**
pane toggle with **F9** and **F10**.

## Arranging the panels

The **Navigation** and **Comments** panes are dockable, Visual-Studio-style:
**drag a pane's title bar** to snap it to any edge (left, right, top or bottom),
drop it onto another pane to **tab** them together, split panes side-by-side, or
pull one out of the window to **float** it. Your arrangement (and the window
size) is **remembered between sessions**; **View ▸ Reset panel layout** puts
everything back to the default.

## Select & copy text

With the **Select** tool active, **drag across text** to highlight it (just like
a web browser) and press **`Ctrl+C`** to copy it to the clipboard. Line breaks
are preserved. Clicking an existing mark still selects/moves it; dragging on
empty page area selects text.

## Find in the document

Press **`Ctrl+F`** to open a search bar (top-right of the viewer). It searches as
you type and stays open until you close it (the **✕** or **`Esc`**). Step through
matches with **`Enter`** / **`Shift+Enter`** or the ▲ / ▼ buttons; the current
match is highlighted in orange and scrolled into view, with an *i/n* counter.

## Marking up

Pick a tool from the toolbar to start annotating — see [[Markup Tools]]. The
**Comments** dock lists everything you add ([[Comments Sidebar]]).

See also [[Keyboard Shortcuts]].

#viewer
