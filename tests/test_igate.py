"""Check the APRS iGate's Direwolf settings, passcode and status reading.

Run: python3 tests/test_igate.py
"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, os.path.join(REPO, path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


igate = load("roles/radio/files/emcomm-igate", "emcomm_igate")
STATION = {"callsign": "AC1SB", "grid": "FN33ed"}


class WithFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (igate.CONFIG, igate.CARD, igate.PTT)
        igate.CONFIG = os.path.join(self.tmp.name, "igate.json")
        igate.CARD = os.path.join(self.tmp.name, "aprsaudio")
        igate.PTT = os.path.join(self.tmp.name, "aprs-ptt")

    def tearDown(self):
        igate.CONFIG, igate.CARD, igate.PTT = self.saved
        self.tmp.cleanup()

    def set(self, **values):
        with open(igate.CONFIG, "w") as f:
            json.dump(values, f)
        return igate.settings()

    def plug(self, *paths):
        for path in paths:
            open(path, "w").close()


class Passcode(unittest.TestCase):
    def test_known_passcodes(self):
        self.assertEqual(igate.passcode("N0CALL"), 13023)
        self.assertEqual(igate.passcode("ac1sb-10"), igate.passcode("AC1SB"))


class Settings(WithFiles):
    def test_receive_only_never_keys_the_radio(self):
        conf = igate.direwolf_conf(self.set(mode="receive"), STATION, igate=True, ptt=True)
        self.assertIn("ADEVICE plughw:CARD=aprsaudio,DEV=0\n", conf)
        self.assertIn("MYCALL AC1SB-10\n", conf)
        self.assertNotIn("PTT ", conf)
        self.assertIn(f"IGLOGIN AC1SB-10 {igate.passcode('AC1SB')}\n", conf)
        self.assertIn("PBEACON sendto=IG ", conf)
        self.assertIn("overlay=R", conf)
        self.assertNotIn("IGTXVIA", conf)
        self.assertEqual(conf.count("PBEACON"), 1)
        # Not the Packet tile's ports.
        self.assertIn("AGWPORT 8010\nKISSPORT 0\nKISSPORT 8011\n", conf)

    def test_two_way_keys_and_beacons_on_the_air(self):
        conf = igate.direwolf_conf(self.set(mode="two-way", ssid=0, comment='Hi "there"'), STATION,
                                   igate=True, ptt=True)
        self.assertIn("MYCALL AC1SB\n", conf)
        self.assertIn(f"PTT {igate.PTT} RTS\n", conf)
        self.assertIn("IGTXVIA 0 WIDE1-1\n", conf)
        self.assertIn("PBEACON delay=2 every=30 via=WIDE1-1 ", conf)
        self.assertIn('comment="Hi there"', conf)
        self.assertIn("overlay=T", conf)

    def test_position_from_settings_or_grid(self):
        conf = igate.direwolf_conf(self.set(mode="receive", lat=43.1634, lon=-73.0721), STATION, True, False)
        self.assertIn("lat=43.1634 long=-73.0721", conf)
        conf = igate.direwolf_conf(self.set(mode="receive"), STATION, True, False)
        self.assertIn("lat=43.1458 long=-73.6250", conf)

    def test_aprs_tile_settings_have_no_igate(self):
        conf = igate.direwolf_conf(self.set(mode="off"), STATION, igate=False, ptt=True)
        self.assertIn(f"PTT {igate.PTT} RTS\n", conf)
        self.assertNotIn("IGSERVER", conf)
        self.assertNotIn("PBEACON", conf)

    def test_odd_settings_put_right(self):
        s = self.set(mode="sideways", ssid=99, server="evil host; rm", lat="north")
        self.assertEqual((s["mode"], s["ssid"], s["server"], s["lat"]), ("off", 15, "noam.aprs2.net", None))

    def test_what_stops_it(self):
        s = self.set(mode="two-way")
        self.assertIn("callsign", igate.blocker(s, {"callsign": "N0CALL"}))
        self.assertIn("sound card", igate.blocker(s, STATION))
        self.plug(igate.CARD)
        self.assertIn("PTT port", igate.blocker(s, STATION))
        self.plug(igate.PTT)
        self.assertIsNone(igate.blocker(s, STATION))
        self.assertIsNone(igate.blocker(self.set(mode="receive"), STATION))


class Counting(unittest.TestCase):
    def test_direwolf_output(self):
        c = igate.Counter()
        for line in ["Now connected to IGate server noam.aprs2.net (1.2.3.4)",
                     "[0.4] N1ABC-9>APDR16,WIDE1-1:=4310.12N/07305.33W>",
                     "[ig] N1ABC-9>APDR16,WIDE1-1,qAR,AC1SB-10:=4310.12N/07305.33W>",
                     "[ig] # aprsc 2.1.14 20 Oct 2026 23:59:00 GMT T2TEXAS",
                     "[ig>tx] W1AW>APRS,TCPIP*::N1ABC-9  :hello{1",
                     "[0] K1XYZ>APRS:>status"]:
            c.line(line)
        self.assertEqual((c.heard, c.igated, c.to_rf, c.connected), (2, 1, 1, True))
        self.assertIn("connected to APRS-IS: heard 2, sent 1 to APRS-IS, 1 sent on the air", c.summary("two-way"))
        c.line("Error reading from IGate server.  Closing connection.")
        self.assertFalse(c.connected)


if __name__ == "__main__":
    unittest.main()
