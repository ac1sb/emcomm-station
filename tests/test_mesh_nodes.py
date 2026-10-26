"""Check emcomm-mesh-nodes reads node positions from Meshtastic and MeshCore, keeps
the last list when a radio can't be asked, and leaves a radio alone while its tile
has it.

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


if __name__ == "__main__":
    unittest.main()
