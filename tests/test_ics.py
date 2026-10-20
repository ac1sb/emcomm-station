"""Check emcomm-ics fills in the ICS 309 and ICS 205 from a net log and My frequencies.

Run: python3 tests/test_ics.py
"""

import importlib.machinery
import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/launcher/files/emcomm-ics")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_ics", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_ics", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ics = load_helper()

NET = {"name": "County ARES <2 m>", "incident": "Flood", "operator": "Pat", "callsign": "AC1SB",
       "started": 1760896800, "closed": 1760900400,
       "entries": [{"time": 1760897100, "from": "W1AW", "to": "AC1SB", "message": "Checked in", "checkin": True},
                   {"time": 1760896800, "from": "AC1SB", "to": "", "message": "Net opened on 146.520"}]}


class Forms(unittest.TestCase):
    def test_309_header_entries_in_time_order_and_escaped(self):
        page = ics.ics309(NET)
        self.assertIn("COMMUNICATIONS LOG (ICS 309)", page)
        self.assertIn("County ARES &lt;2 m&gt;", page)
        self.assertIn("Pat AC1SB", page)
        self.assertIn("From 2025-10-19 18:00Z to 2025-10-19 19:00Z", page)
        self.assertLess(page.index("Net opened"), page.index("Checked in"))
        self.assertIn("Page 1 of 1", page)

    def test_309_runs_onto_more_pages(self):
        net = dict(NET, entries=[{"time": NET["started"] + i, "from": "W1AW", "to": "", "message": str(i)}
                                 for i in range(ics.ROWS_309 + 1)])
        self.assertIn("Page 2 of 2", ics.ics309(net))

    def test_205_channels_from_my_frequencies(self):
        rows = [{"MHz": "146.940", "Mode": "FM", "Name": "W1XYZ rptr", "Note": "Command", "Offset": "-0.6",
                 "Tone": "100"},
                {"MHz": "3.873", "Mode": "LSB", "Name": "State net", "Note": "", "Offset": "", "Tone": ""},
                {"MHz": "", "Mode": "FM", "Name": "no frequency"}]
        channels = [c for c in map(ics.channel, rows) if c]
        self.assertEqual(len(channels), 2)
        self.assertEqual((channels[0]["rx"], channels[0]["tx"], channels[0]["tone"], channels[0]["wide"]),
                         ("146.9400", "146.3400", "100", "W"))
        self.assertEqual((channels[1]["tx"], channels[1]["wide"]), ("3.8730", ""))
        page = ics.ics205(rows, "Flood", "AC1SB", now=NET["started"])
        self.assertIn("INCIDENT RADIO COMMUNICATIONS PLAN (ICS 205)", page)
        self.assertEqual(page.count("<tr><td></td><td></td>"), ics.ROWS_205 - 2)


if __name__ == "__main__":
    unittest.main()
