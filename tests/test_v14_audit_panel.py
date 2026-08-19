"""The Audit tab: findings on screen, marks on the sheet, and waivers.

Two things get tested harder than the rest, because they are the requirements
most easily lost in a refactor: coverage is stated where a reader cannot miss
it, and a finding drawn on the sheet can never obscure or be mistaken for a
user's own markup.
"""

import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QTabWidget
    _QT_OK = True
except Exception:                                     # pragma: no cover
    _QT_OK = False

import fitz

from app import audit
from app.audit.findings import (AuditRun, Coverage, Finding, DEFINITE,
                                POTENTIAL, INFO, STATUS_WAIVED)

HAVE_PYDRC = audit.available()


def _drawing(path):
    doc = fitz.open()
    for title, number, body in (
        ("TITLE PAGE", "EL2507777-000", ()),
        ("24 VDC DISTRIBUTION", "EL2507777-400", ("400010", "PB-40010")),
        ("TERMINAL BLOCK LAYOUT", "EL2507777-800", ("400010", "999990")),
    ):
        page = doc.new_page(width=792, height=1224)
        page.insert_text((40.0, 1000.0), title, rotate=270)
        page.insert_text((70.0, 1000.0), number, rotate=270)
        for i, line in enumerate(body):
            page.insert_text((300.0, 200.0 + i * 16.0), line, rotate=270)
        page.set_rotation(270)
    doc.save(path)
    doc.close()
    return path


def _findings():
    return [
        Finding(key="k1", rule_id="DRC-XREF-WIRE-RECIP-001", severity=POTENTIAL,
                message="Wire 999990 declares sheet 999 but appears only on 800.",
                clause="internal wire numbering convention", sheet="800", page=2,
                subject_id="999990", x=100.0, y=200.0, w=30.0, h=8.0),
        Finding(key="k2", rule_id="DRC-TAG-FAMILY-001", severity=INFO,
                message="Tag PB-40010 uses family code PB.", sheet="400", page=1,
                subject_id="PB-40010", x=50.0, y=60.0, w=40.0, h=8.0),
        Finding(key="k3", rule_id="DRC-SHEET-INDEX-001", severity=POTENTIAL,
                message="Index declares section 200 but no sheet carries it.",
                sheet="", page=0, subject_id="200"),
    ]


