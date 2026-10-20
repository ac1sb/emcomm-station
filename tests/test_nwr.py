"""Check emcomm-nwr reads SAME headers, keeps only the station's counties and
records weekly tests without raising an alert.

Run: python3 tests/test_nwr.py
"""

import calendar
import json
import importlib.machinery
import importlib.util
import os
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/radio/files/emcomm-nwr")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_nwr", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_nwr", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


nwr = load_helper()
NOW = calendar.timegm((2026, 10, 19, 22, 20, 0))  # day 292


class Same(unittest.TestCase):
    def test_header(self):
        h = nwr.parse_header("EAS: ZCZC-WXR-TOR-025017-125021+0030-2922215-KBOX/NWS-\n", NOW)
        self.assertEqual((h["event"], h["severity"], h["originator"]),
                         ("Tornado Warning", "Extreme", "National Weather Service"))
        self.assertEqual(h["places"], ["025017", "125021"])
        self.assertEqual(h["start"], calendar.timegm((2026, 10, 19, 22, 15, 0)))
        self.assertEqual(h["end"] - h["start"], 30 * 60)
        self.assertEqual(h["sender"], "KBOX/NWS")
        self.assertIsNone(nwr.parse_header("EAS: NNNN", NOW))
        self.assertIsNone(nwr.parse_header("EAS (part): ZCZC-WXR-TOR-0250", NOW))

    def test_new_year(self):
        h = nwr.parse_header("EAS: ZCZC-WXR-WSW-025017+0600-3652300-KBOX/NWS-",
                             calendar.timegm((2027, 1, 1, 0, 30, 0)))
        self.assertEqual(time.gmtime(h["start"]).tm_year, 2026)

    def test_counties(self):
        self.assertTrue(nwr.matches(["025017"], []))
        self.assertTrue(nwr.matches(["025017"], ["025017"]))
        self.assertTrue(nwr.matches(["325017"], ["025017"]))  # part of the county
        self.assertTrue(nwr.matches(["025017"], ["325017"]))
        self.assertFalse(nwr.matches(["125017"], ["325017"]))  # a different part
        self.assertTrue(nwr.matches(["025000"], ["025017"]))  # whole state
        self.assertTrue(nwr.matches(["000000"], ["025017"]))
        self.assertFalse(nwr.matches(["033011"], ["025017"]))

    def test_keep(self):
        record = {}
        tor = nwr.parse_header("EAS: ZCZC-WXR-TOR-025017+0030-2922215-KBOX/NWS-", NOW)
        self.assertEqual(nwr.keep(record, tor, ["025017"], 162.55, NOW)["sender"],
                         "NOAA Weather Radio 162.550 MHz")
        nwr.keep(record, tor, ["025017"], 162.55, NOW)  # heard again: not doubled
        self.assertEqual(len(record["data"]), 1)
        svr = nwr.parse_header("EAS: ZCZC-WXR-SVR-033011+0100-2922215-KGYX/NWS-", NOW)
        self.assertIsNone(nwr.keep(record, svr, ["025017"], 162.55, NOW))
        rwt = nwr.parse_header("EAS: ZCZC-WXR-RWT-025017+0015-2922200-KBOX/NWS-", NOW)
        self.assertIsNone(nwr.keep(record, rwt, ["025017"], 162.55, NOW))
        self.assertEqual(record["last_test"]["event"], "Required Weekly Test")
        later = NOW + 3600  # the tornado warning has ended by the next alert
        ffw = nwr.parse_header("EAS: ZCZC-WXR-FFW-025017+0300-2922320-KBOX/NWS-", later)
        nwr.keep(record, ffw, ["025017"], 162.55, later)
        self.assertEqual([a["code"] for a in record["data"]], ["FFW"])


class SharedDongle(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        nwr.SDR_LOCK = os.path.join(self.dir, "sdr.json")

    def claim(self, pid, app="Scanner"):
        with open(nwr.SDR_LOCK, "w", encoding="utf-8") as f:
            json.dump({"pid": pid, "app": app}, f)

    def test_running_app_holds_the_dongle(self):
        self.assertIsNone(nwr.sdr_claimed())
        self.claim(os.getpid())
        self.assertEqual(nwr.sdr_claimed(), "Scanner")

    def test_closed_app_lets_go(self):
        self.claim(2 ** 22 + 7)  # no such process
        self.assertIsNone(nwr.sdr_claimed())
        with open(nwr.SDR_LOCK, "w", encoding="utf-8") as f:
            f.write("not json")
        self.assertIsNone(nwr.sdr_claimed())


if __name__ == "__main__":
    unittest.main()
