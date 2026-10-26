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


def fake_dmr_csv(path):
    """A small RadioID user.csv: two IDs for one US call (listed out of order), one for a
    call the FCC list has, a Canadian, and a row with no ID."""
    rows = ["RADIO_ID,CALLSIGN,FIRST_NAME,LAST_NAME,CITY,STATE,COUNTRY",
            "3112346,KC1ABC,John,Smith,Manchester Center,Vermont,United States",
            "3112345,KC1ABC,John,Smith,Manchester Center,Vermont,United States",
            "3100001,W1AW,Arrl,,Newington,Connecticut,United States",
            "3021234,VE2ABC,Marie,Tremblay,Montreal,Quebec,Canada",
            ",N0ID,No,Id,,,"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(rows) + "\r\n")


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


class BuildDmr(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.csv = os.path.join(self.tmp.name, "user.csv")
        self.db = os.path.join(self.tmp.name, "lib/dmrids.db")
        fake_dmr_csv(self.csv)

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_and_look_up_by_call_and_id(self):
        self.assertEqual(cs.build_dmr(self.csv, self.db), 4)
        self.assertEqual([d["id"] for d in cs.dmr_lookup("kc1abc", self.db)], [3112345, 3112346])
        ve = cs.dmr_lookup("3021234", self.db)
        self.assertEqual([(d["call"], d["name"], d["city"], d["country"]) for d in ve],
                         [("VE2ABC", "Marie Tremblay", "Montreal", "Canada")])
        self.assertEqual(cs.dmr_lookup("N0ID", self.db), [])
        self.assertEqual(os.listdir(os.path.dirname(self.db)), ["dmrids.db"])

    def test_columns_found_by_name(self):
        with open(self.csv, "w", encoding="utf-8") as f:
            f.write("callsign,radio_id,country\nKC1ABC,3112345,United States\n")
        cs.build_dmr(self.csv, self.db)
        self.assertEqual(cs.dmr_lookup("3112345", self.db)[0]["call"], "KC1ABC")

    def test_not_radioid_csv(self):
        with open(self.csv, "w", encoding="utf-8") as f:
            f.write("a,b\n1,2\n")
        with self.assertRaises(ValueError):
            cs.build_dmr(self.csv, self.db)
        self.assertFalse(os.path.exists(self.db))

    def test_no_list(self):
        self.assertEqual(cs.dmr_lookup("KC1ABC", self.db), [])


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

    def test_dmr_update_downloads_builds_and_keeps_old_list_offline(self):
        csv_path = os.path.join(self.tmp.name, "user.csv")
        fake_dmr_csv(csv_path)
        dmr_db = os.path.join(self.tmp.name, "dmrids.db")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            first = cs.update_dmr(db_path=dmr_db, url="file://" + csv_path, cache=self.cache)
            again = cs.update_dmr(db_path=dmr_db, url="file:///nowhere.csv", cache=self.cache, max_age_days=0)
            missing = cs.update_dmr(db_path=os.path.join(self.tmp.name, "none.db"), url="file:///nowhere.csv",
                                    cache=self.cache)
        self.assertEqual((first, again, missing), (0, 0, 1))
        self.assertIn("DMR ID list rebuilt: 4 IDs", out.getvalue())
        self.assertIn("Keeping the list from", out.getvalue())
        self.assertEqual(os.listdir(self.cache), [])
        self.assertEqual(len(cs.dmr_lookup("KC1ABC", dmr_db)), 2)

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
        csv_path = os.path.join(cls.tmp.name, "user.csv")
        fake_dmr_csv(csv_path)
        cls.dmr = os.path.join(cls.tmp.name, "dmrids.db")
        cs.build_dmr(csv_path, cls.dmr)

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

    def test_summaries_with_dmr_ids(self):
        s = self.L.callsign_summary
        self.assertEqual(s("KC1ABC", self.db, self.dmr),
                         ("KC1ABC · John Q Smith · Manchester Center, VT · Amateur Extra · DMR 3112345, 3112346",
                          False))
        self.assertEqual(s("VE2ABC", self.db, self.dmr),
                         ("VE2ABC · Marie Tremblay · Montreal, Quebec, Canada · DMR 3021234", False))
        self.assertEqual(s("K1OLD", self.db, self.dmr)[1], True)
        self.assertEqual(self.L.dmr_ids_text([{"id": n} for n in (1, 2, 3, 4)]), "DMR 1, 2 +2 more")

    def test_look_up_box(self):
        search = self.L.lookup_search
        calls = [c for c, _line, _p in search("k", db=self.db, dmr_db=self.dmr)]
        self.assertEqual(calls, ["K1OLD", "KC1ABC"])
        self.assertEqual([c for c, _l, _p in search("kc1abc", db=self.db, dmr_db=self.dmr)], ["KC1ABC"])
        self.assertEqual([c for c, _l, _p in search("ve", db=self.db, dmr_db=self.dmr)], ["VE2ABC"])
        by_id = search("311234", db=self.db, dmr_db=self.dmr)
        self.assertEqual([line.split(" · ")[0] for _c, line, _p in by_id], ["DMR 3112345", "DMR 3112346"])
        self.assertTrue(by_id[0][1].startswith("DMR 3112345 · KC1ABC · John Q Smith"))
        self.assertEqual(search("3021234", db=self.db, dmr_db=self.dmr)[0][0], "VE2ABC")
        self.assertEqual(search("99", db=self.db, dmr_db=self.dmr), [])
        self.assertEqual(search("", db=self.db, dmr_db=self.dmr), [])

    def test_entry_message_names_who_checked_in(self):
        e = {"message": "Checked in", "name": "John Q Smith", "city": "Manchester Center", "state": "VT"}
        self.assertEqual(self.L.entry_message(e), "Checked in · John Q Smith, Manchester Center VT")
        self.assertEqual(self.L.entry_message({"message": "Net opened"}), "Net opened")
        ics = load(os.path.join(REPO, "roles/launcher/files/emcomm-ics"), "emcomm_ics")
        self.assertEqual(ics.entry_message(e), self.L.entry_message(e))


if __name__ == "__main__":
    unittest.main(verbosity=2 if "-v" in sys.argv else 1)
