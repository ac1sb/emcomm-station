"""Check emcomm-mesh-nodes reads node positions from Meshtastic and MeshCore, keeps
the last list when a radio can't be asked, and leaves a radio alone while its tile
has it; and that the station's own position comes from the Meshtastic radio picked
in Settings > Devices, never from a typed-in position or the radio's own ports.

Run: python3 tests/test_mesh_nodes.py
"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/apps/files/emcomm-mesh-nodes")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_mesh_nodes", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_mesh_nodes", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


mesh = load_helper()

MESHTASTIC = {
    "!a1b2c3d4": {"num": 1, "user": {"id": "!a1b2c3d4", "longName": "AC1SB base", "shortName": "SB1"},
                  "position": {"latitude": 43.16, "longitude": -73.07, "altitude": 270}, "lastHeard": 1760990000,
                  "snr": 6.5, "hopsAway": 0, "deviceMetrics": {"batteryLevel": 88}},
    "!0000beef": {"num": 2, "user": {"id": "!0000beef", "longName": "Dorset relay", "shortName": "DR"},
                  "position": {"latitude": 43.25, "longitude": -73.1}, "lastHeard": 1760980000, "hopsAway": 2},
    "!00000001": {"num": 3, "user": {"longName": "No GPS"}, "position": {}},
    "!00000002": {"num": 4, "user": {"longName": "Zero"}, "position": {"latitude": 0, "longitude": 0}},
}
MESHCORE = {
    "ab12": {"public_key": "ab12cd34ef56aa", "adv_name": "Equinox rpt", "type": 2, "adv_lat": 43.16,
             "adv_lon": -73.11, "last_advert": 1760985000, "out_path_len": 1},
    "cd34": {"public_key": "cd34", "adv_name": "No fix", "type": 1, "adv_lat": 0.0, "adv_lon": 0.0},
}


class Reading(unittest.TestCase):
    def test_meshtastic(self):
        nodes = {n["name"]: n for n in mesh.meshtastic_nodes(MESHTASTIC, my_num=1)}
        self.assertEqual(set(nodes), {"AC1SB base", "Dorset relay"})
        self.assertTrue(nodes["AC1SB base"]["me"])
        self.assertEqual((nodes["AC1SB base"]["battery"], nodes["Dorset relay"]["hops"]), (88, 2))

    def test_meshcore(self):
        nodes = mesh.meshcore_nodes(MESHCORE, me={"name": "AC1SB mc", "adv_lat": 43.2, "adv_lon": -73.0})
        self.assertEqual([(n["name"], n["kind"]) for n in nodes],
                         [("Equinox rpt", "Repeater"), ("AC1SB mc", "This radio")])


class Refreshing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = mesh.CONFIG, mesh.OUT, mesh.in_use
        mesh.CONFIG = os.path.join(self.tmp.name, "mesh-{}.json")
        mesh.OUT = os.path.join(self.tmp.name, "out")
        mesh.in_use = lambda kind: False
        with open(mesh.CONFIG.format("meshtastic"), "w") as f:
            json.dump({"via": "usb", "address": "/dev/serial/by-id/usb-node"}, f)

    def tearDown(self):
        mesh.CONFIG, mesh.OUT, mesh.in_use = self.old
        self.tmp.cleanup()

    def test_asks_the_radio_the_tile_used(self):
        asked = []
        saved = {}
        mesh.refresh("meshtastic", saved, run=lambda *a: asked.append(a) or {"nodes": [{"name": "x"}]})
        self.assertEqual(asked, [("meshtastic", "usb", "/dev/serial/by-id/usb-node")])
        self.assertEqual(saved["meshtastic"]["nodes"], [{"name": "x"}])
        mesh.refresh("meshcore", saved, run=lambda *a: self.fail("never connected"))
        self.assertNotIn("meshcore", saved)

    def test_keeps_the_last_list(self):
        saved = {"meshtastic": {"time": 5, "error": "", "nodes": [{"name": "old"}]}}
        mesh.refresh("meshtastic", saved, run=lambda *a: {"error": "No answer from the radio."})
        self.assertEqual((saved["meshtastic"]["nodes"], saved["meshtastic"]["error"]),
                         ([{"name": "old"}], "No answer from the radio."))
        mesh.in_use = lambda kind: True
        mesh.refresh("meshtastic", saved, run=lambda *a: self.fail("the tile has it"))
        self.assertIn("tile has the radio", saved["meshtastic"]["error"])

    def test_the_meshtastic_app_has_the_radio(self):
        class Done:
            stdout = "org.mozilla.firefox\norg.meshtastic.MeshtasticDesktop\n"
        real = mesh.subprocess.run
        mesh.subprocess.run = lambda *a, **k: Done()
        try:
            self.assertTrue(mesh.flatpak_running("org.meshtastic.MeshtasticDesktop"))
            self.assertTrue(self.old[2]("meshtastic"))
            Done.stdout = "org.mozilla.firefox\n"
            self.assertFalse(mesh.flatpak_running("org.meshtastic.MeshtasticDesktop"))
        finally:
            mesh.subprocess.run = real

        def missing(*a, **k):
            raise FileNotFoundError("flatpak")
        mesh.subprocess.run = missing
        try:
            self.assertFalse(mesh.flatpak_running("org.meshtastic.MeshtasticDesktop"))
        finally:
            mesh.subprocess.run = real

    def test_the_map_gets_a_script(self):
        mesh.save({"meshtastic": {"nodes": []}})
        with open(os.path.join(mesh.OUT, "nodes.js")) as f:
            self.assertTrue(f.read().startswith("window.MESHNODES = {"))


class StationPosition(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = mesh.CONFIG, mesh.GPS_CONFIG, mesh.OUT, mesh.in_use, mesh.RADIO_PORTS
        mesh.CONFIG = os.path.join(self.tmp.name, "mesh-{}.json")
        mesh.GPS_CONFIG = mesh.CONFIG.format("gps")
        mesh.OUT = os.path.join(self.tmp.name, "out")
        mesh.in_use = lambda kind: False
        self.port = os.path.join(self.tmp.name, "usb-RAKwireless_WisCore")
        self.cat = os.path.join(self.tmp.name, "rig-cat")
        open(self.port, "w").close()
        mesh.RADIO_PORTS = (self.cat,)
        with open(mesh.GPS_CONFIG, "w") as f:
            json.dump({"port": self.port}, f)
        self.asked = []

    def tearDown(self):
        mesh.CONFIG, mesh.GPS_CONFIG, mesh.OUT, mesh.in_use, mesh.RADIO_PORTS = self.old
        self.tmp.cleanup()

    def answer(self, *args):
        self.asked.append(args)
        return {"nodes": [{"name": "AC1SB base"}],
                "mine": mesh.own_position(MESHTASTIC_FIX, 1, "on")}

    def test_own_position(self):
        mine = mesh.own_position(MESHTASTIC_FIX, 1, "on")
        self.assertEqual((mine["lat"], mine["lon"], mine["fix_time"], mine["gps"]), (43.16, -73.07, 1760990000, "on"))
        typed = {"a": {"num": 1, "position": dict(MESHTASTIC_FIX["a"]["position"], locationSource="LOC_MANUAL")}}
        self.assertIsNone(mesh.own_position(typed, 1)["lat"])
        self.assertIsNone(mesh.own_position(MESHTASTIC, 3, "none")["lat"])
        self.assertIsNone(mesh.own_position(MESHTASTIC_FIX, None)["lat"])

    def test_asks_then_waits(self):
        entry = mesh.position(run=self.answer)
        self.assertEqual((entry["lat"], entry["port"], entry["error"]), (43.16, self.port, ""))
        self.assertEqual(self.asked, [("meshtastic", "usb", self.port)])
        self.assertEqual(mesh.load()["meshtastic"]["nodes"], [{"name": "AC1SB base"}])  # the map's list too
        mesh.position(run=self.answer)
        self.assertEqual(len(self.asked), 1)  # asked lately
        mesh.position(now=True, run=self.answer)
        self.assertEqual(len(self.asked), 2)

    def test_keeps_the_last_fix(self):
        mesh.position(run=self.answer)
        entry = mesh.position(now=True, run=lambda *a: {"error": "No answer from the radio."})
        self.assertEqual((entry["lat"], entry["error"]), (43.16, "No answer from the radio."))
        mesh.in_use = lambda kind: True
        entry = mesh.position(now=True, run=lambda *a: self.fail("the app has the radio"))
        self.assertIn("app has the radio", entry["error"])
        os.remove(self.port)
        self.assertIn("isn't plugged in", mesh.position(now=True, run=self.answer)["error"])

    def test_never_opens_the_radios_port(self):
        os.symlink(self.port, self.cat)
        entry = mesh.position(now=True, run=lambda *a: self.fail("opened the CAT port"))
        self.assertIn("radio's", entry["error"])
        self.assertIn("radio's", mesh.refresh("meshtastic", {}, run=lambda *a: self.fail("opened it"))["error"])

    def test_off(self):
        os.remove(mesh.GPS_CONFIG)
        self.assertIsNone(mesh.position(run=lambda *a: self.fail("asked with nothing picked")))
        self.assertEqual(mesh.describe_position({}), ["Meshtastic GPS: off (Settings > Devices)"])

    def test_the_map_uses_the_gps_radio_too(self):
        self.assertEqual(mesh.connection("meshtastic"), ("usb", self.port))
        self.assertIsNone(mesh.connection("meshcore"))


MESHTASTIC_FIX = {"a": {"num": 1, "position": {"latitude": 43.16, "longitude": -73.07, "altitude": 270,
                                               "time": 1760990000, "locationSource": "LOC_INTERNAL"}}}


if __name__ == "__main__":
    unittest.main()