def _run():
    return AuditRun(eligible=63, checked=47, skipped=16, packs=["drc-base@1.0.0"],
                    coverage=[Coverage(rule_id="ERC-AMP-001", eligible=63,
                                       checked=47, skipped=16,
                                       reasons={"missing conductor size": 16})])


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestAuditPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from app.model.document import Document
        self.tmp = tempfile.mkdtemp()
        self.src = _drawing(os.path.join(self.tmp, "set.pdf"))
        self.doc = Document(self.src)
        self.doc.load()
        self.doc.set_findings(_findings(), _run())

    def tearDown(self):
        self.doc.close()

    def _panel(self):
        from app.panels.audit_panel import AuditPanel
        p = AuditPanel()
        p.set_document(self.doc)
        return p

    def _rows(self, panel):
        out = []

        def walk(node):
            f = node.data(0, Qt.UserRole)
            if f is not None:
                out.append(f)
            for i in range(node.childCount()):
                walk(node.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
        return out

    def test_lists_every_finding(self):
        panel = self._panel()
        self.assertEqual({f.key for f in self._rows(panel)}, {"k1", "k2", "k3"})

    def test_coverage_is_stated_in_the_header(self):
        # Above the list, not below it: "no findings" and "could not check"
        # must never read the same.
        panel = self._panel()
        text = panel.coverage_label.text()
        self.assertIn("47 of 63", text)
        self.assertIn("16 not checked", text)
        self.assertIn("missing conductor size", text)

    def test_header_says_the_review_is_advisory(self):
        panel = self._panel()          # keep a reference; Qt owns the widgets
        self.assertIn("dvisory", panel.coverage_label.text())

    def test_header_before_any_run(self):
        from app.panels.audit_panel import AuditPanel
        panel = AuditPanel()
        self.assertIn("No design rule check", panel.coverage_label.text())

    def test_groups_by_severity_by_default(self):
        panel = self._panel()
        groups = [panel.tree.topLevelItem(i).text(0)
                  for i in range(panel.tree.topLevelItemCount())]
        self.assertEqual(groups, ["Potential issue", "Informational"])

    def test_filter_narrows_the_list(self):
        panel = self._panel()
        panel.search.setText("999990")
        self.assertEqual([f.key for f in self._rows(panel)], ["k1"])

    def test_informational_can_be_hidden(self):
        panel = self._panel()
        panel.show_info.setChecked(False)
        self.assertNotIn("k2", {f.key for f in self._rows(panel)})

    def test_waived_rows_are_struck_through_and_can_be_hidden(self):
        self.doc.waive_finding("k1", "Accepted", "LWH")
        panel = self._panel()
        row = next(n for n in self._walk_items(panel)
                   if n.data(0, Qt.UserRole) is not None
                   and n.data(0, Qt.UserRole).key == "k1")
        self.assertTrue(row.font(0).strikeOut())
        self.assertEqual(row.text(panel.COL_STATUS), "Waived")
        panel.hide_waived.setChecked(True)
        self.assertNotIn("k1", {f.key for f in self._rows(panel)})

    def _walk_items(self, panel):
        out = []

        def walk(node):
            out.append(node)
            for i in range(node.childCount()):
                walk(node.child(i))

        for i in range(panel.tree.topLevelItemCount()):
            walk(panel.tree.topLevelItem(i))
        return out

    def test_double_click_asks_to_jump(self):
        panel = self._panel()
        seen = []
        panel.activated.connect(seen.append)
        row = next(n for n in self._walk_items(panel)
                   if n.data(0, Qt.UserRole) is not None)
        panel._on_double(row, 0)
        self.assertEqual(len(seen), 1)

    def test_double_click_on_a_group_header_does_nothing(self):
        panel = self._panel()
        seen = []
        panel.activated.connect(seen.append)
        panel._on_double(panel.tree.topLevelItem(0), 0)
        self.assertEqual(seen, [])

    def test_sorting_by_sheet_puts_numbers_in_order(self):
        panel = self._panel()
        panel.group_by.setCurrentIndex(3)          # no grouping
        panel._on_header_clicked(panel.COL_SHEET)
        sheets = [f.sheet for f in self._rows(panel)]
        self.assertEqual(sheets, sorted(sheets, key=lambda s: (0, int(s)) if s else (1, 0)))

    def test_count_line_reports_severities_and_waivers(self):
        self.doc.waive_finding("k1", "Accepted")
        panel = self._panel()
        text = panel.count_label.text()
        self.assertIn("waived", text)
        self.assertIn("informational", text)


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestFindingMarks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from app.model.document import Document
        self.tmp = tempfile.mkdtemp()
        self.src = _drawing(os.path.join(self.tmp, "set.pdf"))
        self.doc = Document(self.src)
        self.doc.load()

    def tearDown(self):
        self.doc.close()

    def _view(self):
        from app.viewer.pdf_view import PdfView
        v = PdfView()
        v.set_document(self.doc, None)
        return v

    def test_draws_one_mark_per_locatable_finding(self):
        view = self._view()
        view.draw_findings(_findings())
        # The set-wide index finding has nowhere to point.
        self.assertEqual(len(view._finding_items), 2)

    def test_marks_sit_below_every_user_mark(self):
        # Structural, not cosmetic: an audit overlay must not be able to hide
        # something a person drew.
        from app.viewer.annotation_items import ANNOT_Z
        view = self._view()
        view.draw_findings(_findings())
        for item in view._finding_items:
            self.assertLess(item.zValue(), ANNOT_Z)

    def test_marks_are_not_annotations(self):
        # The eraser, selection and hit-testing all key on an item's `.ann`.
        # Findings deliberately have none, so they cannot be rubbed out or
        # dragged, and they never reach the annotation store or the saved PDF.
        view = self._view()
        view.draw_findings(_findings())
        for item in view._finding_items:
            self.assertIsNone(getattr(item, "ann", None))
        self.assertEqual(len(self.doc.store.all()), 0)

    def test_redrawing_replaces_rather_than_accumulates(self):
        view = self._view()
        view.draw_findings(_findings())
        view.draw_findings(_findings())
        self.assertEqual(len(view._finding_items), 2)

    def test_clearing_removes_them(self):
        view = self._view()
        view.draw_findings(_findings())
        view.clear_findings()
        self.assertEqual(view._finding_items, [])

    def test_a_finding_with_no_extent_still_gets_a_visible_target(self):
        view = self._view()
        view.draw_findings([Finding(key="z", severity=POTENTIAL, page=1,
                                    x=40.0, y=40.0)])
        self.assertEqual(len(view._finding_items), 1)
        self.assertGreater(view._finding_items[0].rect().width(), 0)


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestWaiveDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_a_reason_is_required(self):
        from app.main_window import WaiveDialog
        dlg = WaiveDialog(_findings()[0], "LWH")
        self.assertFalse(dlg._ok.isEnabled())
        dlg.reason.setText("   ")
        self.assertFalse(dlg._ok.isEnabled())
        dlg.reason.setText("Accepted by client")
        self.assertTrue(dlg._ok.isEnabled())
        self.assertEqual(dlg.values(), ("Accepted by client", "LWH"))

    def test_shows_what_is_being_waived(self):
        from app.main_window import WaiveDialog
        from PySide6.QtWidgets import QLabel
        dlg = WaiveDialog(_findings()[0])
        texts = " ".join(w.text() for w in dlg.findChildren(QLabel))
        self.assertIn("999990", texts)
        self.assertIn("DRC-XREF-WIRE-RECIP-001", texts)


@unittest.skipUnless(_QT_OK, "PySide6 not available")
class TestSettingsTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_design_rules_tab_exists(self):
        from app.main_window import SettingsDialog
        from app.config import AppConfig
        dlg = SettingsDialog(AppConfig())
        tabs = dlg.findChild(QTabWidget)
        self.assertIn("Design rules",
                      [tabs.tabText(i) for i in range(tabs.count())])

    @unittest.skipUnless(HAVE_PYDRC, "PyDRC is not installed")
    def test_lists_the_rules_and_round_trips_a_change(self):
        from app.main_window import SettingsDialog
        from app.config import AppConfig
        config = AppConfig()
        before_disabled = config.audit_disabled_rules()
        before_overrides = config.audit_severity_overrides()
        try:
            dlg = SettingsDialog(config)
            self.assertTrue(dlg.drc_rows)
            rule_id, default_sev, chk, combo = dlg.drc_rows[0]
            chk.setCheckState(Qt.Unchecked)
            other = DEFINITE if default_sev != DEFINITE else INFO
            combo.setCurrentIndex(combo.findData(other))
            dlg.apply()
            self.assertIn(rule_id, config.audit_disabled_rules())
            self.assertEqual(config.audit_severity_overrides()[rule_id], other)
        finally:
            config.set_audit_disabled_rules(before_disabled)
            config.set_audit_severity_overrides(before_overrides)
            config.sync()


@unittest.skipUnless(_QT_OK and HAVE_PYDRC, "needs PySide6 and PyDRC")
class TestMainWindowIntegration(unittest.TestCase):
    """One end-to-end pass: run the check, see it, waive one, keep it."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = _drawing(os.path.join(self.tmp, "set.pdf"))
        # Run the worker inline: no thread, no modal dialog.
        import app.tools.runner as runner_mod
        self._real = runner_mod.run_with_progress

        def sync(parent, title, fn, on_done, on_error=None):
            try:
                on_done(fn(lambda d, t: None, lambda: False))
            except Exception as e:                 # pragma: no cover
                (on_error or (lambda m: None))(str(e))
            return None

        runner_mod.run_with_progress = sync

    def tearDown(self):
        import app.tools.runner as runner_mod
        runner_mod.run_with_progress = self._real

    def test_run_populates_panel_and_sheet_then_waiver_persists(self):
        from app.main_window import MainWindow
        from app.model.document import Document
        win = MainWindow()
        win.load_document(self.src)
        self.assertTrue(win.act_run_audit.isEnabled())

        win.run_audit()
        doc = win.document
        self.assertTrue(doc.findings)
        self.assertIsNotNone(doc.audit_run)
        self.assertIn("checked", win.audit_panel.coverage_label.text())
        self.assertTrue(win.view._finding_items)

        target = doc.findings[0]
        doc.waive_finding(target.key, "Accepted here", "LWH")
        win.run_audit()                     # a re-run must not undo it
        self.assertEqual(
            next(f for f in doc.findings if f.key == target.key).status,
            STATUS_WAIVED)

        doc.save()
        win.close()

        again = Document(self.src)
        again.load()
        self.assertEqual(again.waiver_for(target.key).reason, "Accepted here")
        again.close()

    def test_audit_is_unavailable_without_a_sidecar(self):
        from app.main_window import MainWindow
        win = MainWindow()
        win.load_document(self.src)
        win.document.sidecar_available = False
        win._update_actions_enabled(True)
        self.assertFalse(win.act_run_audit.isEnabled())
        win.close()


if __name__ == "__main__":
    unittest.main()
