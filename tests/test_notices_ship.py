"""The notices must reach the user, not just the repository.

`THIRD-PARTY-NOTICES.md` at the repo root satisfies nothing for somebody who
downloads the installer. MIT, BSD and the LGPL all require the notice to travel
with the **distributed form**, and this build has two of them -- the Inno
installer and the portable zip -- both packaged from `dist/DSI Redline/*`. So
the files go into the PyInstaller `datas`, which is the one place that reaches
both, and this asserts they are still there.

**Parsed with `ast`, never with a regex over the source.** The spec carries a
comment explaining exactly why those files are bundled, and that comment names
both of them -- so a text search for `THIRD-PARTY-NOTICES.md` in the spec passes
with the entry deleted and the comment left behind. That is the inverted dead
gate this repository family has paid for repeatedly, and it is avoidable here by
reading the assignment rather than the page.

This cannot prove the built artifact contains them -- PyInstaller runs on
Windows and nothing here does. It proves the declaration, which is the half that
is checkable locally and the half that gets deleted by accident.
"""

from __future__ import annotations

import ast
import pathlib
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
SPEC = REPO / "packaging" / "DSI_Redline.spec"
NOTICES = REPO / "THIRD-PARTY-NOTICES.md"
LICENSES = REPO / "licenses"


def _datas_strings() -> list[str]:
    """Every string literal in the spec's `datas` assignment, comments gone.

    `ast` drops comments entirely, which is the property being relied on.
    """
    tree = ast.parse(SPEC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "datas" in names:
                return [n.value for n in ast.walk(node.value)
                        if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return []


class TestTheNoticesAreBundled(unittest.TestCase):

    def test_the_notices_file_exists_and_says_something(self) -> None:
        self.assertTrue(NOTICES.is_file(), "THIRD-PARTY-NOTICES.md is missing")
        text = NOTICES.read_text(encoding="utf-8")
        self.assertGreater(len(text), 2000,
                           "the notices file is too short to be a real audit")
        # The load-bearing finding: PyMuPDF's arm is unresolved and the file
        # must keep saying so rather than quietly reading as settled.
        self.assertIn("AGPL", text,
                      "the notices no longer record the PyMuPDF AGPL arm")

    def test_the_licence_texts_the_packages_do_not_ship_are_supplied(self) -> None:
        """PySide6 and shiboken6 ship no licence file of their own -- measured
        on the 6.11.2 wheels, zero LICENSE/COPYING/NOTICE entries in either
        distribution. The LGPL requires the text to accompany the binary, so
        this project supplies it; if that file goes, the installer ships LGPL
        code with no LGPL text."""
        self.assertTrue(LICENSES.is_dir(), "licenses/ is missing")
        lgpl = LICENSES / "LGPL-3.0.txt"
        self.assertTrue(lgpl.is_file(), "the LGPL text nothing else supplies is gone")
        body = lgpl.read_text(encoding="utf-8")
        self.assertIn("GNU LESSER GENERAL PUBLIC LICENSE", body)
        self.assertIn("Version 3", body)

    def test_the_spec_bundles_the_notices_into_the_distributed_form(self) -> None:
        strings = _datas_strings()
        self.assertTrue(strings, "no `datas` assignment found in the spec")
        joined = " ".join(strings)
        self.assertIn("THIRD-PARTY-NOTICES.md", joined,
                      "the notices are not bundled, so neither the installer "
                      "nor the portable zip carries them")
        self.assertIn("licenses", joined,
                      "the licences directory is not bundled")

    def test_the_check_reads_the_assignment_rather_than_the_comment(self) -> None:
        """The guard on the guard.

        The spec's comment names both files by design, so this asserts the
        extraction is genuinely blind to comments -- otherwise every assertion
        above passes over prose while the bundling is gone.
        """
        source = SPEC.read_text(encoding="utf-8")
        self.assertIn("# ", source, "the spec has no comments to be fooled by")
        stripped = ast.unparse(ast.parse(source))
        self.assertNotIn("#", stripped.split("THIRD-PARTY")[0][-200:],
                         "ast.unparse leaked a comment, which should be impossible")
        # And the real proof: the extraction finds it in the assignment.
        self.assertIn("THIRD-PARTY-NOTICES.md", " ".join(_datas_strings()))


if __name__ == "__main__":
    unittest.main()
