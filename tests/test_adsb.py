"""Check the ADS-B helper picks its dongle, turns dump1090's output into what the map
shows, and that the weather radio listener and the Scanner leave that dongle alone.

Run: python3 tests/test_adsb.py
"""

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tests"))


def load(path, name):
    loader = importlib.machinery.SourceFileLoader(name, os.path.join(REPO, path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


adsb = load("roles/radio/files/emcomm-adsb", "emcomm_adsb")
nwr = load("roles/radio/files/emcomm-nwr", "emcomm_nwr")

THREE = [{"index": 0, "serial": "00000001", "name": "Realtek RTL2838UHIDIR"},
         {"index": 1, "serial": "00000001", "name": "Realtek RTL2838UHIDIR"},
         {"index": 2, "serial": "SN4471", "name": "RTL-SDR Blog V4"}]


class Picking(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = adsb.CONFIG, adsb.SDR_LOCK
        adsb.CONFIG = os.path.join(self.tmp.name, "adsb.json")
        adsb.SDR_LOCK = os.path.join(self.tmp.name, "sdr.json")

    def tearDown(self):
        adsb.CONFIG, adsb.SDR_LOCK = self.old
        self.tmp.cleanup()

    def test_writing_the_mark_leaves_another_apps_lock_alone(self):
        with open(adsb.SDR_LOCK, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getppid(), "app": "Scanner"}, f)  # a process that is running
        real_which = adsb.shutil.which
        adsb.shutil.which = lambda _name: "/usr/bin/rtl_eeprom"
        try:
            self.assertIn("Scanner", adsb.write_mark(0))
        finally:
            adsb.shutil.which = real_which
        with open(adsb.SDR_LOCK, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["app"], "Scanner")
        with open(adsb.SDR_LOCK, "w", encoding="utf-8") as f:
            json.dump({"pid": 2 ** 22 - 1, "app": "Scanner"}, f)  # one that has gone
        self.assertIsNone(adsb.lock_holder())

    def test_default_is_the_usual_adsb_serial(self):
        self.assertEqual(adsb.adsb_serial(), "00001090")
        self.assertIsNone(adsb.adsb_dongle(THREE, adsb.adsb_serial()))
        marked = THREE + [{"index": 3, "serial": "00001090", "name": "FlightAware Pro Stick"}]
        self.assertEqual(adsb.adsb_dongle(marked, adsb.adsb_serial())["index"], 3)

    def test_a_dongle_with_its_own_serial_is_saved_as_is(self):
        text = adsb.use(2, THREE, write_serial=lambda _i: self.fail("nothing to write"))
        self.assertIn("SN4471", text)
        self.assertEqual(adsb.adsb_serial(), "SN4471")

    def test_a_dongle_sharing_its_serial_gets_the_adsb_one(self):
        written = []
        text = adsb.use(1, THREE, write_serial=lambda i: written.append(i))
        self.assertEqual(written, [1])
        self.assertIn("Unplug it", text)
        self.assertEqual(adsb.adsb_serial(), "00001090")

    def test_a_failed_write_changes_nothing(self):
        text = adsb.use(0, THREE, write_serial=lambda _i: "Couldn't write to the dongle.")
        self.assertEqual(text, "Couldn't write to the dongle.")
        self.assertFalse(os.path.exists(adsb.CONFIG))

    def test_off(self):
        adsb.save_config({"off": True})
        self.assertIsNone(adsb.adsb_serial())


class Aircraft(unittest.TestCase):
    def test_old_and_new_field_names(self):
        data = {"now": 1, "aircraft": [
            {"hex": "a1b2c3", "flight": "N123AB  ", "lat": 43.1, "lon": -73.0, "altitude": 4500, "speed": 120,
             "track": 90, "squawk": "1200", "seen_pos": 3},
            {"hex": "~c0ffee", "lat": 42.9, "lon": -73.2, "alt_baro": "ground", "gs": 10, "seen_pos": 1},
            {"hex": "abcdef", "flight": "NOPOS", "altitude": 30000},  # no position yet
            {"hex": "ac0001", "lat": 43.5, "lon": -72.5, "altitude": 9000, "seen_pos": 300},  # lost
            {"hex": "ac0002", "lat": 43.6, "lon": -72.6, "altitude": 7000, "squawk": "7700", "seen_pos": 0.5}]}
        shown = {a["hex"]: a for a in adsb.aircraft(data)}
        self.assertEqual(set(shown), {"a1b2c3", "c0ffee", "ac0002"})
        self.assertEqual((shown["a1b2c3"]["flight"], shown["a1b2c3"]["alt"], shown["a1b2c3"]["speed"]),
                         ("N123AB", 4500, 120))
        self.assertEqual(shown["c0ffee"]["alt"], "ground")
        self.assertEqual(shown["ac0002"]["emergency"], "Emergency")

    def test_the_map_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = adsb.OUT
            adsb.OUT = tmp
            try:
                adsb.write_js("running", "", [{"hex": "a1b2c3"}])
            finally:
                adsb.OUT = old
            with open(os.path.join(tmp, "aircraft.js")) as f:
                text = f.read()
        self.assertTrue(text.startswith("window.AIRCRAFT = "))
        data = json.loads(text[len("window.AIRCRAFT = "):].rstrip().rstrip(";"))
        self.assertEqual((data["state"], data["aircraft"][0]["hex"]), ("running", "a1b2c3"))

    def test_decoder_gets_the_station_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            station = os.path.join(tmp, "station.json")
            with open(station, "w") as f:
                json.dump({"grid": "FN33"}, f)
            old = adsb.STATION_PATH
            adsb.STATION_PATH = station
            try:
                command = adsb.decoder_command(2)
            finally:
                adsb.STATION_PATH = old
        self.assertEqual(command[:3], ["dump1090-mutability", "--device-index", "2"])
        self.assertNotIn("--net", command)  # no network ports
        self.assertEqual(command[command.index("--lat") + 1], "43.5")


class OthersLeaveItAlone(unittest.TestCase):
    def test_weather_radio_takes_the_first_other_dongle(self):
        self.assertEqual(nwr.weather_dongle(["00001090", "00000001"], "00001090"), 1)
        self.assertEqual(nwr.weather_dongle(["00000001", "00001090"], "00001090"), 0)
        self.assertEqual(nwr.weather_dongle(["00001090", "00000001"], None), 0)
        self.assertIsNone(nwr.weather_dongle(["00001090"], "00001090"))
        self.assertEqual(nwr.weather_dongle([], "00001090"), 0)  # no library: rtl_fm finds out

    def test_scanner_skips_the_adsb_dongle(self):
        import types
        devices = [{"driver": "rtlsdr", "label": "Generic RTL2832U OEM :: 00001090", "serial": "00001090"},
                   {"driver": "rtlsdr", "label": "Generic RTL2832U OEM :: 00000001", "serial": "00000001"},
                   {"driver": "rtlsdr", "label": "RTL-SDR Blog V4 :: 00000002", "serial": "00000002"}]
        fake = types.SimpleNamespace(
            Device=types.SimpleNamespace(enumerate=lambda q: [d for d in devices if d["driver"] == q.split("=")[1]]),
            SOAPY_SDR_RX=0, SOAPY_SDR_CRITICAL=0, setLogLevel=lambda _l: None)
        sys.modules["SoapySDR"] = fake
        try:
            sc = load("roles/apps/files/emcomm-scanner", "emcomm_scanner_adsb")
            with tempfile.TemporaryDirectory() as tmp:
                sc.ADSB_CONFIG = os.path.join(tmp, "adsb.json")
                rxs = sc.receivers()
                self.assertEqual([rx["rtl_index"] for rx in rxs], [1, 2])  # numbered as librtlsdr does
                self.assertEqual([rx["nwr"] for rx in rxs], [True, False])
                self.assertEqual(sc.pick_receiver("", rxs, nwr=True)["rtl_index"], 2)
                with open(sc.ADSB_CONFIG, "w") as f:
                    json.dump({"off": True}, f)
                self.assertEqual([rx["rtl_index"] for rx in sc.receivers()], [0, 1, 2])
        finally:
            del sys.modules["SoapySDR"]


if __name__ == "__main__":
    unittest.main()
