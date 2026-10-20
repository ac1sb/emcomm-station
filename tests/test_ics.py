"""Check emcomm-ics fills in the ICS 309 and ICS 205 from a net log and My frequencies,
and the ICS 213 from an flmsg file.

Run: python3 tests/test_ics.py
"""

import contextlib
import importlib.machinery
import io
import importlib.util
import os
import tempfile
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


def flmsg_file(fields, wrap=False):
    body = "<flmsg>4.0.23\n:hdr_fm:21 AC1SB 20261020140500\n<ics213>\n"
    body += "".join(f":{k}:{len(v.encode())} {v}\n" for k, v in fields)
    if wrap:
        body = "[WRAP:beg][WRAP:lf][WRAP:fn x.213]" + body + "[WRAP:chksum 1A2B][WRAP:end]"
    return body.encode()


MESSAGE = [("inc", "Flood"), ("to", "J. Smith"), ("p1", "Logistics"), ("fm", "A. Brown"), ("p2", "Shelter"),
           ("d1", "2026-10-20"), ("t1", "1405"), ("sb", "Cots — 50"),
           ("mg", "Line one :to:3 abc\nLine two\n"), ("d2", "2026-10-20"), ("t2", "1520")]


class Form213(unittest.TestCase):
    def test_reads_fields_by_byte_length_even_when_text_looks_like_a_field(self):
        for wrap in (False, True):
            fields = ics.parse_flmsg(flmsg_file(MESSAGE, wrap))
            self.assertEqual(fields["mg"], "Line one :to:3 abc\nLine two\n")
            self.assertEqual(fields["to"], "J. Smith")
            self.assertEqual(fields["sb"], "Cots — 50")
            self.assertNotIn("hdr_fm", fields)

    def test_rejects_other_files(self):
        with self.assertRaises(ValueError):
            ics.parse_flmsg(b"<flmsg>4.0\n<ics214>\n:inc:1 x\n")

    def test_form_values(self):
        values = ics.form_values(ics.parse_flmsg(flmsg_file(MESSAGE)))
        self.assertEqual(values["2 To Name and Position"], "J. Smith, Logistics")
        self.assertEqual(values["3 From Name and Position"], "A. Brown, Shelter")
        self.assertEqual(values["DateTime_14"], "2026-10-20 1520")
        self.assertEqual(values["7 Message"], "Line one :to:3 abc\nLine two")
        self.assertNotIn("8 Approved by Name", values)

    def test_long_messages_get_smaller_text(self):
        self.assertEqual(ics.font_size("short", 530, 240), 10)
        self.assertLess(ics.font_size("word " * 900, 530, 240), 10)

    def test_fills_the_pdf(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf isn't installed")
        template = os.path.join(REPO, "roles/launcher/files/forms/ics213.pdf")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.pdf")
            with contextlib.redirect_stdout(io.StringIO()):
                ics.ics213_pdf(ics.parse_flmsg(flmsg_file(MESSAGE)), template, out)
            filled = {k: v.get("/V") for k, v in PdfReader(out).get_fields().items()}
        self.assertEqual(filled["4 Subject"], "Cots — 50")
        self.assertEqual(filled["2 To Name and Position"], "J. Smith, Logistics")
        self.assertFalse(filled.get("9 Reply"))


if __name__ == "__main__":
    unittest.main()
