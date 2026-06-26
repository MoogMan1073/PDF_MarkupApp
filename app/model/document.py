"""High-level document controller (GUI-free).

Owns the open :class:`fitz.Document`, the :class:`AnnotationStore`, and the
:class:`SidecarDB`, and implements the hybrid open/save workflow described in
the spec.  The viewer/panels talk to this object.
"""

from __future__ import annotations

import os
from typing import Iterable, Optional

import fitz  # PyMuPDF

from .annotations import Annotation, AnnotationStore
from .storage import (
    SidecarDB, load_pdf_annotations, write_annotations_to_pdf,
    compile_ignore_patterns, text_is_ignored,
    marked_pdf_path, sidecar_path, original_pdf_path, is_marked_pdf,
    strip_annotations, DEFAULT_IGNORE_PATTERNS,
)


class Document:
    """A single open PDF plus its markup state."""

    def __init__(self, path: str, ignore_patterns: Optional[Iterable[str]] = None):
        self.path = path
        self.fitz_doc = fitz.open(path)
        self.store = AnnotationStore()
        sc_path = sidecar_path(path)
        # Opening a *.marked.pdf reuses the ORIGINAL's single sidecar. If that
        # sidecar is missing (e.g. the file was moved on its own), we create a
        # fresh one and flag it so the UI can tell the user.
        self.sidecar_recreated = is_marked_pdf(path) and not os.path.exists(sc_path)
        self.sidecar = SidecarDB(sc_path)
        self.ignore_patterns = list(
            ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS
        )
        self.wires: list = []
        self.components: list = []
        self.sheet_labels: dict = {}   # page_index -> sheet number (str, e.g. "000")
        self._dirty = False

    # -- basic page access ---------------------------------------------------

    @property
    def page_count(self) -> int:
        return self.fitz_doc.page_count

    def page_rect(self, page_no: int) -> "fitz.Rect":
        return self.fitz_doc[page_no].rect

    def get_pixmap(self, page_no: int, zoom: float = 1.0) -> "fitz.Pixmap":
        """Render a page to a :class:`fitz.Pixmap` (GUI converts to QImage).

        ``annots=False`` so the bitmap is the clean page: the app draws every
        mark as its own overlay item, so a PDF that already carries annotations
        (a ``.marked.pdf`` or a colleague's markup) isn't rendered twice.
        """
        mat = fitz.Matrix(zoom, zoom)
        return self.fitz_doc[page_no].get_pixmap(matrix=mat, alpha=False, annots=False)

    # -- loading -------------------------------------------------------------

    def load(self) -> None:
        """Load sidecar (our) annotations, then import external PDF annots.

        The sidecar is authoritative for marks this app created.  Any annotation
        found in the PDF whose ``/NM`` id is *not* already known is treated as
        external (e.g. a colleague's markup or AutoCAD junk) and imported with
        its real author; junk is flagged ignored.
        """
        # 1) our marks from the sidecar
        known_ids = set()
        for ann in self.sidecar.load_annotations():
            self.store.add(ann, silent=True)
            known_ids.add(ann.id)

        # 2) external marks living in the PDF itself
        compiled = compile_ignore_patterns(self.ignore_patterns)
        for ann in load_pdf_annotations(self.fitz_doc, self.ignore_patterns):
            if ann.id in known_ids:
                continue  # sidecar copy already loaded
            # re-evaluate junk filter against the current pattern list
            if text_is_ignored(ann.text, compiled) or text_is_ignored(ann.author, compiled):
                ann.ignored = True
            self.store.add(ann, silent=True)

        # 3) cached wire numbers + component labels
        self.wires = self.sidecar.load_wires()
        self.components = self.sidecar.load_components()

        # 4) per-page sheet numbers: load saved edits, then best-effort
        #    title-block auto-detect for searchable pages we don't know yet
        self._load_sheet_labels()

    # -- sheet numbers (per page) -------------------------------------------

    def _load_sheet_labels(self) -> None:
        import json
        raw = self.sidecar.get_meta("sheet_labels")
        saved = {}
        if raw:
            try:
                saved = {int(k): str(v) for k, v in json.loads(raw).items()}
            except Exception:
                saved = {}
        self.sheet_labels = saved
        self._autodetect_sheet_labels()

    def _autodetect_sheet_labels(self) -> None:
        """Fill sheet numbers from the title block of searchable pages, without
        clobbering any the user has already saved/edited."""
        from ..extraction.text_extract import page_has_text, read_titleblock_sheet_label
        for i in range(self.page_count):
            if i in self.sheet_labels:
                continue
            try:
                page = self.fitz_doc[i]
                if not page_has_text(page):
                    continue   # scanned page: leave blank for manual entry
                label = read_titleblock_sheet_label(page)
            except Exception:
                label = None
            if label:
                self.sheet_labels[i] = label

    def sheet_label(self, page_no: int) -> str:
        return self.sheet_labels.get(int(page_no), "")

    def set_sheet_label(self, page_no: int, label: str) -> None:
        """Set (or clear, when blank) a page's sheet number and persist it."""
        page_no = int(page_no)
        label = (label or "").strip()
        if label:
            self.sheet_labels[page_no] = label
        else:
            self.sheet_labels.pop(page_no, None)
        self._save_sheet_labels()

    def _save_sheet_labels(self) -> None:
        import json
        self.sidecar.set_meta(
            "sheet_labels",
            json.dumps({str(k): v for k, v in self.sheet_labels.items()}))

    # -- saving --------------------------------------------------------------

    def save(self, marked_path: Optional[str] = None,
             include_ignored: bool = False) -> str:
        """Write the ``.marked.pdf`` copy and sync the sidecar.

        The original PDF is never overwritten.  Returns the marked PDF path.
        """
        out = marked_path or marked_pdf_path(self.path)
        # Base the write on the PRISTINE original when it's available, so re-saving
        # never doubles the marks; if only the .marked.pdf exists, strip its
        # annotations first. Either way the store is the single source of truth.
        original = original_pdf_path(self.path)
        if os.path.exists(original):
            work = fitz.open(original)
        else:
            work = fitz.open(self.path)
            if is_marked_pdf(self.path):
                strip_annotations(work)
        write_annotations_to_pdf(work, self.store.all(), include_ignored=include_ignored)

        # ``out`` is the same file this Document already holds open (e.g. the user
        # opened the .marked.pdf itself) → write a temp, RELEASE our handle (on
        # Windows an open file can't be replaced), atomically swap it in, then
        # reopen on the freshly-written file.
        out_is_open = os.path.abspath(out) == os.path.abspath(self.path)
        if out_is_open:
            import tempfile
            d = os.path.dirname(os.path.abspath(out)) or "."
            fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=d)
            os.close(fd)
            work.save(tmp, garbage=3, deflate=True)
            work.close()
            try:
                self.fitz_doc.close()
            except Exception:
                pass
            os.replace(tmp, out)
            self.fitz_doc = fitz.open(out)
            self.path = out
        else:
            work.save(out, garbage=3, deflate=True)
            work.close()

        # sync app state + wire cache
        self.sidecar.save_annotations(self.store.all())
        if self.wires:
            self.sidecar.save_wires(self.wires)
        if self.components:
            self.sidecar.save_components(self.components)
        self._save_sheet_labels()
        self.sidecar.set_meta("source_pdf", os.path.basename(self.path))
        self._dirty = False
        return out

    def export_annotated_pdf(self, out_path: str, include_ignored: bool = False) -> str:
        """Explicit 'Export annotated PDF…' to an arbitrary path."""
        return self.save(marked_path=out_path, include_ignored=include_ignored)

    # -- wire cache ----------------------------------------------------------

    def set_wires(self, wires: list) -> None:
        self.wires = wires
        self.sidecar.save_wires(wires)

    def set_components(self, components: list) -> None:
        self.components = components
        self.sidecar.save_components(components)

    # -- lifecycle -----------------------------------------------------------

    def mark_dirty(self) -> None:
        self._dirty = True

    @property
    def dirty(self) -> bool:
        return self._dirty

    def close(self) -> None:
        try:
            self.sidecar.close()
        finally:
            try:
                self.fitz_doc.close()
            except Exception:
                pass
