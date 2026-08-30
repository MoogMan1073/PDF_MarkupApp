"""Every test in this suite must be reachable, and reachable the same way.

Two ways a test module here silently runs fewer tests than it holds. Neither
is a failure -- both are a *smaller number*, which no runner reports as
anything.

**A misplaced ``if __name__ == "__main__"`` block hides everything below it
from a direct run.** ``python3 tests/test_requirements.py`` ran **3** tests
where ``python3 -m unittest tests.test_requirements`` ran **5**: the guard sat
at line 44 and ``TestVersionIsStatedOnce`` began at 48, so the two tests that
vanished were the version-drift gates -- the ones that exist because the
installer once sat at 1.4.0 while the app moved on. Four modules carried the
guard mid-file; in three of them it was harmless only because those modules
import ``app`` at module scope and cannot be run as scripts at all. That is
luck, not a design, and it is exactly the kind that expires.

**A Qt-dependent class without the ``skipUnless`` its siblings carry errors
instead of skipping.** ``tests/test_v14_audit_panel.py`` guards its PySide6
import into ``_QT_OK`` and decorates the classes that need it;
``TestRolledUpFindingOnScreen`` was missing one, so a machine without Qt got
``FAILED (errors=1, skipped=31)`` where it should get a clean skip. An error
is loud, which is better than the alternative -- but it is loud about the
wrong thing, and it makes a legitimately-skipping run look broken.

Both gates sweep **the artifact** rather than a list of the modules that had
the problem when this was written. A gate scoped to today's offenders covers
what was there when the list was made.
"""

import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _modules():
    return sorted(n for n in os.listdir(HERE)
                  if n.startswith("test_") and n.endswith(".py"))


def _tree(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=name)


class TestTheSweepFindsSomething(unittest.TestCase):
    """The gate's own premise. Both checks below are 'nothing was wrong'
    assertions, and a sweep that has stopped finding modules reports exactly
    that while measuring nothing.
    """

    def test_the_module_scan_finds_the_suite(self):
        found = _modules()
        self.assertGreater(
            len(found), 20,
            "the module scan found almost nothing; every check in this file "
            "would now pass over an empty list")
        self.assertIn("test_requirements.py", found)
        self.assertIn("test_v14_audit_panel.py", found)


class TestNoTestIsHiddenByAMisplacedMainGuard(unittest.TestCase):
    def test_the_main_guard_is_the_last_thing_in_the_file(self):
        for name in _modules():
            with self.subTest(name):
                tree = _tree(name)
                guards = [n.lineno for n in tree.body
                          if isinstance(n, ast.If)
                          and ast.dump(n.test).count("__main__")]
                if not guards:
                    continue
                below = [n.name for n in tree.body
                         if isinstance(n, ast.ClassDef)
                         and n.lineno > min(guards)]
                self.assertEqual(
                    below, [],
                    f"{name}: the `if __name__ == \"__main__\"` guard at line "
                    f"{min(guards)} sits above {below} -- a direct run of this "
                    "file executes unittest.main() before those classes are "
                    "defined, and reports a smaller number with no error. "
                    "Move the guard to the end of the file.")


class TestNoClassUsesAGuardedImportWithoutSkipping(unittest.TestCase):
    """A name bound inside a ``try: import ...`` is absent when it fails.

    Limit, stated rather than discovered later: this reads **direct** use of
    such a name inside a class body. A class calling a module-level helper
    that uses one is not caught. Widening it means resolving calls, which is
    a different tool; the direct case is what fired here, on a class whose
    ``setUpClass`` calls ``QApplication.instance()`` on line two.

    **Calibrated before it was trusted, and its first draft cried wolf.**
    ``unittest.skipUnless`` sets ``__unittest_skip__`` on the class it
    decorates and a subclass **inherits it** -- measured, not assumed: a
    child of a skipped base reports ``OK (skipped=2)`` and
    ``Child.__unittest_skip__`` is ``True``. So ``test_v12_order.py``'s
    ``TestDrawNewOnce`` and ``TestStackingOrder`` are covered by the ``_Base``
    above them and the whole module skips cleanly (10 of 10). A gate that
    flags a working file is one nobody reads twice, so ancestry counts --
    within this module, which is where these bases live.
    """

    def _decorated(self, node, by_name):
        """Is this class skipped -- itself, or through a base in this file?"""
        seen = set()
        stack = [node]
        while stack:
            cls = stack.pop()
            if cls.name in seen:
                continue
            seen.add(cls.name)
            if any("skip" in ast.dump(d).lower() for d in cls.decorator_list):
                return True
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id in by_name:
                    stack.append(by_name[base.id])
        return False

    def _guarded_names(self, tree):
        names = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    for alias in stmt.names:
                        names.add((alias.asname or alias.name).split(".")[0])
        return names

    def test_a_class_touching_an_optional_import_carries_a_skip(self):
        for name in _modules():
            tree = _tree(name)
            guarded = self._guarded_names(tree)
            if not guarded:
                continue
            by_name = {n.name: n for n in tree.body
                       if isinstance(n, ast.ClassDef)}
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if self._decorated(node, by_name):
                    continue
                used = sorted({n.id for n in ast.walk(node)
                               if isinstance(n, ast.Name) and n.id in guarded})
                with self.subTest(f"{name}::{node.name}"):
                    self.assertEqual(
                        used, [],
                        f"{name}: {node.name} uses {used}, which is bound "
                        "inside a guarded import, and carries no skip "
                        "decorator -- without that dependency it raises "
                        "NameError instead of skipping. Its siblings in the "
                        "same file show the decorator to copy.")


if __name__ == "__main__":
    unittest.main()
