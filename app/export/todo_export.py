"""TODO list export to Markdown and DOCX (Phase 5).

GUI-free; operates on :class:`app.model.annotations.Annotation` objects flagged
as TODO items.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

GROUP_SHEET = "sheet"
GROUP_COMMENTER = "commenter"
GROUP_NONE = "none"


def _date_only(iso: str) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d")
    except ValueError:
        return iso[:10]


def _group_key(ann, group_by: str):
    if group_by == GROUP_SHEET:
        return f"Sheet {ann.page + 1}"
    if group_by == GROUP_COMMENTER:
        return ann.author or "(unknown)"
    return ""


def _grouped(todos: list, group_by: str) -> list:
    """Return ``[(heading, [anns...]), ...]`` preserving first-seen order."""
    if group_by == GROUP_NONE:
        return [("", list(todos))]
    order: list = []
    buckets: dict = {}
    for a in todos:
        k = _group_key(a, group_by)
        if k not in buckets:
            buckets[k] = []
            order.append(k)
        buckets[k].append(a)
    return [(k, buckets[k]) for k in order]


def export_markdown(todos: Iterable, path: str, group_by: str = GROUP_SHEET,
                    title: str = "TODO List") -> str:
    """GitHub task-list markdown grouped by sheet with ``##`` headers."""
    todos = list(todos)
    lines = [f"# {title}", "",
             f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_", ""]
    for heading, group in _grouped(todos, group_by):
        if heading:
            lines.append(f"## {heading}")
            lines.append("")
        for a in group:
            box = "x" if a.todo_done else " "
            text = " ".join((a.text or a.snippet()).split())
            meta = f"p.{a.page + 1}"
            if a.author:
                meta += f", {a.author}"
            d = _date_only(a.created)
            if d:
                meta += f", {d}"
            tag = f" #{','.join(a.tags)}" if a.tags else ""
            lines.append(f"- [{box}] {text} — {meta}{tag}")
        lines.append("")
    content = "\n".join(lines).rstrip() + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def export_docx(todos: Iterable, path: str, group_by: str = GROUP_SHEET,
                title: str = "TODO List") -> str:
    """DOCX table: Done | Text | Page | Commenter | Date with ☐/☑ glyphs."""
    from docx import Document as Docx
    from docx.shared import Pt

    todos = list(todos)
    doc = Docx()
    doc.add_heading(title, level=0)
    doc.add_paragraph(f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    for heading, group in _grouped(todos, group_by):
        if heading:
            doc.add_heading(heading, level=2)
        table = doc.add_table(rows=1, cols=5)
        try:
            table.style = "Light Grid Accent 1"
        except Exception:
            pass
        hdr = table.rows[0].cells
        for i, name in enumerate(["Done", "Text", "Page", "Commenter", "Date"]):
            hdr[i].text = name
            for p in hdr[i].paragraphs:
                for r in p.runs:
                    r.font.bold = True
                    r.font.size = Pt(10)
        for a in group:
            cells = table.add_row().cells
            cells[0].text = "☑" if a.todo_done else "☐"  # ☑ / ☐
            cells[1].text = " ".join((a.text or a.snippet()).split())
            cells[2].text = str(a.page + 1)
            cells[3].text = a.author or ""
            cells[4].text = _date_only(a.created)
    doc.save(path)
    return path
