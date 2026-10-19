"""Render settings for every radio profile into a scratch tree and check the output.

Run: python3 tests/test_apply_settings.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/radio/files/emcomm-apply-settings")
RADIOS = os.path.join(REPO, "radios")


class ApplySettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        profiles = os.path.join(self.root, "usr/share/emcomm/radios")
        os.makedirs(profiles)
        for name in os.listdir(RADIOS):
            if name.endswith(".yml"):
                with open(os.path.join(RADIOS, name)) as f:
                    data = yaml.safe_load(f)
                with open(os.path.join(profiles, name[:-4] + ".json"), "w") as f:
                    json.dump(data, f)

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, settings, *flags):
        path = os.path.join(self.root, "new.json")
        with open(path, "w") as f:
            json.dump(settings, f)
        env = dict(os.environ, EMCOMM_ROOT=self.root)
        return subprocess.run([sys.executable, HELPER, *flags, path], env=env,
                              capture_output=True, text=True)

    def read(self, rel):
        with open(os.path.join(self.root, rel)) as f:
            return f.read()

    def test_ft891_digirig(self):
        r = self.run_helper({"callsign": "ac1sb", "grid": "fn31pr", "radio": "ft-891-digirig"})
        self.assertEqual(r.returncode, 0, r.stderr)
        rules = self.read("etc/udev/rules.d/99-emcomm-radio.rules")
        self.assertIn('ATTRS{idProduct}=="ea70"', rules)
        self.assertIn('SYMLINK+="rig-ptt"', rules)
        self.assertIn('ATTR{id}="rigaudio"', rules)
        env = self.read("etc/emcomm/rigctld.env")
        self.assertIn("--model=1036", env)
        self.assertIn("--serial-speed=38400", env)
        self.assertIn("--ptt-type=RTS", env)
        self.assertIn("--ptt-file=/dev/rig-ptt", env)
        saved = json.loads(self.read("etc/emcomm/station.json"))
        self.assertEqual(saved["callsign"], "AC1SB")
        self.assertEqual(saved["grid"], "FN31pr")
        self.assertIn("STATION_CALLSIGN=AC1SB", self.read("etc/emcomm/station.env"))

    def test_ft710_baud_override(self):
        r = self.run_helper({"callsign": "AC1SB", "grid": "FN31", "radio": "ft-710", "cat_baud": 9600})
        self.assertEqual(r.returncode, 0, r.stderr)
        env = self.read("etc/emcomm/rigctld.env")
        self.assertIn("--model=1049", env)
        self.assertIn("--serial-speed=9600", env)
        self.assertIn("--ptt-type=CAT", env)
        self.assertNotIn("--ptt-file", env)
        self.assertNotIn("rig-ptt", self.read("etc/udev/rules.d/99-emcomm-radio.rules"))

    def test_rejects_bad_input(self):
        bad = [
            {"callsign": "NOT A CALL", "grid": "FN31", "radio": "ft-710"},
            {"callsign": "AC1SB", "grid": "ZZ99", "radio": "ft-710"},
            {"callsign": "AC1SB", "grid": "FN31", "radio": "../../etc/passwd"},
            {"callsign": "AC1SB", "grid": "FN31", "radio": "ft-710", "cat_baud": 1234},
            {"callsign": "AC1SB", "grid": "FN31", "radio": "ft-710", "ptt_method": "RTS"},
        ]
        for settings in bad:
            with self.subTest(settings=settings):
                r = self.run_helper(settings)
                self.assertEqual(r.returncode, 1)
                self.assertIn("Settings not saved", r.stderr)
                self.assertFalse(os.path.exists(os.path.join(self.root, "etc/emcomm/station.json")))

    def test_check_only_writes_nothing(self):
        r = self.run_helper({"callsign": "AC1SB", "grid": "FN31", "radio": "ft-710"}, "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, "etc/emcomm")))


if __name__ == "__main__":
    unittest.main()
