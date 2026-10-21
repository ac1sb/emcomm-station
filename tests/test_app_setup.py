"""Check that emcomm-app-setup fills app settings from the station settings
and keeps what the operator set in the apps themselves.

Run: python3 tests/test_app_setup.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/apps/files/emcomm-app-setup")


class AppSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.station = os.path.join(self.home, "station.json")
        self.set_station(callsign="AC1SB", grid="FN31pr")

    def tearDown(self):
        self.tmp.cleanup()

    def set_station(self, **values):
        with open(self.station, "w") as f:
            json.dump(values, f)

    def run_helper(self, app, **extra):
        env = dict(os.environ, HOME=self.home, EMCOMM_STATION=self.station, **extra)
        result = subprocess.run([sys.executable, HELPER, app], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_pat_new_config(self):
        cfg = json.loads(self.read(self.run_helper("pat")))
        self.assertEqual(cfg["mycall"], "AC1SB")
        self.assertEqual(cfg["locator"], "FN31pr")
        self.assertEqual(cfg["hamlib_rigs"]["radio"], {"address": "127.0.0.1:4532", "network": "tcp"})
        for modem in ("ardop", "varahf", "varafm"):
            self.assertEqual(cfg[modem]["rig"], "radio")
            self.assertTrue(cfg[modem]["ptt_ctrl"])
        self.assertEqual(cfg["varahf"]["addr"], "localhost:8300")
        self.assertEqual(cfg["ax25"]["engine"], "agwpe")

    def test_pat_keeps_operator_settings_and_follows_callsign(self):
        path = os.path.join(self.home, ".config/pat/config.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            json.dump({"mycall": "N0CALL", "secure_login_password": "secret",
                       "varahf": {"addr": "localhost:8400", "bandwidth": 500, "ptt_ctrl": False}}, f)
        self.set_station(callsign="W1AW", grid="FN31")
        cfg = json.loads(self.read(self.run_helper("pat")))
        self.assertEqual(cfg["mycall"], "W1AW")
        self.assertEqual(cfg["secure_login_password"], "secret")
        self.assertEqual(cfg["varahf"], {"addr": "localhost:8400", "bandwidth": 500, "ptt_ctrl": False,
                                         "rig": "radio"})

    def test_direwolf(self):
        conf = self.read(self.run_helper("direwolf"))
        self.assertIn("MYCALL AC1SB\n", conf)
        self.assertIn("ADEVICE pipewire\n", conf)
        self.assertIn("PTT RIG 2 localhost:4532\n", conf)
        self.assertIn("AGWPORT 8000\n", conf)

    def test_direwolf_custom_config_wins(self):
        custom = os.path.join(self.home, ".config/emcomm/direwolf.custom.conf")
        os.makedirs(os.path.dirname(custom))
        open(custom, "w").close()
        self.assertEqual(self.run_helper("direwolf"), custom)

    def test_js8call_first_run_only(self):
        path = self.run_helper("js8call")
        ini = self.read(path)
        self.assertIn("MyCall=AC1SB\n", ini)
        self.assertIn("CATNetworkPort=127.0.0.1:4532\n", ini)
        with open(path, "w") as f:
            f.write("[Configuration]\nMyCall=CHANGED\n")
        self.run_helper("js8call")
        self.assertEqual(self.read(path), "[Configuration]\nMyCall=CHANGED\n")

    def test_xastir_position_from_grid_and_agwpe_port(self):
        cnf = self.read(self.run_helper("xastir"))
        self.assertIn("STATION_CALLSIGN:AC1SB\n", cnf)
        self.assertIn("STATION_LAT:4143.750N\n", cnf)
        self.assertIn("STATION_LONG:07242.500W\n", cnf)
        self.assertIn("DEVICE0_TYPE:12\n", cnf)
        self.assertIn("DEVICE0_SPEED:8000\n", cnf)

    def test_xastir_uses_the_aprs_radio_when_plugged_in(self):
        card = os.path.join(self.home, "aprsaudio")
        open(card, "w").close()
        cnf = self.read(self.run_helper("xastir", EMCOMM_APRS_CARD=card))
        self.assertIn("DEVICE0_SPEED:8010\n", cnf)
        os.remove(card)  # unplugged: back to the main radio's Direwolf
        cnf = self.read(self.run_helper("xastir", EMCOMM_APRS_CARD=card)).splitlines()
        self.assertIn("DEVICE0_SPEED:8000", cnf)
        self.assertEqual(sum(line.startswith("DEVICE0_SPEED:") for line in cnf), 1)

    def test_xastir_keeps_operator_interfaces(self):
        path = os.path.join(self.home, ".xastir/config/xastir.cnf")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            f.write("STATION_CALLSIGN:N0CALL\nDEVICE0_TYPE:1\nDEVICE0_SPEED:9600\nMAP_BGCOLOR:3\n")
        self.set_station(callsign="w1aw", grid="FN31")
        cnf = self.read(self.run_helper("xastir")).splitlines()
        self.assertIn("STATION_CALLSIGN:W1AW", cnf)
        self.assertNotIn("STATION_CALLSIGN:N0CALL", cnf)
        self.assertIn("DEVICE0_SPEED:9600", cnf)
        self.assertIn("MAP_BGCOLOR:3", cnf)
        self.assertNotIn("DEVICE0_TYPE:12", cnf)


if __name__ == "__main__":
    unittest.main()
