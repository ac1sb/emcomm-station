"""Check that every GTK program pins the Gdk version it needs before importing it.

Without the pin, PyGObject loads the newest Gdk it finds. On a computer that also
has GTK 4 installed that is Gdk 4.0, and Gtk 3.0 then fails to load, so the window
never opens.

Run: python3 tests/test_gi_versions.py
"""

import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES = os.path.join(REPO, "roles")
IMPORT = re.compile(r"^\s*from gi\.repository import (.+)$")
PIN = re.compile(r"""^\s*gi\.require_version\(["'](\w+)["']""")


def programs():
    for root, dirs, files in os.walk(ROLES):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            if "from gi.repository import" in text:
                yield path, text


class GiVersions(unittest.TestCase):
    def test_gdk_pinned_before_import(self):
        found = 0
        for path, text in programs():
            pinned = set()
            for number, line in enumerate(text.splitlines(), 1):
                match = PIN.match(line)
                if match:
                    pinned.add(match.group(1))
                    continue
                match = IMPORT.match(line)
                if not match:
                    continue
                names = {n.strip() for n in match.group(1).split("#")[0].split(",")}
                found += 1
                for needs in ("Gtk", "Gdk"):
                    with self.subTest(path=os.path.relpath(path, REPO), line=number, name=needs):
                        if needs in names:
                            self.assertIn(needs, pinned, f"{needs} imported without gi.require_version")
        self.assertGreater(found, 0)


if __name__ == "__main__":
    unittest.main()
