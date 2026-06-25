"""Per-page sheet numbers: title-block auto-detect (string-preserving),
document round-trip, and TODO grouping/export by page vs sheet."""

import os
import tempfile
import unittest

import fitz

from app.extraction.text_extract import read_titleblock_sheet_label
from app.model.document import Document
from app.model.annotations import Annotation
from app.export.todo_export import _grouped, GROUP_PAGE, GROUP_SHEET, GROUP_NONE


def _make_pdf(path, sheet_texts):
    """One landscape page per entry; entry is the title-block text (or None)."""
    doc = fitz.open()
    for txt in sheet_texts:
        page = doc.new_page(width=792, height=612)   # landscape
        if txt:
            page.insert_text((72, 72), txt)
    doc.save(path)
    doc.close()


class TestTitleblockLabel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_preserves_leading_zeros(self):
        p = os.path.join(self.tmp, "a.pdf")
        _make_pdf(p, ["SHEET 000", "SHEET 261"])
        doc = fitz.open(p)
        self.assertEqual(read_titleblock_sheet_label(doc[0]), "000")
        self.assertEqual(read_titleblock_sheet_label(doc[1]), "261")
        doc.close()

    def test_none_when_absent(self):
        p = os.path.join(self.tmp, "b.pdf")
        _make_pdf(p, ["no sheet here"])
        doc = fitz.open(p)
        self.assertIsNone(read_titleblock_sheet_label(doc[0]))
        doc.close()


class TestDocumentSheetLabels(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "draw.pdf")
        _make_pdf(self.src, ["SHEET 000", "SHEET 300", "no titleblock"])

    def test_autodetect_on_load(self):
        doc = Document(self.src)
        doc.load()
        self.assertEqual(doc.sheet_label(0), "000")
        self.assertEqual(doc.sheet_label(1), "300")
        self.assertEqual(doc.sheet_label(2), "")   # not detected -> blank
        doc.close()

    def test_edit_persists_and_overrides_autodetect(self):
        doc = Document(self.src)
        doc.load()
        doc.set_sheet_label(2, "601")      # manual entry on the blank page
        doc.set_sheet_label(1, "300A")     # correct an auto-detected one
        doc.close()

        doc2 = Document(self.src)
        doc2.load()
        self.assertEqual(doc2.sheet_label(2), "601")
        self.assertEqual(doc2.sheet_label(1), "300A")  # saved edit wins over detect
        self.assertEqual(doc2.sheet_label(0), "000")
        doc2.close()

    def test_clear_label(self):
        doc = Document(self.src)
        doc.load()
        doc.set_sheet_label(0, "")
        self.assertEqual(doc.sheet_label(0), "")
        doc.close()


class TestTodoGrouping(unittest.TestCase):
    def test_group_by_page_vs_sheet(self):
        a0 = Annotation(page=0, kind="comment", is_todo=True, text="a")
        a1 = Annotation(page=1, kind="comment", is_todo=True, text="b")
        a2 = Annotation(page=2, kind="comment", is_todo=True, text="c")
        sheets = {0: "000", 1: "300"}   # page 2 has no sheet
        by_page = [h for h, _ in _grouped([a0, a1, a2], GROUP_PAGE, sheets)]
        self.assertEqual(by_page, ["Page 1", "Page 2", "Page 3"])
        by_sheet = [h for h, _ in _grouped([a0, a1, a2], GROUP_SHEET, sheets)]
        self.assertEqual(by_sheet, ["Sheet 000", "Sheet 300", "(no sheet)"])

    def test_no_grouping(self):
        a0 = Annotation(page=0, kind="comment", is_todo=True, text="a")
        out = _grouped([a0], GROUP_NONE, {})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "")


if __name__ == "__main__":
    unittest.main()
