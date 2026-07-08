"""v1.1.0 Phase 3: callout tool (text box + leader arrow to a target point)."""

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz

from app.model.annotations import (
    Annotation, AnnotationStore, KIND_CALLOUT, KIND_TEXTBOX, TEXT_KINDS,
)
from app.model.storage import (
    write_annotations_to_pdf, marked_pdf_path,
)
from app.model.document import Document

try:
    from PySide6.QtWidgets import QApplication
    _QT_OK = True
except Exception:  # pragma: no cover
    _QT_OK = False


class TestCalloutModel(unittest.TestCase):
    def test_callout_is_text_kind(self):
        self.assertIn(KIND_CALLOUT, TEXT_KINDS)
        a = Annotation(page=0, kind=KIND_CALLOUT, text="x")
        self.assertTrue(a.is_comment_like)
        self.assertTrue(a.shows_in_comments)

    def test_callout_point_roundtrips(self):
        a = Annotation(page=0, kind=KIND_CALLOUT, rect=(10, 10, 60, 40),
                       callout_point=(5.0, 90.0))
        b = Annotation.from_dict(a.to_dict())
        self.assertEqual(b.callout_point, (5.0, 90.0))

    def test_callout_point_none_roundtrips(self):
        a = Annotation(page=0, kind=KIND_CALLOUT)
        b = Annotation.from_dict(a.to_dict())
        self.assertIsNone(b.callout_point)


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestCalloutItem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _item(self, ann):
        from app.viewer.annotation_items import make_item

        class _V:
            select_mode = True
            store = AnnotationStore()
        return make_item(ann, _V())

    def test_factory_makes_callout_item(self):
        from app.viewer.annotation_items import CalloutItem
        it = self._item(Annotation(page=0, kind=KIND_CALLOUT,
                                   rect=(100, 100, 220, 150), text="hi",
                                   callout_point=(60, 220)))
        self.assertIsInstance(it, CalloutItem)
        self.assertIsNotNone(it._tip_handle)

    def test_default_tip_when_unset(self):
        it = self._item(Annotation(page=0, kind=KIND_CALLOUT,
                                   rect=(100, 100, 220, 150), text="hi"))
        # a tip is auto-placed below-left of the box
        self.assertIsNotNone(it.ann.callout_point)
        tx, ty = it.ann.callout_point
        self.assertLess(tx, 100)
        self.assertGreater(ty, 150)

    def test_bounding_includes_tip(self):
        it = self._item(Annotation(page=0, kind=KIND_CALLOUT,
                                   rect=(100, 100, 220, 150), text="hi",
                                   callout_point=(60, 220)))
        br = it.boundingRect()
        # tip is at local (-40, 120); the bounding rect must reach it
        self.assertLessEqual(br.left(), -40)
        self.assertGreaterEqual(br.bottom(), 120)

    def test_callout_not_rotated(self):
        it = self._item(Annotation(page=0, kind=KIND_CALLOUT,
                                   rect=(100, 100, 220, 150), rotation=45.0))
        it.sync_from_model()
        self.assertEqual(it.ann.rotation, 0.0)


class TestCalloutExport(unittest.TestCase):
    def _blank(self, path):
        d = fitz.open(); d.new_page(width=400, height=300); d.save(path); d.close()

    def test_export_writes_freetext_with_leader(self):
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, "d.pdf")
        self._blank(src)
        ann = Annotation(page=0, kind=KIND_CALLOUT, rect=(100, 100, 220, 150),
                         color=(1, 0, 0), text="SEE NOTE", callout_point=(60, 220))
        d = fitz.open(src)
        n = write_annotations_to_pdf(d, [ann])
        self.assertEqual(n, 1)
        mp = marked_pdf_path(src)
        d.save(mp)
        d.close()
        d2 = fitz.open(mp)
        found = []
        for a in d2[0].annots():
            found.append((a.type[1], a.info.get("content"),
                          d2.xref_get_key(a.xref, "CL")))
        d2.close()
        self.assertEqual(len(found), 1)
        typ, content, cl = found[0]
        self.assertEqual(typ, "FreeText")
        self.assertEqual(content, "SEE NOTE")
        self.assertEqual(cl[0], "array")           # a callout leader is present
        # tip (60,220 visual) -> PDF (60, 300-220=80)
        nums = [int(x) for x in cl[1].strip("[]").split()]
        self.assertEqual(nums[0], 60)
        self.assertEqual(nums[1], 80)

    def test_callout_roundtrips_via_sidecar(self):
        tmp = tempfile.mkdtemp()
        src = os.path.join(tmp, "d.pdf")
        self._blank(src)
        doc = Document(src); doc.load()
        doc.store.add(Annotation(page=0, kind=KIND_CALLOUT, rect=(100, 100, 220, 150),
                                 color=(1, 0, 0), text="SEE NOTE",
                                 callout_point=(60, 220)))
        doc.save(); doc.close()
        doc2 = Document(src); doc2.load()
        c = [a for a in doc2.store.all() if a.kind == KIND_CALLOUT][0]
        self.assertEqual(c.callout_point, (60, 220))
        self.assertEqual(c.text, "SEE NOTE")
        doc2.close()


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestCalloutInSidebar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_callout_listed_and_filterable(self):
        from app.panels.comment_panel import CommentPanel
        from PySide6.QtCore import Qt
        store = AnnotationStore()
        callout = Annotation(page=0, kind=KIND_CALLOUT, text="note", rect=(1, 1, 2, 2))
        store.add(callout, silent=True)
        panel = CommentPanel()
        panel.set_store(store, config=None)
        panel.refresh()
        rows = [panel.tree.topLevelItem(i).data(0, Qt.UserRole)
                for i in range(panel.tree.topLevelItemCount())]
        self.assertIn(callout, rows)
        # the Callout filter is index 7
        panel.type_filter.setCurrentIndex(7)
        panel.refresh()
        rows = [panel.tree.topLevelItem(i).data(0, Qt.UserRole)
                for i in range(panel.tree.topLevelItemCount())]
        self.assertEqual(rows, [callout])


if __name__ == "__main__":
    unittest.main()
