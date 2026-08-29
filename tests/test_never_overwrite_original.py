"""The repository's first boundary, as a test rather than a sentence.

CLAUDE.md opens with "The original file is never overwritten". Before this
module the only guard was `tests/test_storage.py::test_document_save_does_not_
touch_original`, and it is narrow in two ways that matter: it calls `doc.save()`
with no arguments, so it exercises only the DERIVED destination and never the
caller-supplied one; and it compares `os.path.getsize`, so a replacement of
similar size would pass it.

`export_annotated_pdf` had no test at all. Measured on the code as it stood:
exporting onto the open drawing replaced it, wrote no `.marked.pdf`, and left
every later save writing two copies of every mark -- because the clobbered file
is what `original_pdf_path` resolves to, `is_marked_pdf` says False, and so the
`strip_annotations` branch that exists to stop exactly that never runs.

Every assertion here is on BYTES (sha256) or on a page/annotation count read
back off disk. A size comparison is what let this through.

Model layer only, so it runs wherever PyMuPDF does -- these are the paths that
destroy data, and gating them behind Qt would put the boundary's only real test
in the 219 that skip when PySide6 is absent.
"""

import hashlib
import os
import tempfile
import unittest

import fitz

from app.model.annotations import Annotation, KIND_RECT
from app.model.document import Document
from app.model.storage import (
    ProtectedPathError, marked_pdf_path, protected_reason, same_path,
    sidecar_path,
)
from app.tools import pdf_ops


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _pdf(path, pages=3, label="SHEET"):
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 100), f"{label} {i + 1}")
    doc.save(path)
    doc.close()
    return path


def _annots(path):
    doc = fitz.open(path)
    n = sum(len(list(page.annots() or [])) for page in doc)
    doc.close()
    return n


def _pages(path):
    doc = fitz.open(path)
    n = doc.page_count
    doc.close()
    return n


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = _pdf(os.path.join(self.tmp, "DWG-101.pdf"))
        self.pristine = _sha(self.src)

    def _open(self, path=None):
        doc = Document(path or self.src)
        doc.load()
        return doc

    def _marked(self, doc, n=1):
        for _ in range(n):
            doc.store.add(Annotation(page=0, kind=KIND_RECT, rect=(50, 50, 200, 120)))
        return doc

    def assertIntact(self, path=None):
        path = path or self.src
        self.assertEqual(_sha(path), self.pristine,
                         f"{os.path.basename(path)} was rewritten")


class TestTheOriginalIsNeverOverwritten(_Base):
    """The reported defect, and each way of reaching it."""

    def test_export_annotated_onto_the_open_original_is_refused(self):
        doc = self._marked(self._open())
        with self.assertRaises(ProtectedPathError):
            doc.export_annotated_pdf(self.src)
        self.assertIntact()

    def test_export_flattened_onto_the_open_original_is_refused(self):
        """The worse of the two: a flattened export bakes the marks into the
        page CONTENT, so `strip_annotations` cannot undo it and there is no
        route back at all."""
        doc = self._marked(self._open())
        with self.assertRaises(ProtectedPathError):
            doc.export_flattened_pdf(self.src)
        self.assertIntact()

    def test_export_onto_the_original_is_refused_when_the_document_is_the_marked_copy(self):
        doc = self._marked(self._open())
        marked = doc.save()
        second = self._open(marked)
        with self.assertRaises(ProtectedPathError):
            second.export_annotated_pdf(self.src)
        self.assertIntact()

    def test_export_onto_the_originals_path_is_refused_when_the_original_is_GONE(self):
        """Not a clobber -- it would CREATE the pristine base every later open
        reads from, carrying marks. The next save then writes them again on
        top of it, permanently."""
        doc = self._marked(self._open())
        marked = doc.save()
        os.remove(self.src)
        second = self._open(marked)
        with self.assertRaises(ProtectedPathError):
            second.export_annotated_pdf(self.src)
        self.assertFalse(os.path.exists(self.src))

    def test_the_refusal_names_the_file_and_says_what_to_do(self):
        """The message IS the interface: `main_window.export_pdf` catches
        Exception and shows `str(e)`."""
        doc = self._open()
        with self.assertRaises(ProtectedPathError) as cm:
            doc.export_annotated_pdf(self.src)
        msg = str(cm.exception)
        self.assertIn("DWG-101.pdf", msg)
        self.assertIn(os.path.basename(marked_pdf_path(self.src)), msg)

    def test_save_as_onto_the_documents_own_original_is_refused(self):
        doc = self._marked(self._open())
        with self.assertRaises(ProtectedPathError):
            doc.save_as(self.src)


