"""Tests for the merged PDF tools backend (app/tools/pdf_ops.py)."""

import os
import tempfile
import unittest

import fitz

from app.tools import pdf_ops as ops
from app.tools.pdf_ops import (
    SheetRegion, parse_page_ranges, sheet_from_text,
    SHEET_EXACT, SHEET_FIRST_NUMBER, SHEET_SMALLER_OF_TWO,
)


def _make_set(path, pages=5, sheet_base=300):
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page(width=612, height=792)
        p.insert_text((50, 50), f"BODY {i + 1}")
        p.insert_text((420, 745), f"SHEET {sheet_base + i} OF 420", fontsize=10)
    doc.save(path)
    doc.close()


class TestParsers(unittest.TestCase):
    def test_parse_page_ranges(self):
        self.assertEqual(parse_page_ranges("1,3,5-7"), [0, 2, 4, 5, 6])
        self.assertEqual(parse_page_ranges("3-1"), [0, 1, 2])           # reversed
        self.assertEqual(parse_page_ranges("1,2,9", max_page=5), [0, 1])  # clamp

    def test_sheet_from_text(self):
        self.assertEqual(sheet_from_text("SHEET 300 OF 420", SHEET_EXACT), "SHEET 300 OF 420")
        self.assertEqual(sheet_from_text("SHEET 300 OF 420", SHEET_FIRST_NUMBER), "300")
        self.assertEqual(sheet_from_text("SHEET 300 OF 420", SHEET_SMALLER_OF_TWO), "300")
        self.assertEqual(sheet_from_text("E-301", SHEET_FIRST_NUMBER), "301")
        self.assertEqual(sheet_from_text("", SHEET_FIRST_NUMBER), "")


class TestPdfOps(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "set.pdf")
        _make_set(self.src, pages=5)

    def test_split_by_page(self):
        files = ops.split_pdf(self.src, os.path.join(self.tmp, "p"), naming="page")
        self.assertEqual(len(files), 5)
        self.assertTrue(files[0].endswith("set-page01.pdf"))
        self.assertEqual(fitz.open(files[0]).page_count, 1)

    def test_split_by_sheet_region(self):
        reg = SheetRegion(0, 4, (410, 735, 600, 760))
        files = ops.split_pdf(self.src, os.path.join(self.tmp, "s"), naming="sheet",
                              regions=[reg], mode=SHEET_FIRST_NUMBER)
        names = sorted(os.path.basename(f) for f in files)
        self.assertIn("set-sheet300.pdf", names)
        self.assertIn("set-sheet304.pdf", names)

    def test_extract_sheet_numbers(self):
        reg = SheetRegion(0, 4, (410, 735, 600, 760))
        doc = fitz.open(self.src)
        res = ops.extract_sheet_numbers(doc, [reg], mode=SHEET_FIRST_NUMBER)
        doc.close()
        self.assertEqual(res, {0: "300", 1: "301", 2: "302", 3: "303", 4: "304"})

    def test_combine(self):
        ops.split_pdf(self.src, os.path.join(self.tmp, "p"), naming="page")
        out = ops.combine_pdfs(os.path.join(self.tmp, "p"),
                               os.path.join(self.tmp, "c.pdf"))
        self.assertEqual(fitz.open(out).page_count, 5)

    def test_insert(self):
        ins = os.path.join(self.tmp, "ins.pdf")
        d = fitz.open(); d.new_page(); d.new_page(); d.save(ins); d.close()
        out = ops.insert_pdf(self.src, ins, os.path.join(self.tmp, "i.pdf"), 2)
        self.assertEqual(fitz.open(out).page_count, 7)

    def test_swap(self):
        one = os.path.join(self.tmp, "one.pdf")
        d = fitz.open(); d.new_page(); d.save(one); d.close()
        out = ops.swap_page(self.src, one, os.path.join(self.tmp, "sw.pdf"), 2)
        self.assertEqual(fitz.open(out).page_count, 5)

    def test_swap_rejects_multipage(self):
        multi = os.path.join(self.tmp, "m.pdf")
        d = fitz.open(); d.new_page(); d.new_page(); d.save(multi); d.close()
        with self.assertRaises(ValueError):
            ops.swap_page(self.src, multi, os.path.join(self.tmp, "x.pdf"), 0)

    def test_delete(self):
        out = ops.delete_pages(self.src, os.path.join(self.tmp, "d.pdf"), "2,4")
        self.assertEqual(fitz.open(out).page_count, 3)

    def test_rotate_adds_to_existing(self):
        out = ops.rotate_pdf(self.src, os.path.join(self.tmp, "r.pdf"), 90)
        self.assertEqual(fitz.open(out)[0].rotation, 90)
        out2 = ops.rotate_pdf(out, os.path.join(self.tmp, "r2.pdf"), 90)
        self.assertEqual(fitz.open(out2)[0].rotation, 180)

    def test_crop_to_png(self):
        pngs = ops.crop_regions_to_png(self.src, os.path.join(self.tmp, "cr"),
                                       {0: [(410, 735, 600, 760)]})
        self.assertTrue(pngs and os.path.exists(pngs[0]))

    def test_rotated_page_region_extraction(self):
        # box drawn in the viewer's visual coords must read correctly on a
        # rotated page (get_text clip uses visual coords)
        rot = os.path.join(self.tmp, "rot.pdf")
        d = fitz.open(); p = d.new_page(width=612, height=792)
        p.insert_text((420, 745), "300", fontsize=10)
        p.set_rotation(270)
        d.save(rot); d.close()
        d = fitz.open(rot)
        # find the token's visual bbox, then read it back via a region
        bbox = None
        for w in d[0].get_text("words"):
            if w[4] == "300":
                bbox = (w[0], w[1], w[2], w[3])
        self.assertIsNotNone(bbox)
        reg = SheetRegion(0, 0, (bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2))
        res = ops.extract_sheet_numbers(d, [reg], mode=SHEET_EXACT)
        d.close()
        self.assertEqual(res[0], "300")


if __name__ == "__main__":
    unittest.main()
