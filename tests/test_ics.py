"""Check emcomm-ics fills in the ICS 309 and ICS 205 from a net log and My frequencies,
and the ICS 213 from an flmsg file.

Run: python3 tests/test_ics.py
"""

import contextlib
import importlib.machinery
import io
import importlib.util
import json
import os
import tempfile
import threading
import unittest
import xmlrpc.server

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

    def test_writes_files_flmsg_reads(self):
        fields = dict(MESSAGE)
        data = ics.write_flmsg(fields, "AC1SB", now=0)
        self.assertTrue(data.startswith(b"<flmsg>4.0.23\n:hdr_ed:21 \nAC1SB 19700101000000\n<ics213>\n"))
        self.assertEqual(ics.parse_flmsg(data), fields)
        self.assertIn(":sb:%d Cots \u2014 50\n" % len("Cots \u2014 50".encode()), data.decode())
        self.assertLess(data.index(b":inc:"), data.index(b":to:"))
        self.assertNotIn(b":rp:", data)  # empty fields are left out, as flmsg does

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


class Listing(unittest.TestCase):
    def test_messages_nets_and_forms_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent, nets, forms = (os.path.join(tmp, d) for d in ("sent", "nets", "forms"))
            for d in (sent, nets, forms):
                os.makedirs(d)
            with open(os.path.join(sent, "ICS213-1.213"), "wb") as f:
                f.write(ics.write_flmsg(dict(MESSAGE), "AC1SB", now=0))
            os.utime(os.path.join(sent, "ICS213-1.213"), (1000, 1000))
            with open(os.path.join(nets, "open.json"), "w", encoding="utf-8") as f:
                json.dump(dict(NET, closed=None), f)
            with open(os.path.join(nets, "closed.json"), "w", encoding="utf-8") as f:
                json.dump(NET, f)
            with open(os.path.join(nets, "bad.json"), "w", encoding="utf-8") as f:
                f.write("[")
            with open(os.path.join(forms, "ICS-309 2025-10-19 1800Z County ARES.html"), "w") as f:
                f.write("<html>")
            os.utime(os.path.join(forms, "ICS-309 2025-10-19 1800Z County ARES.html"), (2000, 2000))
            found = ics.list_forms([("Sent", sent)], nets, forms)
        self.assertEqual([m["kind"] for m in found], ["net", "net", "309", "213"])
        self.assertEqual(found[0]["title"], "County ARES <2 m>")
        self.assertIn("open since 18:00Z".replace(":", ""), found[0]["detail"])
        self.assertTrue(found[0]["open"] and not found[1]["open"])
        self.assertIn("1 checked in", found[1]["detail"])
        self.assertEqual(found[2]["detail"], "ICS-309 Communications Log · saved 1970-01-01 00:33Z")
        self.assertEqual((found[3]["title"], found[3]["detail"]), ("Cots — 50", "ICS-213 · Sent · to J. Smith · 2026-10-20 · 1405"))


