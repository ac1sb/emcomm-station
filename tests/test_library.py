"""Check emcomm-library finds books and picks the newest one on the Kiwix server.

Run: python3 tests/test_library.py
"""

import importlib.machinery
import importlib.util
import os
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/apps/files/emcomm-library")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_library", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_library", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


library = load_helper()

LISTING = """<a href="wikem_en_all_maxi_2024-05.zim">wikem_en_all_maxi_2024-05.zim</a> 2024-05-20 40M
<a href="wikem_en_all_maxi_2025-01.zim">wikem_en_all_maxi_2025-01.zim</a> 2025-01-10 41M
<a href="wikem_en_all_maxi_2025-01.zim.torrent">torrent</a>
<a href="wikem_en_all_nopic_2025-06.zim">wikem_en_all_nopic_2025-06.zim</a>"""


class Library(unittest.TestCase):
    def test_latest_file(self):
        self.assertEqual(library.latest_file(LISTING, "wikem_en_all_maxi"), "wikem_en_all_maxi_2025-01.zim")
        self.assertIsNone(library.latest_file(LISTING, "ifixit_en_all_maxi"))

    def test_book_name(self):
        self.assertEqual(library.book_name("zimgit-water_en_2024-08.zim"), "zimgit-water_en")
        self.assertEqual(library.book_name("my-notes.zim"), "my-notes")

    def test_find_books_on_station_and_stick(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as stick:
            os.makedirs(os.path.join(stick, "kiwix"))
            for path in (os.path.join(home, "wikem_en_all_maxi_2025-01.zim"),
                         os.path.join(stick, "wikem_en_all_maxi_2024-05.zim"),
                         os.path.join(stick, "kiwix", "wikipedia_en_all_nopic_2025-03.zim"),
                         os.path.join(home, "notes.txt")):
                open(path, "w").close()
            books = library.find_books([home, stick])
            self.assertEqual(sorted(books), ["wikem_en_all_maxi", "wikipedia_en_all_nopic"])
            self.assertTrue(books["wikem_en_all_maxi"].startswith(home))  # the newer copy


if __name__ == "__main__":
    unittest.main()