class TestAnotherDrawingUnderReviewIsProtectedToo(_Base):
    """A reviewer works on a FOLDER of drawings, and a save dialog opened there
    puts every one of them one click away. Measured before the guard: an export
    aimed at a neighbouring drawing replaced it wholesale -- a three-page
    drawing became a one-page copy of the acting document."""

    def _victim(self, name="DWG-102.pdf", pages=4):
        path = _pdf(os.path.join(self.tmp, name), pages=pages, label="VICTIM")
        doc = Document(path)
        doc.load()
        doc.store.add(Annotation(page=0, kind=KIND_RECT, rect=(9, 9, 90, 90)))
        doc.save()
        return path

    def test_export_onto_a_neighbouring_drawing_with_marks_is_refused(self):
        victim = self._victim()
        before, pages = _sha(victim), _pages(victim)
        doc = self._marked(self._open())
        with self.assertRaises(ProtectedPathError):
            doc.export_annotated_pdf(victim)
        self.assertEqual((_sha(victim), _pages(victim)), (before, pages))

    def test_flattened_export_onto_a_neighbouring_drawing_is_refused(self):
        victim = self._victim()
        before = _sha(victim)
        doc = self._marked(self._open())
        with self.assertRaises(ProtectedPathError):
            doc.export_flattened_pdf(victim)
        self.assertEqual(_sha(victim), before)

    def test_a_page_tool_will_not_write_over_a_drawing_with_marks(self):
        victim = self._victim()
        before, pages = _sha(victim), _pages(victim)
        with self.assertRaises(ProtectedPathError):
            pdf_ops.rotate_pdf(self.src, victim, 90)
        self.assertEqual((_sha(victim), _pages(victim)), (before, pages))

    def test_save_as_onto_a_drawing_with_marks_is_refused(self):
        victim = self._victim()
        before = _sha(victim)
        doc = self._marked(self._open())
        with self.assertRaises(ProtectedPathError):
            doc.save_as(victim)
        self.assertEqual(_sha(victim), before)

    def test_a_file_merely_OPENED_is_NOT_protected(self):
        """Opening a PDF creates its `.markup.db` unconditionally, so a sidecar
        means "seen here", not "has marks". Testing for the file's existence
        refused an ordinary second export and broke two of this repository's
        own regression tests; the rule asks whether the sidecar holds
        ANNOTATIONS."""
        looked_at = _pdf(os.path.join(self.tmp, "client-copy.pdf"), pages=1)
        Document(looked_at).load()
        self.assertTrue(os.path.exists(sidecar_path(looked_at)))
        self.assertEqual(protected_reason(looked_at), "")
        doc = self._marked(self._open())
        doc.export_annotated_pdf(looked_at)          # must not raise
        self.assertEqual(_annots(looked_at), 1)


