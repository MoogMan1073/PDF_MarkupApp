"""In-app user-manual reader — a read-only, Obsidian-style vault.

Renders the markdown files in ``docs/`` (kept next to the app so they ship with
it) with working ``[[wikilinks]]``, clickable ``#tags`` and a simple graph view.
Falls back gracefully if the vault folder is missing.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from urllib.parse import quote, unquote

from PySide6.QtCore import Qt, QUrl, QPointF, QRectF
from PySide6.QtGui import QColor, QPen, QBrush, QDesktopServices, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QTextBrowser, QListWidget, QTabWidget,
    QToolBar, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsSimpleTextItem, QLabel, QVBoxLayout,
)

_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9_][\w/-]*)")
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_FM_TAGS_RE = re.compile(r"tags:\s*\[([^\]]*)\]")


def vault_dir() -> Path:
    """Locate the docs vault (ships alongside the app)."""
    here = Path(__file__).resolve().parent.parent / "docs"
    if here.is_dir():
        return here
    return Path.cwd() / "docs"


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1)


def _frontmatter_tags(text: str) -> set:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return set()
    mt = _FM_TAGS_RE.search(m.group(0))
    if not mt:
        return set()
    return {t.strip() for t in mt.group(1).split(",") if t.strip()}


def _strip_code(text: str) -> str:
    """Blank out fenced and inline code so examples like `[[link]]`/`#tag`
    aren't mistaken for real links/tags."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def _link_sub(m) -> str:
    page = m.group(1).strip()
    alias = (m.group(2) or page).strip()
    return f"[{alias}](vault:{quote(page)})"


def _tag_sub(m) -> str:
    return f"[#{m.group(1)}](tag:{quote(m.group(1))})"


