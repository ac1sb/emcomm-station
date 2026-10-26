"""Check emcomm-mesh-check finds the Meshtastic radio's port without ever picking the
radio's CAT or PTT port or the GPS, explains the radio's GPS and position, and puts
Meshtastic's own command line on the mesh radio's port.

Run: python3 tests/test_mesh_check.py
"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/diagnostics/files/emcomm-mesh-check")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_mesh_check", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_mesh_check", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


mc = load_helper()

NOW = 1793030000
RADIO = {
    "my": {"user": {"id": "!a1b2c3d4", "longName": "AC1SB base", "shortName": "SB1"},
           "position": {"latitude": 43.16, "longitude": -73.07, "altitude": 270, "time": NOW - 600,
                        "locationSource": "LOC_INTERNAL", "satsInView": 9}},
    "metadata": {"firmwareVersion": "2.5.6.d55c08d", "hwModel": "HELTEC_V3"},
    "config": {"device": {}, "position": {"gpsMode": "ENABLED", "positionBroadcastSmartEnabled": True},
               "lora": {"region": "US", "modemPreset": "LONG_FAST"}},
    "nodes": 12, "nodes_with_position": 5,
}


def radio(**changes):
    data = json.loads(json.dumps(RADIO))
    for path, value in changes.items():
        where = data
        keys = path.split("__")
        for key in keys[:-1]:
            where = where[key]
        if value is None:
            where.pop(keys[-1], None)
        else:
            where[keys[-1]] = value
    return data


class Ports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.by_id = os.path.join(root, "by-id")
        os.makedirs(self.by_id)
        self.devs = {}
        for name in ("ttyUSB0", "ttyUSB1", "ttyACM0"):
            open(os.path.join(root, name), "w").close()
        for link, dev in (("usb-Silicon_Labs_CP2102N_FT-710-if00", "ttyUSB0"),
                          ("usb-Digirig-if00", "ttyUSB1"), ("usb-Espressif_heltec-if00", "ttyACM0")):
            os.symlink(os.path.join(root, dev), os.path.join(self.by_id, link))
        os.symlink(os.path.join(root, "ttyUSB0"), os.path.join(root, "rig-cat"))
        os.symlink(os.path.join(root, "ttyUSB1"), os.path.join(root, "rig-ptt"))
        self.saved = (mc.SERIAL_DIR, mc.RADIO_PORTS, mc.CONFIG)
        mc.SERIAL_DIR = self.by_id
        mc.RADIO_PORTS = (os.path.join(root, "rig-cat"), os.path.join(root, "rig-ptt"), os.path.join(root, "gps0"))
        os.makedirs(os.path.join(root, "config"))
        mc.CONFIG = os.path.join(root, "config", "mesh-{}.json")
        self.mesh = os.path.join(self.by_id, "usb-Espressif_heltec-if00")

    def tearDown(self):
        mc.SERIAL_DIR, mc.RADIO_PORTS, mc.CONFIG = self.saved
        self.tmp.cleanup()

    def test_only_other_port_is_picked(self):
        self.assertEqual(mc.pick_port(), (self.mesh, None))

    def test_radio_ports_never_picked(self):
        port, why = mc.pick_port(os.path.join(self.by_id, "usb-Digirig-if00"))
        self.assertIsNone(port)
        self.assertIn("CAT or PTT", why)
        os.remove(self.mesh)
        port, why = mc.pick_port()
        self.assertIsNone(port)
        self.assertIn("No USB serial port", why)

    def test_two_candidates_asks_for_port(self):
        open(os.path.join(self.tmp.name, "ttyACM1"), "w").close()
        os.symlink(os.path.join(self.tmp.name, "ttyACM1"), os.path.join(self.by_id, "usb-RAK4631-if00"))
        port, why = mc.pick_port()
        self.assertIsNone(port)
        self.assertIn("--port", why)
        self.assertIn("RAK4631", why)
        self.assertNotIn("Digirig", why)

    def test_saved_port_wins(self):
        open(os.path.join(self.tmp.name, "ttyACM1"), "w").close()
        other = os.path.join(self.by_id, "usb-RAK4631-if00")
        os.symlink(os.path.join(self.tmp.name, "ttyACM1"), other)
        with open(mc.CONFIG.format("meshtastic"), "w") as f:
            json.dump({"via": "usb", "address": other}, f)
        self.assertEqual(mc.pick_port(), (other, None))
        with open(mc.CONFIG.format("gps"), "w") as f:  # Settings > Devices comes first
            json.dump({"port": self.mesh}, f)
        self.assertEqual(mc.pick_port(), (self.mesh, None))

    def test_bluetooth_tile_isnt_a_port(self):
        with open(mc.CONFIG.format("meshtastic"), "w") as f:
            json.dump({"via": "ble", "address": "AA:BB:CC:DD:EE:FF"}, f)
        self.assertEqual(mc.pick_port(), (self.mesh, None))

    def test_meshtastic_gets_the_mesh_port(self):
        ran = []
        saved = (mc.os.execv, mc.in_use, mc.VENV)
        mc.os.execv = lambda prog, argv: ran.append(argv)
        mc.in_use = lambda: None
        mc.VENV = self.tmp.name
        os.makedirs(os.path.join(self.tmp.name, "bin"))
        open(os.path.join(self.tmp.name, "bin", "meshtastic"), "w").close()
        try:
            mc.meshtastic(["--info"])
            mc.meshtastic(["--help"])
            mc.meshtastic(["--host", "192.168.1.5", "--info"])
            mc.meshtastic(["--port", "--info"])  # meshtastic's own search would try the radio's ports
            mc.meshtastic(["--nodes", "-s", self.mesh])
            self.assertEqual(mc.meshtastic(["--port", os.path.join(self.by_id, "usb-Digirig-if00"), "--info"]), 1)
            self.assertEqual(mc.meshtastic([f"--serial={os.path.join(self.by_id, 'usb-Digirig-if00')}", "--info"]), 1)
            mc.in_use = lambda: "the Mesh text tile"
            self.assertEqual(mc.meshtastic(["--nodes"]), 1)
        finally:
            mc.os.execv, mc.in_use, mc.VENV = saved
        self.assertEqual([argv[1:] for argv in ran],
                         [["--port", self.mesh, "--info"], ["--help"], ["--host", "192.168.1.5", "--info"],
                          ["--port", self.mesh, "--info"], ["--port", self.mesh, "--nodes"]])


class Summary(unittest.TestCase):
    def text(self, data):
        return "\n".join(mc.summarize(data, "/dev/ttyACM0", now=NOW))

    def test_good_fix(self):
        out = self.text(RADIO)
        self.assertIn("AC1SB base (SB1) !a1b2c3d4", out)
        self.assertIn("HELTEC_V3, firmware 2.5.6", out)
        self.assertIn("Region:    US, role CLIENT", out)
        self.assertIn("GPS:       on, checks every 120 s, sends its position every 900 s, smart position on", out)
        self.assertIn("43.16000, -73.07000, 270 m; fixed", out)
        self.assertIn("(10 min ago), 9 satellites", out)
        self.assertIn("12 heard, 5 with a position", out)
        self.assertNotIn("What to do", out)

    def test_gps_off(self):
        out = self.text(radio(config__position__gpsMode=None, my__position={}))
        self.assertIn("GPS:       switched off", out)
        self.assertIn("gps_mode ENABLED", out)
        self.assertNotIn("No GPS fix yet", out)  # turning it on comes first

    def test_older_firmware_gps_enabled(self):
        self.assertEqual(mc.gps_state({"gpsEnabled": True}), "on")
        self.assertEqual(mc.gps_state({}), "off")
        self.assertEqual(mc.gps_state({"gpsMode": "NOT_PRESENT"}), "none")

    def test_no_fix_yet(self):
        out = self.text(radio(my__position={"latitude": 0, "longitude": 0}))
        self.assertIn("Position:  none", out)
        self.assertIn("No GPS fix yet", out)

    def test_fixed_position(self):
        out = self.text(radio(config__position__fixedPosition=True, my__position__locationSource="LOC_MANUAL"))
        self.assertIn("Fixed position: on", out)
        self.assertIn("typed in, not from the GPS", out)
        self.assertIn("--remove-position", out)

    def test_region_unset_and_stale_fix(self):
        out = self.text(radio(config__lora={}, my__position__time=NOW - 3 * 3600))
        self.assertIn("Region:    UNSET", out)
        self.assertIn("won't transmit", out)
        self.assertIn("over an hour old", out)

    def test_no_gps_fitted(self):
        out = self.text(radio(config__position__gpsMode="NOT_PRESENT", my__position={}))
        self.assertIn("none fitted", out)
        self.assertIn("u-blox", out)

    def test_error(self):
        out = self.text({"error": "Timed out waiting for connection completion"})
        self.assertIn("No answer: Timed out", out)

    def test_times_are_utc(self):
        self.assertEqual(mc.utc(0), "1970-01-01 00:00Z")
        self.assertEqual(mc.ago(90 * 60), "1 h 30 min ago")
        self.assertTrue(time.gmtime(NOW))


if __name__ == "__main__":
    unittest.main()
