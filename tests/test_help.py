"""Tests for the user-manual vault and its markdown conversion."""

import unittest

from app.help import load_vault, vault_dir, to_markdown


class TestHelpVault(unittest.TestCase):
    def setUp(self):
        self.pages = load_vault(vault_dir())

    def test_vault_loads_home(self):
        self.assertTrue(self.pages, "docs vault should not be empty")
        self.assertIn("Home", self.pages)

    def test_no_dangling_wikilinks(self):
        dangling = [(n, l) for n, p in self.pages.items()
                    for l in p["links"] if l not in self.pages]
        self.assertEqual(dangling, [], f"dangling links: {dangling}")

    def test_links_and_tags_convert(self):
        md = to_markdown(self.pages["Home"]["raw"])
        self.assertIn("(vault:", md)   # a [[wikilink]] became an anchor
        self.assertIn("(tag:", md)     # a #tag became an anchor

    def test_code_examples_preserved(self):
        # literal `[[link]]`/`#tag` inside backticks must not be converted
        md = to_markdown(self.pages["Home"]["raw"])
        self.assertIn("`[[link]]`", md)

    def test_key_pages_present(self):
        for page in ("Wire Numbers", "Wire Export", "Settings", "Markup Tools",
                     "Comments Sidebar", "TODO", "Eraser"):
            self.assertIn(page, self.pages)


if __name__ == "__main__":
    unittest.main()
