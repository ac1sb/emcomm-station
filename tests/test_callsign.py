"""Check emcomm-callsign builds the offline callsign database from the FCC's l_amat.zip
and looks calls up, and that the launcher shows and logs what it finds.

Run: python3 tests/test_callsign.py
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import sys
import tempfile
import time
import unittest
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/launcher/files/emcomm-callsign")


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


cs = load(HELPER, "emcomm_callsign")


def hd(usi, call, status, expires):
    return "|".join(["HD", str(usi), "", "", call, status, "HA", "01/01/2016", expires] + [""] * 50)


def en(usi, call, first="", mi="", last="", entity="", city="", state="", zipc=""):
    fields = ["EN", str(usi), "", "", call, "L", "", entity, first, mi, last, "", "", "", "", "1 Main St",
              city, state, zipc] + [""] * 10
    return "|".join(fields)


def am(usi, call, cls):
    return "|".join(["AM", str(usi), "", "", call, cls] + [""] * 12)


def fake_zip(path):
    """A small l_amat.zip: an active Extra, a club, a lapsed call, a reissued call whose
    old expired record must lose to its new active one, a cancelled call (left out), a
    stray short line, and Windows line ends as the FCC writes them."""
    rows = {
        "HD.dat": [hd(1, "KC1ABC", "A", "03/01/2034"), hd(2, "W1AW", "A", "11/30/2030"),
                   hd(3, "K1OLD", "E", "02/15/2025"), hd(4, "N1NEW", "E", "05/01/2010"),
                   hd(5, "N1NEW", "A", "06/01/2033"), hd(6, "K1GONE", "C", "01/01/2020"), "HD|7|broken"],
        "EN.dat": [en(1, "KC1ABC", "JOHN", "Q", "SMITH", city="MANCHESTER CENTER", state="VT", zipc="052550001"),
                   en(2, "W1AW", entity="ARRL INC", city="NEWINGTON", state="CT", zipc="06111"),
                   en(3, "K1OLD", "MARY", "", "JONES", city="DORSET", state="VT"),
                   en(4, "N1NEW", "OLD", "", "HOLDER", city="BOSTON", state="MA"),
                   en(5, "N1NEW", "NEW", "", "HOLDER", city="RUTLAND", state="VT"),
                   en(6, "K1GONE", "GONE", "", "AWAY", city="X", state="VT")],
        "AM.dat": [am(1, "KC1ABC", "E"), am(2, "W1AW", ""), am(3, "K1OLD", "T"), am(4, "N1NEW", "N"),
                   am(5, "N1NEW", "G")],
    }
    with zipfile.ZipFile(path, "w") as zf:
        for name, lines in rows.items():
            zf.writestr(name, "\r\n".join(lines) + "\r\n")


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zip = os.path.join(self.tmp.name, "l_amat.zip")
        self.db = os.path.join(self.tmp.name, "lib/callsigns.db")
        fake_zip(self.zip)

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_keeps_active_and_expired_only(self):
        self.assertEqual(cs.build(self.zip, self.db), 4)
        self.assertIsNone(cs.lookup("K1GONE", self.db))
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.db))], ["callsigns.db"])  # no temp left

    def test_lookup_fields(self):
        cs.build(self.zip, self.db)
        me = cs.lookup(" kc1abc ", self.db)
        self.assertEqual((me["name"], me["city"], me["state"], me["zip"], me["class"], me["status"], me["expires"]),
                         ("John Q Smith", "Manchester Center", "VT", "05255", "Amateur Extra", "active", "2034-03-01"))
        club = cs.lookup("W1AW", self.db)
        self.assertEqual((club["name"], club["class"]), ("ARRL INC", "Club"))
        self.assertEqual(cs.lookup("K1OLD", self.db)["status"], "expired")

    def test_reissued_call_takes_the_active_licence(self):
        cs.build(self.zip, self.db)
        new = cs.lookup("N1NEW", self.db)
        self.assertEqual((new["name"], new["city"], new["class"], new["status"]),
                         ("New Holder", "Rutland", "General", "active"))

    def test_not_the_fcc_file(self):
        bad = os.path.join(self.tmp.name, "other.zip")
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("readme.txt", "hi")
        with self.assertRaises(ValueError):
            cs.build(bad, self.db)
        self.assertFalse(os.path.exists(self.db))

    def test_lookup_without_database(self):
        self.assertIsNone(cs.lookup("KC1ABC", self.db))
        self.assertIsNone(cs.built(self.db))

    def test_us_calls(self):
        for call in ("KC1ABC", "W1AW", "K1A", "KA1ABC", "N1NEW", "AL7XX"):
            self.assertTrue(cs.is_us_call(call), call)
        for call in ("VE2ABC", "G4XYZ", "AM1A", "W1", "1AB"):
            self.assertFalse(cs.is_us_call(call), call)


class Update(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "callsigns.db")
        self.cache = os.path.join(self.tmp.name, "cache")
        self.src = os.path.join(self.tmp.name, "src.zip")
        fake_zip(self.src)
        self.url = "file://" + self.src

    def tearDown(self):
        self.tmp.cleanup()

    def run_update(self, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = cs.update(db_path=self.db, cache=self.cache, **kw)
        return rc, out.getvalue()

    def test_first_update_downloads_builds_and_removes_the_zip(self):
        rc, out = self.run_update(url=self.url)
        self.assertEqual(rc, 0)
        self.assertIn("rebuilt: 4 callsigns", out)
        self.assertEqual(os.listdir(self.cache), [])
        self.assertEqual(cs.lookup("KC1ABC", self.db)["state"], "VT")

    def test_fresh_list_is_left_alone(self):
        self.run_update(url=self.url)
        rc, out = self.run_update(url="file:///nowhere.zip")
        self.assertEqual(rc, 0)
        self.assertIn("not updating yet", out)

    def test_offline_keeps_the_old_list_and_says_so(self):
        self.run_update(url=self.url)
        rc, out = self.run_update(url="file:///nowhere.zip", max_age_days=0)
        self.assertEqual(rc, 0)
        self.assertIn("Keeping the list from", out)
        self.assertIsNotNone(cs.lookup("KC1ABC", self.db))

    def test_offline_with_no_list_fails(self):
        rc, out = self.run_update(url="file:///nowhere.zip")
        self.assertEqual(rc, 1)
        self.assertIn("needs one download with internet", out)


class Launcher(unittest.TestCase):
    """The launcher's own lookups (it reads the same database), loaded without a display."""

    @classmethod
    def setUpClass(cls):
        try:
            import gi  # noqa: F401
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401
        except (ImportError, ValueError):
            raise unittest.SkipTest("GTK's Python bindings aren't installed")
        cls.L = load(os.path.join(REPO, "roles/launcher/files/emcomm-launcher"), "emcomm_launcher")
        cls.tmp = tempfile.TemporaryDirectory()
        zip_path = os.path.join(cls.tmp.name, "l_amat.zip")
        fake_zip(zip_path)
        cls.db = os.path.join(cls.tmp.name, "callsigns.db")
        cs.build(zip_path, cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_summaries(self):
        s = self.L.callsign_summary
        self.assertEqual(s("kc1abc", self.db),
                         ("KC1ABC · John Q Smith · Manchester Center, VT · Amateur Extra", False))
        self.assertEqual(s("K1OLD", self.db),
                         ("K1OLD · Mary Jones · Dorset, VT · Technician · licence expired 2025-02-15", True))
        today = time.strftime("%Y-%m-%d", time.gmtime())
        self.assertEqual(s("K1ZZZ", self.db), (f"K1ZZZ isn't in the FCC list from {today}. Check the call.", False))
        self.assertEqual(s("VE2ABC", self.db), ("VE2ABC: not a US call, so not in the FCC list.", False))
        self.assertEqual(s("", self.db), ("", False))
        missing = os.path.join(self.tmp.name, "none.db")
        self.assertIn("run Update station once", s("KC1ABC", missing)[0])

    def test_entry_message_names_who_checked_in(self):
        e = {"message": "Checked in", "name": "John Q Smith", "city": "Manchester Center", "state": "VT"}
        self.assertEqual(self.L.entry_message(e), "Checked in · John Q Smith, Manchester Center VT")
        self.assertEqual(self.L.entry_message({"message": "Net opened"}), "Net opened")
        ics = load(os.path.join(REPO, "roles/launcher/files/emcomm-ics"), "emcomm_ics")
        self.assertEqual(ics.entry_message(e), self.L.entry_message(e))


if __name__ == "__main__":
    unittest.main(verbosity=2 if "-v" in sys.argv else 1)
