"""Exporting an audit report.

Every format carries the two things that make a finding checkable — the clause
it rests on and the facts behind it — and the coverage statement, which is not
optional in any of them. Qt-free.
"""

import os
import tempfile
import unittest

from app.audit.findings import (AuditRun, Coverage, Finding, Waiver,
                                POTENTIAL, INFO)
from app.export.audit_export import (export_csv, export_html, export_markdown,
                                     export_report)


class _Doc:
    """The little a report needs from a document."""

    def __init__(self, findings, run, waivers=None):
        self.findings = findings
        self.audit_run = run
        self.waivers = waivers or {}
        self.path = "/tmp/Demo Panel.pdf"

    def waiver_for(self, key):
        return self.waivers.get(key)


def _doc(waived=False):
    findings = [
        Finding(key="k1", rule_id="DRC-XREF-WIRE-RECIP-001", severity=POTENTIAL,
                message="Wire 400790 declares sheet 400 but appears only on 500.",
                clause="internal 2026-08 wire numbering convention",
                sheet="500", page=8, subject_id="400790", x=1.0, y=2.0,
                evidence={"declared_sheet": 400, "seen_sheets": [500]},
                status="waived" if waived else "open"),
        Finding(key="k2", rule_id="DRC-TAG-FAMILY-001", severity=INFO,
                message="Tag POT-70024 uses family code POT.",
                clause="internal 2026-08 family codes",
                sheet="700", page=11, subject_id="POT-70024", x=1.0, y=2.0),
    ]
    run = AuditRun(eligible=63, checked=47, skipped=16, packs=["drc-base@1.0.0"],
                   coverage=[Coverage(rule_id="DRC-TAG-DUP-001", eligible=63,
                                      checked=47, skipped=16,
                                      reasons={"missing catalog": 16})])
    waivers = {"k1": Waiver(key="k1", reason="Accepted by client",
                            author="LWH")} if waived else {}
    return _Doc(findings, run, waivers)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def _path(self, name):
        return os.path.join(self.tmp, name)

    def _read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class TestMarkdown(_Base):
    def test_contains_findings_clauses_and_evidence(self):
        text = self._read(export_markdown(_doc(), self._path("r.md")))
        self.assertIn("400790", text)
        self.assertIn("wire numbering convention", text)
        self.assertIn("declared_sheet=400", text)

    def test_states_coverage(self):
        text = self._read(export_markdown(_doc(), self._path("r.md")))
        self.assertIn("47 of 63", text)
        self.assertIn("Not checked", text)
        self.assertIn("missing catalog", text)

    def test_is_advisory_not_a_verdict(self):
        text = self._read(export_markdown(_doc(), self._path("r.md"))).lower()
        self.assertIn("not a determination of compliance", text)
        for banned in ("is compliant", "passes", "certified"):
            self.assertNotIn(banned, text)

    def test_records_the_waiver_and_who_made_it(self):
        text = self._read(export_markdown(_doc(waived=True), self._path("r.md")))
        self.assertIn("Accepted by client", text)
        self.assertIn("LWH", text)
        self.assertIn("waived", text.lower())

    def test_empty_report_does_not_read_as_clean(self):
        doc = _Doc([], AuditRun(eligible=10, checked=4, skipped=6))
        text = self._read(export_markdown(doc, self._path("r.md")))
        self.assertIn("No findings", text)
        self.assertIn("coverage", text.lower())


class TestCsv(_Base):
    def test_has_a_header_and_a_row_per_finding(self):
        import csv
        path = export_csv(_doc(), self._path("r.csv"))
        with open(path, encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0][0], "Severity")
        self.assertIn("400790", rows[1])
        self.assertEqual(rows[1][3], "9")          # page 8, shown 1-based

    def test_coverage_is_appended(self):
        text = self._read(export_csv(_doc(), self._path("r.csv")))
        self.assertIn("Coverage", text)
        self.assertIn("47 of 63", text)


class TestHtml(_Base):
    def test_is_self_contained(self):
        text = self._read(export_html(_doc(), self._path("r.html")))
        self.assertTrue(text.startswith("<!doctype html"))
        self.assertNotIn("http", text.split("</style>")[0])

    def test_escapes_content(self):
        doc = _doc()
        doc.findings[0].message = 'Tag <script>alert("x")</script> is odd'
        text = self._read(export_html(doc, self._path("r.html")))
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;", text)

    def test_shows_coverage_table_and_the_gap(self):
        text = self._read(export_html(_doc(), self._path("r.html")))
        self.assertIn("Coverage", text)
        self.assertIn("missing catalog", text)
        self.assertIn("skipped item is not a passing item", text)

    def test_waived_findings_are_marked(self):
        text = self._read(export_html(_doc(waived=True), self._path("r.html")))
        self.assertIn("waived", text)


class TestFormatChoice(_Base):
    def test_extension_picks_the_format(self):
        self.assertTrue(self._read(export_report(_doc(), self._path("a.md")))
                        .startswith("# Design rule check"))
        self.assertIn("Severity", self._read(export_report(_doc(), self._path("a.csv"))))
        self.assertTrue(self._read(export_report(_doc(), self._path("a.html")))
                        .startswith("<!doctype html"))

    def test_unknown_extension_falls_back_to_html(self):
        self.assertTrue(self._read(export_report(_doc(), self._path("a.txt")))
                        .startswith("<!doctype html"))


if __name__ == "__main__":
    unittest.main()
