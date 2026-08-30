"""The base requirements must be installable by anyone, without credentials.

A private ``git+https://`` dependency in ``requirements.txt`` fails for every
CI runner and every new developer who lacks access to that repository -- and it
fails at ``pip install``, before any of the graceful-degradation code that
makes the dependency optional in the first place ever gets to run. That
happened once; this keeps it from happening again.
"""

import os
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lines(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as fh:
        return [ln.strip() for ln in fh
                if ln.strip() and not ln.strip().startswith("#")]


class TestRequirements(unittest.TestCase):
    def test_base_requirements_need_no_credentials(self):
        for line in _lines("requirements.txt"):
            self.assertNotIn("git+", line,
                             "requirements.txt must install without repository "
                             "credentials; put VCS dependencies in "
                             "requirements-drc.txt (see CI.md)")

    def test_the_rule_library_is_still_declared_somewhere(self):
        # Optional is not the same as forgotten: dropping it from both files
        # would leave nothing telling anyone how to install it.
        self.assertTrue(any("pydrc" in ln.lower()
                            for ln in _lines("requirements-drc.txt")))

    def test_every_app_import_is_covered_by_the_base_requirements(self):
        # The app must start with only requirements.txt installed, so nothing
        # imported at module scope may live in the optional file.
        base = " ".join(_lines("requirements.txt")).lower()
        for dist in ("pyside6", "pymupdf", "pyyaml", "pillow"):
            self.assertIn(dist, base)


class TestVersionIsStatedOnce(unittest.TestCase):
    """The installer carries its own copy of the version, and it must agree.

    `app/__init__.py` is what the About box and the audit report show;
    `packaging/installer.iss` is what names the setup executable and what
    Windows records in Add/Remove Programs. They are two files, so they drift
    -- the installer sat at 1.4.0 while the app moved on, which would have
    shipped `DSI_Redline_Setup_1.4.0.exe` containing 1.5.0.

    A release is tagged `vX.Y.Z` and the tag triggers the build, so a third
    copy of the number lives in the tag. This test cannot see that one; it can
    at least stop the two in the tree disagreeing.
    """

    def _installer_version(self):
        import re
        path = os.path.join(HERE, "packaging", "installer.iss")
        with open(path, encoding="utf-8", errors="replace") as fh:
            m = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', fh.read())
        self.assertIsNotNone(m, "installer.iss no longer defines MyAppVersion")
        return m.group(1)

    def test_the_installer_and_the_app_agree(self):
        from app import __version__
        self.assertEqual(
            self._installer_version(), __version__,
            "packaging/installer.iss and app/__init__.py disagree about the "
            "version; bump both in the same commit.")

    def test_the_changelog_documents_the_current_version(self):
        from app import __version__
        path = os.path.join(HERE, "CHANGELOG.md")
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        self.assertIn(f"## v{__version__}", text,
                      f"CHANGELOG.md has no section for v{__version__}; the "
                      "changelog is the release notes for the tag.")


class TestTheInterpreterClaimIsExercised(unittest.TestCase):
    """"Python 3.11+" is a claim to contributors, and only 3.11 was ever run.

    `CONTRIBUTING.md` and `README.md` both say 3.11+. The CI matrix varied only
    the operating system and pinned `python-version: "3.11"` on both runners,
    so 3.12 and 3.13 -- increasingly the default on a fresh machine -- were
    advertised and never checked.

    The frozen Windows build pins its own interpreter, so a shipped installer
    is unaffected. What this is about is **running from source**, which the
    README documents as a first-class way to use the app, against a suite that
    heavily exercises PySide6 and PyMuPDF.

    Parsed by hand rather than with PyYAML, which this project does not depend
    on -- and read with comments stripped, because the comment explaining this
    defect necessarily names the versions the check is hunting for.
    """

    def _workflow(self, name):
        with open(os.path.join(HERE, ".github", "workflows", name),
                  encoding="utf-8") as fh:
            return "\n".join(ln for ln in fh.read().splitlines()
                              if not ln.lstrip().startswith("#"))

    def _declared_minimum(self):
        """The lowest version the documentation promises."""
        import re
        found = set()
        for doc in ("CONTRIBUTING.md", "README.md"):
            with open(os.path.join(HERE, doc), encoding="utf-8") as fh:
                found |= set(re.findall(r"Python \*{0,2}(\d+\.\d+)\+", fh.read()))
        self.assertTrue(found, "no document states a Python version any more")
        self.assertEqual(len(found), 1,
                         f"the documents promise different minimums: {found}")
        return next(iter(found))

    def test_the_test_matrix_covers_the_version_the_docs_promise(self):
        import re
        text = self._workflow("tests.yml")
        m = re.search(r"python-version:\s*\[([^\]]+)\]", text)
        self.assertIsNotNone(
            m, "tests.yml no longer varies python-version; the docs promise a "
               "range and a single pin cannot check one")
        versions = re.findall(r"\d+\.\d+", m.group(1))
        self.assertIn(self._declared_minimum(), versions,
                      "the matrix does not include the minimum the docs promise")
        self.assertGreater(
            len(versions), 1,
            "the matrix names one version, so '3.11+' is still unchecked above "
            "the floor")

    def test_the_frozen_build_stays_pinned_and_says_why(self):
        """The asymmetry is deliberate; without the reason somebody 'fixes' it."""
        import re
        raw = open(os.path.join(HERE, ".github", "workflows",
                                "build-windows.yml"), encoding="utf-8").read()
        text = self._workflow("build-windows.yml")
        self.assertRegex(text, r'python-version:\s*"\d+\.\d+"',
                         "the Windows build no longer pins one interpreter")
        self.assertIn("not vary run to run", raw,
                      "the pin carries no stated reason, so it reads as the "
                      "oversight the test matrix just corrected")

    def test_no_workflow_pins_a_deprecated_node20_action(self):
        """GitHub is force-running these on Node 24; the forcing is temporary.

        When it ends, a workflow pinned to these majors stops working -- and for
        this repository that is the Windows build, the only path that produces
        the installer.
        """
        import glob
        import re
        stale = {"actions/checkout@v4", "actions/setup-python@v5",
                 "actions/upload-artifact@v4"}
        offenders = []
        for path in sorted(glob.glob(
                os.path.join(HERE, ".github", "workflows", "*.yml"))):
            name = os.path.basename(path)
            for i, line in enumerate(self._workflow(name).splitlines(), 1):
                for ref in re.findall(r"uses:\s*(\S+)", line):
                    if ref in stale:
                        offenders.append(f"{name}: {ref}")
        self.assertEqual(
            offenders, [], "a Node-20 action major is pinned: " + str(offenders))


if __name__ == "__main__":
    unittest.main()
