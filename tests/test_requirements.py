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


if __name__ == "__main__":
    unittest.main()


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
