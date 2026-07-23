"""Print… (Ctrl+P): render the drawing + its marks and send it to the system
print service. Exercised here against a PDF-output printer so no hardware is
needed."""

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz

from app.model.annotations import Annotation, KIND_RECT

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtGui import QImage
    _QT_OK = True
except Exception:  # pragma: no cover
    _QT_OK = False


def _make_pdf(dirpath, pages=2, name="d.pdf"):
    src = os.path.join(dirpath, name)
    d = fitz.open()
    for _ in range(pages):
        p = d.new_page(width=400, height=300)
        p.insert_text((72, 72), "sheet")
    d.save(src); d.close()
    return src


class TestAnnotatedFitz(unittest.TestCase):
    def test_returns_doc_with_marks(self):
        from app.model.document import Document
        tmp = tempfile.mkdtemp()
        src = _make_pdf(tmp, pages=1)
        doc = Document(src); doc.load()
        doc.store.add(Annotation(page=0, kind=KIND_RECT,
                                 rect=(10, 10, 100, 80), color=(1, 0, 0)),
                      silent=True)
        work = doc.annotated_fitz()
        try:
            self.assertEqual(work.page_count, 1)
            self.assertTrue(len(list(work[0].annots() or [])) >= 1)
        finally:
            work.close()
            doc.close()


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestPrint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _win_with(self, pages=2):
        from app.main_window import MainWindow
        tmp = tempfile.mkdtemp()
        src = _make_pdf(tmp, pages=pages)
        win = MainWindow(); win.load_document(src)
        return win, tmp

    def test_render_print_image_is_capped(self):
        win, _ = self._win_with(pages=1)
        printer = QPrinter(QPrinter.HighResolution)   # 1200 dpi
        work = win.document.annotated_fitz()
        try:
            img = win._render_print_image(work[0], printer)
        finally:
            work.close()
        self.assertFalse(img.isNull())
        # 400pt @ ≤200dpi ≈ ≤1112px wide — proves the DPI cap kicked in
        self.assertLessEqual(img.width(), 1200)
        self.assertGreater(img.width(), 100)

    def test_print_to_pdf_printer_emits_all_pages(self):
        win, tmp = self._win_with(pages=3)
        out = os.path.join(tmp, "out.pdf")
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(out)
        win._print_to(printer)
        self.assertTrue(os.path.exists(out) and os.path.getsize(out) > 0)
        chk = fitz.open(out)
        try:
            self.assertEqual(chk.page_count, 3)
        finally:
            chk.close()

    def test_print_to_honours_page_range(self):
        win, tmp = self._win_with(pages=4)
        out = os.path.join(tmp, "range.pdf")
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(out)
        printer.setFromTo(2, 3)          # print only pages 2–3
        win._print_to(printer)
        chk = fitz.open(out)
        try:
            self.assertEqual(chk.page_count, 2)
        finally:
            chk.close()

    def test_new_printer_avoids_highres_query(self):
        # HighResolution (1200 dpi) queries the printer at construction and can
        # hang; _new_printer builds a ScreenResolution printer bumped to 300 dpi.
        win, _ = self._win_with(pages=1)
        p = win._new_printer()
        self.assertEqual(p.resolution(), 300)

    def test_print_document_prints_via_native_dialog(self):
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        win, tmp = self._win_with(pages=2)
        out = os.path.join(tmp, "native.pdf")

        def fake_exec(dlg):
            dlg.printer().setOutputFormat(QPrinter.PdfFormat)
            dlg.printer().setOutputFileName(out)
            return QPrintDialog.Accepted

        from unittest import mock
        with mock.patch.object(QPrintDialog, "exec", fake_exec):
            win.print_document()
        self.assertTrue(os.path.exists(out) and os.path.getsize(out) > 0)
        chk = fitz.open(out)
        try:
            self.assertEqual(chk.page_count, 2)
        finally:
            chk.close()

    def test_print_document_cancelled_prints_nothing(self):
        from PySide6.QtPrintSupport import QPrintDialog
        win, tmp = self._win_with(pages=1)
        from unittest import mock
        with mock.patch.object(QPrintDialog, "exec",
                               lambda d: QPrintDialog.Rejected):
            win.print_document()   # must simply return, no exception

    def test_print_action_enabled_with_document(self):
        win, _ = self._win_with(pages=1)
        self.assertTrue(win.act_print.isEnabled())

    def test_print_action_disabled_without_document(self):
        from app.main_window import MainWindow
        win = MainWindow()
        self.assertFalse(win.act_print.isEnabled())


if __name__ == "__main__":
    unittest.main()