def load_vault(folder: Path) -> dict:
    """Return ``{page_name: {raw, tags:set, links:set}}``."""
    pages: dict = {}
    if not folder.is_dir():
        return pages
    for path in sorted(folder.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            continue
        clean = _strip_code(_strip_frontmatter(raw))
        pages[path.stem] = {
            "raw": raw,
            "tags": _frontmatter_tags(raw) | set(_TAG_RE.findall(clean)),
            "links": {m.group(1).strip() for m in _LINK_RE.finditer(clean)},
        }
    return pages


def to_markdown(raw: str) -> str:
    """Convert vault markdown to QTextBrowser markdown with working links.

    Headings and code (fenced or inline) are left untouched so literal
    ``[[link]]`` / ``#tag`` examples render verbatim.
    """
    text = _strip_frontmatter(raw)
    out_lines = []
    in_code = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_code = not in_code
            out_lines.append(line)
            continue
        # a real ATX heading is "# text" (hashes + space); "#home" is a tag line
        if in_code or re.match(r"#{1,6}\s", stripped):
            out_lines.append(line)
            continue
        # convert only outside inline-code segments (odd indices are code)
        parts = line.split("`")
        for i in range(0, len(parts), 2):
            parts[i] = _TAG_RE.sub(_tag_sub, _LINK_RE.sub(_link_sub, parts[i]))
        out_lines.append("`".join(parts))
    return "\n".join(out_lines)


class _NodeItem(QGraphicsEllipseItem):
    """Clickable page node in the graph view."""

    R = 9.0

    def __init__(self, name, on_click):
        super().__init__(-self.R, -self.R, 2 * self.R, 2 * self.R)
        self.name = name
        self._on_click = on_click
        self.setBrush(QBrush(QColor(40, 120, 220)))
        self.setPen(QPen(QColor("white"), 1))
        self.setZValue(2)
        self.setCursor(Qt.PointingHandCursor)
        label = QGraphicsSimpleTextItem(name, self)
        label.setBrush(QBrush(QColor(40, 40, 40)))
        br = label.boundingRect()
        label.setPos(-br.width() / 2, self.R + 2)

    def mousePressEvent(self, event):
        self._on_click(self.name)
        event.accept()


class HelpWindow(QMainWindow):
    """Read-only vault reader: Pages / Tags / Graph + a markdown view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DSI Redline — User Manual")
        self.resize(1040, 720)
        self.pages = load_vault(vault_dir())
        self._history = []
        self._hindex = -1

        tb = QToolBar("nav")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.act_back = QAction("← Back", self); self.act_back.triggered.connect(self.go_back)
        self.act_fwd = QAction("Forward →", self); self.act_fwd.triggered.connect(self.go_forward)
        self.act_home = QAction("Home", self); self.act_home.triggered.connect(lambda: self.load_page("Home"))
        tb.addAction(self.act_back); tb.addAction(self.act_fwd); tb.addSeparator(); tb.addAction(self.act_home)

        split = QSplitter(self)
        self.setCentralWidget(split)

        self.nav = QTabWidget()
        self.nav.setMaximumWidth(300)
        self.page_list = QListWidget(); self.page_list.addItems(sorted(self.pages))
        self.page_list.itemClicked.connect(lambda it: self.load_page(it.text()))
        self.tag_list = QListWidget()
        all_tags = sorted({t for p in self.pages.values() for t in p["tags"]})
        self.tag_list.addItems([f"#{t}" for t in all_tags])
        self.tag_list.itemClicked.connect(lambda it: self.show_tag(it.text().lstrip("#")))
        self.graph = _GraphView(self.pages, self.load_page)
        self.nav.addTab(self.page_list, "Pages")
        self.nav.addTab(self.tag_list, "Tags")
        self.nav.addTab(self.graph, "Graph")
        split.addWidget(self.nav)

        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setOpenExternalLinks(False)
        self.view.anchorClicked.connect(self._on_anchor)
        split.addWidget(self.view)
        split.setStretchFactor(1, 1)

        if self.pages:
            self.load_page("Home" if "Home" in self.pages else sorted(self.pages)[0])
        else:
            self.view.setMarkdown("# User manual not found\n\nThe `docs/` folder "
                                  "was not found next to the application.")

    # -- rendering -----------------------------------------------------------

    def _render(self, entry):
        kind, value = entry
        if kind == "page":
            data = self.pages.get(value)
            self.view.setMarkdown(to_markdown(data["raw"]) if data else f"# {value}\n\n*Missing page.*")
            self.setWindowTitle(f"DSI Redline — User Manual — {value}")
        else:  # tag
            names = sorted(n for n, p in self.pages.items() if value in p["tags"])
            body = "\n".join(f"- [[{n}]]" for n in names) or "*No pages.*"
            self.view.setMarkdown(to_markdown(f"# Tag: #{value}\n\nPages tagged `#{value}`:\n\n{body}"))
            self.setWindowTitle(f"DSI Redline — User Manual — #{value}")
        self._update_nav_actions()

    def _push(self, entry):
        # truncate any forward history, then append
        self._history = self._history[: self._hindex + 1]
        self._history.append(entry)
        self._hindex = len(self._history) - 1
        self._render(entry)

    def load_page(self, name, record=True):
        if record:
            self._push(("page", name))
        else:
            self._render(("page", name))

    def show_tag(self, tag):
        self._push(("tag", tag))

    def go_back(self):
        if self._hindex > 0:
            self._hindex -= 1
            self._render(self._history[self._hindex])

    def go_forward(self):
        if self._hindex < len(self._history) - 1:
            self._hindex += 1
            self._render(self._history[self._hindex])

    def _update_nav_actions(self):
        self.act_back.setEnabled(self._hindex > 0)
        self.act_fwd.setEnabled(self._hindex < len(self._history) - 1)

    # -- links ---------------------------------------------------------------

    def _on_anchor(self, url: QUrl):
        s = url.toString()
        if s.startswith("vault:"):
            self.load_page(unquote(s[len("vault:"):]))
        elif s.startswith("tag:"):
            self.show_tag(unquote(s[len("tag:"):]))
        else:
            QDesktopServices.openUrl(url)


class _GraphView(QGraphicsView):
    """Simple circular-layout graph of pages and their [[links]]."""

    def __init__(self, pages: dict, on_click):
        super().__init__()
        from PySide6.QtGui import QPainter
        self.setRenderHint(QPainter.Antialiasing)
        scene = QGraphicsScene(self)
        self.setScene(scene)
        names = sorted(pages)
        n = max(1, len(names))
        radius = 30 + 22 * n
        pos = {}
        for i, name in enumerate(names):
            ang = 2 * math.pi * i / n
            pos[name] = QPointF(radius * math.cos(ang), radius * math.sin(ang))

        edge_pen = QPen(QColor(180, 180, 180), 0)
        seen = set()
        for name in names:
            for tgt in pages[name]["links"]:
                if tgt in pos and (tgt, name) not in seen:
                    seen.add((name, tgt))
                    scene.addLine(pos[name].x(), pos[name].y(),
                                  pos[tgt].x(), pos[tgt].y(), edge_pen)
        for name in names:
            node = _NodeItem(name, on_click)
            node.setPos(pos[name])
            scene.addItem(node)
        margin = 80
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
