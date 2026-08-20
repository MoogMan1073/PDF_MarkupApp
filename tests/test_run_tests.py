"""The test runner's own skip attribution.

It has been wrong twice: once counting every skip against the design rule
library when most were Qt, and once failing a run whose Qt was fine because a
compound reason named PySide6 alongside PyDRC. Both are cheap to lock down.
"""

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "run_tests", os.path.join(HERE, "tools", "run_tests.py"))
run_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_tests)


class TestClassify(unittest.TestCase):
    def test_splits_the_two_causes(self):
        drc, qt = run_tests.classify(
            {"PyDRC is not installed": 15, "PySide6 not available": 47})
        self.assertEqual((drc, qt), (15, 47))

    def test_a_reason_naming_both_counts_against_the_rule_library(self):
        # Qt is installed by both workflows, so attributing this to Qt fails a
        # run that is working exactly as intended when no token is configured.
        drc, qt = run_tests.classify({"needs PySide6 and PyDRC": 2})
        self.assertEqual((drc, qt), (2, 0))

    def test_ezdxf_and_pydrc_is_a_rule_library_skip(self):
        drc, qt = run_tests.classify({"needs ezdxf and pydrc": 5})
        self.assertEqual((drc, qt), (5, 0))

    def test_unrelated_reasons_count_as_neither(self):
        drc, qt = run_tests.classify({"needs a display": 3})
        self.assertEqual((drc, qt), (0, 0))

    def test_nothing_skipped(self):
        self.assertEqual(run_tests.classify({}), (0, 0))


if __name__ == "__main__":
    unittest.main()
