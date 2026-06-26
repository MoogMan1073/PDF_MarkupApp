"""Hybrid storage: PyMuPDF annotation I/O + SQLite sidecar (Phase 3).

* The **marked PDF** (``<name>.marked.pdf``) is the portable artifact - every
  mark is written as a standard PDF annotation so anyone can view it, and any
  *external* annotations found in an opened PDF (e.g. markups received from a
  colleague) are imported with their real author.
* The **sidecar** (``<name>.markup.db``) is the source of truth for app-only
  state (TODO done/undone, tags, priority, extra text-box styling, the wire
  cache) and stores the full annotation model so nothing is lost on round-trip.

GUI-free.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Iterable, Optional

import fitz  # PyMuPDF

from .annotations import (
    Annotation, now_iso,
    KIND_HIGHLIGHT, KIND_PEN, KIND_COMMENT, KIND_TEXTBOX, KIND_RECT, KIND_ARROW,
)

# Seeded SHX / AutoCAD junk ignore-patterns (regex, may use inline (?i)).
DEFAULT_IGNORE_PATTERNS = [
    r"SHX",
    r"(?i)font.*could not",
    r"(?i)could not be displayed",
    r"(?i)comment from autocad",
    r"(?i)autocad",
    r"(?i)produced by an autodesk",
]

# Map PyMuPDF annotation type-name -> our kind.
_PDF_TYPE_TO_KIND = {
    "Text": KIND_COMMENT,
    "FreeText": KIND_TEXTBOX,
    "Highlight": KIND_HIGHLIGHT,
    "Ink": KIND_PEN,
    "Square": KIND_RECT,
    "Line": KIND_ARROW,
}


# --- date helpers -----------------------------------------------------------


def pdf_date_to_iso(value: Optional[str]) -> str:
    """Convert a PDF date (``D:YYYYMMDDHHmmSS+hh'mm'``) to ISO-8601.

    Falls back to the current time when the value is missing/unparseable.
    """
    if not value:
        return now_iso()
    s = value.strip()
    if s.startswith("D:"):
        s = s[2:]
    s = s.replace("'", "")
    m = re.match(r"(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", s)
    if not m:
        return now_iso()
    y = int(m.group(1))
    mo = int(m.group(2) or 1)
    d = int(m.group(3) or 1)
    hh = int(m.group(4) or 0)
    mm = int(m.group(5) or 0)
    ss = int(m.group(6) or 0)
    try:
        dt = datetime(y, mo, d, hh, mm, ss, tzinfo=timezone.utc)
        return dt.astimezone().isoformat(timespec="seconds")
    except ValueError:
        return now_iso()


# --- ignore (SHX junk) filter ----------------------------------------------


def compile_ignore_patterns(patterns: Iterable[str]) -> list:
    compiled = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            continue
    return compiled


def text_is_ignored(text: str, compiled_patterns: list) -> bool:
    if not text:
        return False
    return any(rx.search(text) for rx in compiled_patterns)


# --- reading PDF annotations ------------------------------------------------


def _color_or_default(colors: dict, key: str, default):
    seq = (colors or {}).get(key) or []
    if len(seq) >= 3:
        return (float(seq[0]), float(seq[1]), float(seq[2]))
    return default


def load_pdf_annotations(
    doc: "fitz.Document",
    ignore_patterns: Optional[Iterable[str]] = None,
) -> list:
    """Read existing PDF annotations into :class:`Annotation` objects.

    Authors come from the annotation ``title`` (PDF ``/T``); creation/mod dates
    are parsed from the PDF date strings.  Marks matching the junk filter are
    flagged ``ignored=True`` (hidden, never deleted).
    """
    compiled = compile_ignore_patterns(
        ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS
    )
    out: list = []
    for pno in range(doc.page_count):
        page = doc[pno]
        # PDF annotation geometry is in unrotated user space; rotate it into the
        # viewer's (visual) space so it lines up on rotated pages. Identity when
        # the page isn't rotated.
        rotm = page.rotation_matrix
        for annot in page.annots() or []:
            try:
                tname = annot.type[1]
            except Exception:
                continue
            kind = _PDF_TYPE_TO_KIND.get(tname)
            if kind is None:
                continue
            info = annot.info or {}
            rect = annot.rect * rotm
            colors = annot.colors or {}
            ann = Annotation(
                page=pno,
                kind=kind,
                rect=(float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)),
                color=_color_or_default(colors, "stroke", (1.0, 0.85, 0.0)),
                author=info.get("title", "") or "",
                created=pdf_date_to_iso(info.get("creationDate")),
                modified=pdf_date_to_iso(info.get("modDate")),
                text=info.get("content", "") or "",
                source="pdf",
                pdf_xref=annot.xref,
            )
            # geometry refinements
            if kind == KIND_PEN:
                try:
                    verts = annot.vertices or []
                    # ink vertices come as a list of strokes
                    pts = []
                    for stroke in verts:
                        if isinstance(stroke, (list, tuple)) and stroke and isinstance(stroke[0], (list, tuple)):
                            pts.extend(tuple(fitz.Point(p[0], p[1]) * rotm) for p in stroke)
                        else:
                            pts.append(tuple(fitz.Point(stroke[0], stroke[1]) * rotm))
                    ann.points = pts
                except Exception:
                    pass
            if kind == KIND_TEXTBOX:
                ann.font_size = float(info.get("fontsize", 11) or 11)
            # carry the /NM name so the sidecar can re-link app state
            name = info.get("name") or ""
            if name:
                ann.id = name
            # junk filter
            if text_is_ignored(ann.text, compiled) or text_is_ignored(ann.author, compiled):
                ann.ignored = True
            out.append(ann)
    return out


# --- writing PDF annotations ------------------------------------------------


def _apply_common(annot, ann: Annotation) -> None:
    info = {"title": ann.author or "", "content": ann.text or ""}
    try:
        annot.set_info(info)
    except Exception:
        pass
    try:
        annot.set_name(ann.id)  # /NM - links back to the sidecar on reload
    except Exception:
        pass


def write_annotations_to_pdf(doc: "fitz.Document", annotations: Iterable[Annotation],
                             include_ignored: bool = False) -> int:
    """Write our marks into ``doc`` as standard PDF annotations.

    The caller is responsible for saving ``doc`` to the ``.marked.pdf`` path.
    Returns the number of annotations written.
    """
    written = 0
    for ann in annotations:
        if ann.ignored and not include_ignored:
            continue
        if ann.page < 0 or ann.page >= doc.page_count:
            continue
        page = doc[ann.page]
        # Our model coordinates are in the *rotated* (visual) page space - the
        # same space the viewer renders and get_text() reports. PDF annotations,
        # however, live in unrotated user space, so transform by the page's
        # derotation matrix (identity when the page isn't rotated). FreeText also
        # needs the page rotation applied so the text reads upright.
        derot = page.derotation_matrix
        prot = page.rotation
        x0, y0, x1, y1 = ann.rect
        rect = fitz.Rect(x0, y0, x1, y1) * derot
        p0 = fitz.Point(x0, y0) * derot
        p1 = fitz.Point(x1, y1) * derot
        annot = None
        try:
            if ann.kind == KIND_HIGHLIGHT:
                annot = page.add_highlight_annot(rect)
                annot.set_colors(stroke=ann.color)
                try:
                    annot.set_opacity(ann.opacity)
                except Exception:
                    pass
            elif ann.kind == KIND_PEN and ann.points:
                stroke = [tuple(fitz.Point(px, py) * derot) for px, py in ann.points]
                annot = page.add_ink_annot([stroke])
                annot.set_colors(stroke=ann.color)
                annot.set_border(width=ann.width)
            elif ann.kind == KIND_COMMENT:
                annot = page.add_text_annot(p0, ann.text or "", icon="Comment")
                # an explicit popup makes the note open as a genuine comment in
                # Adobe / Chrome / other PDF viewers
                try:
                    annot.set_popup(fitz.Rect(x0 + 20, y0, x0 + 220, y0 + 90) * derot)
                except Exception:
                    pass
            elif ann.kind == KIND_TEXTBOX:
                annot = page.add_freetext_annot(
                    rect, ann.text or "", fontsize=ann.font_size,
                    text_color=ann.color, rotate=prot,
                )
            elif ann.kind == KIND_RECT:
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=ann.color)
                annot.set_border(width=ann.width)
            elif ann.kind == KIND_ARROW:
                annot = page.add_line_annot(p0, p1)
                annot.set_colors(stroke=ann.color)
                annot.set_border(width=ann.width)
                try:
                    annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)
                except Exception:
                    pass
        except Exception:
            annot = None
        if annot is not None:
            _apply_common(annot, ann)
            try:
                annot.update()
            except Exception:
                pass
            written += 1
    return written


# --- SQLite sidecar ---------------------------------------------------------


class SidecarDB:
    """``<name>.markup.db`` - app-only state, full annotation cache, wire cache."""

    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        c = self.conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS annotations (
                id TEXT PRIMARY KEY,
                page INTEGER,
                kind TEXT,
                is_todo INTEGER,
                todo_done INTEGER,
                ignored INTEGER,
                "order" INTEGER,
                json TEXT
            );
            CREATE TABLE IF NOT EXISTS wires (
                label TEXT,
                sheet INTEGER,
                rung INTEGER,
                wire_index INTEGER,
                wire_type TEXT,
                page INTEGER,
                source TEXT,
                count INTEGER,
                included INTEGER,
                flags TEXT
            );
            CREATE TABLE IF NOT EXISTS components (
                label TEXT,
                family TEXT,
                number TEXT,
                sheet INTEGER,
                rung INTEGER,
                comp_type TEXT,
                page INTEGER,
                source TEXT,
                count INTEGER,
                included INTEGER,
                flags TEXT
            );
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        c.commit()

    # -- annotations ---------------------------------------------------------

    def save_annotations(self, annotations: Iterable[Annotation]) -> None:
        rows = [
            (
                a.id, a.page, a.kind, int(a.is_todo), int(a.todo_done),
                int(a.ignored), a.order, json.dumps(a.to_dict()),
            )
            for a in annotations
        ]
        self.conn.execute("DELETE FROM annotations")
        self.conn.executemany(
            'INSERT OR REPLACE INTO annotations '
            '(id, page, kind, is_todo, todo_done, ignored, "order", json) '
            "VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()

    def load_annotations(self) -> list:
        cur = self.conn.execute("SELECT json FROM annotations")
        out = []
        for row in cur.fetchall():
            try:
                out.append(Annotation.from_dict(json.loads(row["json"])))
            except Exception:
                continue
        return out

    def app_state_map(self) -> dict:
        """``id -> {app-only fields}`` for re-linking imported PDF annots."""
        cur = self.conn.execute("SELECT id, json FROM annotations")
        out: dict = {}
        for row in cur.fetchall():
            try:
                out[row["id"]] = json.loads(row["json"])
            except Exception:
                continue
        return out

    # -- wire cache ----------------------------------------------------------

    def save_wires(self, wires: Iterable) -> None:
        self.conn.execute("DELETE FROM wires")
        rows = [
            (
                w.label, w.sheet, w.rung, w.wire_index, w.wire_type,
                w.page, w.source, w.count, int(w.included),
                json.dumps(list(w.flags)),
            )
            for w in wires
        ]
        self.conn.executemany(
            "INSERT INTO wires (label, sheet, rung, wire_index, wire_type, "
            "page, source, count, included, flags) VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()

    def load_wires(self) -> list:
        from ..extraction.wire_parser import WireNumber
        cur = self.conn.execute("SELECT * FROM wires")
        out = []
        for r in cur.fetchall():
            try:
                out.append(WireNumber(
                    label=r["label"], sheet=r["sheet"], rung=r["rung"],
                    wire_index=r["wire_index"], wire_type=r["wire_type"],
                    page=r["page"], source=r["source"], count=r["count"],
                    included=bool(r["included"]),
                    flags=json.loads(r["flags"] or "[]"),
                ))
            except Exception:
                continue
        return out

    # -- component cache -----------------------------------------------------

    def save_components(self, components: Iterable) -> None:
        self.conn.execute("DELETE FROM components")
        rows = [
            (
                c.label, c.family, c.number, c.sheet, c.rung, c.comp_type,
                c.page, c.source, c.count, int(c.included),
                json.dumps(list(c.flags)),
            )
            for c in components
        ]
        self.conn.executemany(
            "INSERT INTO components (label, family, number, sheet, rung, "
            "comp_type, page, source, count, included, flags) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()

    def load_components(self) -> list:
        from ..extraction.component_parser import ComponentLabel
        try:
            cur = self.conn.execute("SELECT * FROM components")
        except Exception:
            return []
        out = []
        for r in cur.fetchall():
            try:
                out.append(ComponentLabel(
                    label=r["label"], family=r["family"], number=r["number"],
                    sheet=r["sheet"], rung=r["rung"], comp_type=r["comp_type"],
                    page=r["page"], source=r["source"], count=r["count"],
                    included=bool(r["included"]),
                    flags=json.loads(r["flags"] or "[]"),
                ))
            except Exception:
                continue
        return out

    # -- meta ----------------------------------------------------------------

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value)
        )
        self.conn.commit()

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        cur = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


# --- path helpers -----------------------------------------------------------


def _canonical_stem(pdf_path: str) -> str:
    """The stem shared by a document and its ``.marked.pdf`` / ``.markup.db``.

    Opening either ``foo.pdf`` or ``foo.marked.pdf`` maps to the same stem
    ``foo`` — so there is only ever ONE ``foo.marked.pdf`` (never
    ``foo.marked.marked.pdf``) and ONE ``foo.markup.db`` sidecar.
    """
    base, _ = os.path.splitext(pdf_path)
    if base.lower().endswith(".marked"):
        base = base[: -len(".marked")]
    return base


def is_marked_pdf(pdf_path: str) -> bool:
    """True when the path is a ``*.marked.pdf`` produced by this app."""
    base, _ = os.path.splitext(pdf_path)
    return base.lower().endswith(".marked")


def original_pdf_path(pdf_path: str) -> str:
    return _canonical_stem(pdf_path) + ".pdf"


def marked_pdf_path(pdf_path: str) -> str:
    return _canonical_stem(pdf_path) + ".marked.pdf"


def sidecar_path(pdf_path: str) -> str:
    return _canonical_stem(pdf_path) + ".markup.db"


def strip_annotations(doc: "fitz.Document") -> None:
    """Remove every annotation from ``doc`` (used when a ``.marked.pdf`` is the
    only available base, so re-saving the store doesn't double the marks)."""
    for page in doc:
        for annot in list(page.annots() or []):
            try:
                page.delete_annot(annot)
            except Exception:
                pass