class TestAPageToolWillNotEatItsOwnInput(_Base):
    """PyMuPDF refuses a save from the document that opened the file
    ("save to original must be incremental"), and every one of these builds a
    NEW document instead -- so that check never fires and the write lands."""

    def test_extract_pages_onto_its_source_is_refused(self):
        with self.assertRaises(ProtectedPathError):
            pdf_ops.extract_pages(self.src, self.src, [0], merge=True)
        self.assertIntact()

    def test_split_ranges_onto_its_source_is_refused(self):
        with self.assertRaises(ProtectedPathError):
            pdf_ops.split_ranges(self.src, self.src, [(0, 1)], merge=True)
        self.assertIntact()

    def test_combine_pdfs_onto_any_of_its_inputs_is_refused(self):
        other = _pdf(os.path.join(self.tmp, "OTHER.pdf"), pages=2, label="OTHER")
        for target in (self.src, other):
            with self.subTest(os.path.basename(target)):
                before = _sha(target)
                with self.assertRaises(ProtectedPathError):
                    pdf_ops.combine_pdfs([self.src, other], target)
                self.assertEqual(_sha(target), before)

    # Any call by which this module has been observed to put bytes on disk.
    # `save` is PyMuPDF's; `convert` is pdf2docx's, and leaving it out is what
    # made the first version of this gate DEAD -- removing `pdf_to_docx`'s
    # guard changed nothing, because the scan did not count that function as a
    # writer at all. A gate scoped to the one shape you happened to think of
    # passes over every other shape in silence.
    _WRITE_CALLS = {"save", "convert", "write", "write_bytes", "write_text"}

    def test_every_writer_in_pdf_ops_is_guarded(self):
        """A gate over the ARTIFACT, not over a list of the functions that
        existed when this was written -- the whole family shares one defect, so
        a new writer added without a guard fails here rather than on somebody's
        drawing set."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(pdf_ops))
        unguarded = []
        seen = []
        for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
            writes = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                         and c.func.attr in self._WRITE_CALLS for c in ast.walk(fn))
            guards = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                         and c.func.id == "_guard_out" for c in ast.walk(fn))
            if writes:
                seen.append(fn.name)
                if not guards:
                    unguarded.append(fn.name)
        self.assertEqual(unguarded, [], "a writer with no _guard_out call")
        # ...and the scan must still be FINDING the writers. Without this the
        # gate goes green the day a rename makes it match nothing, which is the
        # same silence it was written to break.
        self.assertGreaterEqual(len(seen), 10, f"the writer scan found only {seen}")
        self.assertIn("pdf_to_docx", seen, "the non-PyMuPDF writer is not counted")


class TestTheOrdinaryWorkflowStillWorks(_Base):
    """A guard that refuses too much is a worse defect than the one it fixes.
    Every one of these was measured working before the change and must stay so."""

    def test_a_plain_save_writes_the_marked_copy(self):
        doc = self._marked(self._open())
        out = doc.save()
        self.assertTrue(out.endswith(".marked.pdf"))
        self.assertEqual(_annots(out), 1)
        self.assertIntact()

    def test_re_saving_an_open_marked_pdf_still_works(self):
        """The `out_is_open` temp-and-replace branch -- which is what defeated
        PyMuPDF's own refusal and made the clobber possible. It is legitimate
        here and must keep working."""
        doc = self._marked(self._open())
        marked = doc.save()
        second = self._open(marked)
        self.assertEqual(len(second.store.all()), 1)
        second.save()
        self.assertEqual(_annots(marked), 1)
        self.assertIntact()

    def test_export_to_a_new_name_works(self):
        doc = self._marked(self._open())
        dest = os.path.join(self.tmp, "for-the-client.pdf")
        doc.export_annotated_pdf(dest)
        self.assertEqual(_annots(dest), 1)
        self.assertIntact()

    def test_flattened_export_to_a_new_name_works(self):
        doc = self._marked(self._open())
        dest = os.path.join(self.tmp, "flat.pdf")
        doc.export_flattened_pdf(dest)
        self.assertTrue(os.path.exists(dest))
        self.assertIntact()

    def test_fork_to_a_new_name_works(self):
        doc = self._marked(self._open())
        doc.save_as(os.path.join(self.tmp, "fork.pdf"))
        self.assertEqual(os.path.basename(doc.path), "fork.pdf")
        self.assertIntact()

    def test_exporting_onto_a_marked_pdf_is_allowed(self):
        """This app's own artifact, rewritten on every save by design."""
        doc = self._marked(self._open())
        marked = doc.save()
        doc.export_annotated_pdf(marked)
        self.assertTrue(os.path.exists(marked))

    def test_page_tools_write_to_new_files(self):
        out = os.path.join(self.tmp, "out.pdf")
        pdf_ops.extract_pages(self.src, out, [0, 2], merge=True)
        self.assertEqual(_pages(out), 2)
        folder = os.path.join(self.tmp, "pages")
        self.assertEqual(len(pdf_ops.extract_pages(self.src, folder, [0, 1], merge=False)), 2)
        self.assertIntact()


class TestSamePath(_Base):
    """`os.path.abspath` was the comparison `save` used, and it is not enough:
    on Windows one file has many spellings. `os.path.samefile` is right and
    raises when either side is missing -- which an export destination usually
    is, so both halves are needed."""

    def test_a_missing_destination_is_still_comparable(self):
        missing = os.path.join(self.tmp, "not-here-yet.pdf")
        self.assertTrue(same_path(missing, os.path.join(self.tmp, ".", "not-here-yet.pdf")))
        self.assertFalse(same_path(missing, os.path.join(self.tmp, "other.pdf")))

    def test_an_existing_pair_is_asked_of_the_filesystem(self):
        """A HARD link, not a symlink -- and the difference is why this test
        exists at all. `os.path.realpath` resolves a symlink, so the fallback
        answers that case correctly on its own and a symlink fixture leaves the
        `os.path.samefile` branch unexercised: measured, deleting that branch
        kept a symlink test green. A hard link has two real names that
        `realpath` does not collapse, so only `samefile` can see it."""
        link = os.path.join(self.tmp, "hardlink.pdf")
        try:
            os.link(self.src, link)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("this filesystem does not support hard links")
        self.assertNotEqual(os.path.realpath(self.src), os.path.realpath(link),
                            "this fixture is not exercising the samefile branch")
        self.assertTrue(same_path(self.src, link))

    def test_neither_side_may_be_empty(self):
        self.assertFalse(same_path("", self.src))
        self.assertFalse(same_path(self.src, None))


if __name__ == "__main__":
    unittest.main()
