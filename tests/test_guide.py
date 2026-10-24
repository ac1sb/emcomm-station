"""Check the operations guide: every link inside it lands on a heading, every picture
is there, and emcomm-guide turns it into a page with those pictures.

Run: python3 tests/test_guide.py (needs markdown: pip install markdown)
"""

import importlib.machinery
import importlib.util
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/launcher/files/emcomm-guide")
DOCS = os.path.join(REPO, "docs")
GUIDE = os.path.join(DOCS, "operations-guide.md")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_guide", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_guide", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


guide = load_helper()


class Guide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(GUIDE, encoding="utf-8") as f:
            cls.text = f.read()
        cls.page = guide.render(cls.text, guide.THEMES["dark"], guide_dir=DOCS)

    def test_links_land_on_headings(self):
        ids = set(re.findall(r'id="([^"]+)"', self.page))
        for target in re.findall(r"\]\(#([^)]+)\)", self.text):
            self.assertIn(target, ids, f"#{target} isn't a heading")

    def test_pictures_are_there(self):
        pictures = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", self.text)
        self.assertTrue(pictures)
        for path in pictures:
            self.assertTrue(path.startswith("guide/"), path)
            self.assertTrue(os.path.exists(os.path.join(DOCS, path)), path)
            self.assertIn(f'src="file://{DOCS}/{path}"', self.page)

    def test_no_links_out_of_the_installed_guide(self):
        # Only the guide and its pictures are installed, so a link to another repo file would break.
        for target in re.findall(r"\]\(([^)#][^)]*)\)", self.text):
            self.assertTrue(target.startswith(("https://", "guide/")), target)

    def test_every_theme_renders(self):
        for colours in guide.THEMES.values():
            self.assertIn("@media print", guide.render("# Title", colours))


if __name__ == "__main__":
    unittest.main()