class Sending(unittest.TestCase):
    def test_checksum_as_flmsg_works_it_out(self):
        self.assertEqual(ics.flmsg_crc16(b"123456789"), "4B37")  # CRC-16/MODBUS, for plain text
        self.assertEqual(ics.flmsg_crc16(b""), "FFFF")
        # A byte above 127 goes in as a negative char in flmsg's C++: the sign bits carry up.
        # When they're still there at the end, flmsg's sval() prints into char[5]: the first four digits.
        self.assertEqual(ics.flmsg_crc16("é".encode()), "{:04X}".format(ics_crc_reference("é".encode()))[:4])
        self.assertEqual(ics.flmsg_crc16("é\n".encode()), "{:04X}".format(ics_crc_reference("é\n".encode())))

    def test_wrapped_as_flmsg_autosend(self):
        text, wrapped = ics.wrap_for_fldigi("ICS213-x.213", b"<flmsg>4.0.23\n<ics213>\n:sb:2 hi\n")
        payload = b"[WRAP:fn ICS213-x.213]<flmsg>4.0.23\n<ics213>\n:sb:2 hi\n"
        self.assertEqual(wrapped, b"[WRAP:beg][WRAP:lf]" + payload + b"[WRAP:chksum "
                         + ics.flmsg_crc16(payload).encode() + b"][WRAP:end]")
        self.assertEqual(text, "\n\n\n... start\n" + wrapped.decode() + "\n... end\n\n\n")
        # Windows line endings are sent as line feeds, and the envelope says so.
        _text, wrapped = ics.wrap_for_fldigi("a.213", b"x\r\ny\r\n")
        self.assertTrue(wrapped.startswith(b"[WRAP:beg][WRAP:crlf][WRAP:fn a.213]x\ny\n[WRAP:chksum "))

    def test_sends_through_fldigi(self):
        calls = []
        server = xmlrpc.server.SimpleXMLRPCServer(("127.0.0.1", 0), logRequests=False)
        server.register_function(lambda: "4.2.06", "fldigi.version")
        server.register_function(lambda: calls and calls[-1][0] == "modem" and calls[-1][1] or "BPSK31",
                                 "modem.get_name")
        server.register_function(lambda: ["BPSK31", "MT63-2000L", "MFSK32", "CW"], "modem.get_names")
        server.register_function(lambda: "RX", "main.get_trx_state")
        server.register_function(lambda name: calls.append(("modem", name)) or 0, "modem.set_by_name")
        server.register_function(lambda text: calls.append(("queue", text)) or 0, "text.add_tx_queu")
        server.register_function(lambda: calls.append(("tx",)) or 0, "main.tx")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        real = ics.FLDIGI_URL, ics.WRAP_SEND_DIR, ics.SENT_LOG
        with tempfile.TemporaryDirectory() as tmp:
            ics.FLDIGI_URL = f"http://127.0.0.1:{server.server_address[1]}/"
            ics.WRAP_SEND_DIR, ics.SENT_LOG = os.path.join(tmp, "send"), os.path.join(tmp, "auto_sent.csv")
            path = os.path.join(tmp, "ICS213-x.213")
            with open(path, "wb") as f:
                f.write(ics.write_flmsg(dict(MESSAGE), "AC1SB", now=0))
            try:
                status = ics.fldigi_status(modems=True)
                self.assertEqual((status["online"], status["trx"], status["modems"][:2]), (True, "rx", ["MT63-2000L", "MFSK32"]))
                result = ics.send_to_fldigi(path, "MT63-2000L")
                self.assertEqual(result["modem"], "MT63-2000L")
                with open(result["wrap"], "rb") as f:
                    self.assertTrue(f.read().startswith(b"[WRAP:beg][WRAP:lf][WRAP:fn ICS213-x.213]<flmsg>"))
                with open(ics.SENT_LOG, encoding="utf-8") as f:
                    self.assertTrue(f.read().startswith("ICS213-x.213,"))  # as flmsg appends it, no header
            finally:
                ics.FLDIGI_URL, ics.WRAP_SEND_DIR, ics.SENT_LOG = real
                server.shutdown()
                server.server_close()
        self.assertEqual([c[0] for c in calls], ["modem", "queue", "tx"])
        self.assertTrue(calls[1][1].endswith("[WRAP:end]\n... end\n\n\n^r"))

    def test_no_fldigi(self):
        real = ics.FLDIGI_URL
        ics.FLDIGI_URL = "http://127.0.0.1:1/"
        try:
            self.assertEqual(ics.fldigi_status(), {"online": False})
        finally:
            ics.FLDIGI_URL = real


def ics_crc_reference(data):
    """flmsg's Ccrc16::update, bit for bit, with C's signed char and 32-bit unsigned int."""
    crc = 0xFFFF
    for byte in data:
        c = byte - 256 if byte > 127 else byte
        crc = (crc ^ c) & 0xFFFFFFFF
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xA001) if crc & 1 else (crc >> 1)
    return crc


if __name__ == "__main__":
    unittest.main()
