"""Render settings into a scratch tree and check the udev rules and rigctld arguments.

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


def preset(name, **changes):
    with open(os.path.join(REPO, "radios", name + ".yml")) as f:
        settings = yaml.safe_load(f)
    settings.update({"callsign": "AC1SB", "grid": "FN31"}, **changes)
    return settings


class ApplySettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

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

    def test_ft891_digirig_preset(self):
        r = self.run_helper(preset("ft-891-digirig", callsign="ac1sb", grid="fn31pr"))
        self.assertEqual(r.returncode, 0, r.stderr)
        rules = self.read("etc/udev/rules.d/99-emcomm-radio.rules")
        self.assertIn('ENV{ID_MODEL_ID}=="ea70"', rules)
        self.assertIn('ENV{ID_USB_INTERFACE_NUM}=="00"', rules)
        self.assertIn('SYMLINK+="rig-ptt"', rules)
        self.assertIn('ENV{ID_VENDOR_ID}=="0d8c"', rules)
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

    def test_ft710_preset_no_audio_yet(self):
        r = self.run_helper(preset("ft-710", cat_baud=9600))
        self.assertEqual(r.returncode, 0, r.stderr)
        env = self.read("etc/emcomm/rigctld.env")
        self.assertIn("--model=1049", env)
        self.assertIn("--serial-speed=9600", env)
        self.assertIn("--ptt-type=CAT", env)
        self.assertNotIn("--ptt-file", env)
        rules = self.read("etc/udev/rules.d/99-emcomm-radio.rules")
        self.assertNotIn("rig-ptt", rules)
        self.assertNotIn("rigaudio", rules)

    def test_any_hamlib_radio_with_detected_devices(self):
        settings = {
            "callsign": "AC1SB", "grid": "FN31", "radio_name": "Icom IC-7300", "rig_model": 3073,
            "cat_baud": 19200,
            "cat_match": {"vendor": "10C4", "product": "EA60", "serial": "IC-7300_03001234"},
            "ptt_method": "RTS", "ptt_match": "cat",
            "audio_match": {"vendor": "08bb", "product": "2901", "serial": ""},
        }
        r = self.run_helper(settings)
        self.assertEqual(r.returncode, 0, r.stderr)
        rules = self.read("etc/udev/rules.d/99-emcomm-radio.rules")
        self.assertIn('ENV{ID_SERIAL_SHORT}=="IC-7300_03001234"', rules)
        self.assertIn('ENV{ID_VENDOR_ID}=="10c4"', rules)
        self.assertNotIn("rig-ptt", rules)
        env = self.read("etc/emcomm/rigctld.env")
        self.assertIn("--model=3073", env)
        self.assertIn("--ptt-file=/dev/rig-cat", env)

    def test_gps_defaults_to_ublox_or_the_chosen_port(self):
        r = self.run_helper(preset("ft-891-digirig"))
        self.assertEqual(r.returncode, 0, r.stderr)
        rules = self.read("etc/udev/rules.d/99-emcomm-radio.rules")
        self.assertIn('ENV{ID_VENDOR_ID}=="1546", SYMLINK+="gps0"', rules)
        r = self.run_helper(preset("ft-891-digirig", gps_match={"vendor": "067B", "product": "2303"}))
        self.assertEqual(r.returncode, 0, r.stderr)
        rules = self.read("etc/udev/rules.d/99-emcomm-radio.rules")
        self.assertIn('ENV{ID_MODEL_ID}=="2303", ENV{ID_VENDOR_ID}=="067b", SYMLINK+="gps0"', rules)
        self.assertEqual(json.loads(self.read("etc/emcomm/station.json"))["gps_match"],
                         {"vendor": "067b", "product": "2303"})

    def test_gps_cannot_be_the_radio_port(self):
        settings = preset("ft-891-digirig")
        settings["gps_match"] = settings["cat_match"]
        r = self.run_helper(settings)
        self.assertEqual(r.returncode, 1)
        self.assertIn("GPS", r.stderr)

    def test_rejects_bad_input(self):
        bad = [
            preset("ft-710", callsign="NOT A CALL"),
            preset("ft-710", grid="ZZ99"),
            preset("ft-710", rig_model="abc"),
            preset("ft-710", cat_baud=1234),
            preset("ft-710", ptt_method="RTS", ptt_match=None),
            preset("ft-710", cat_match=None),
            preset("ft-710", cat_match={"vendor": "10c4", "product": "ea70\", RUN+=\"/bin/sh"}),
            preset("ft-710", cat_match={"vendor": "10c4", "product": "ea70", "serial": "a\"b"}),
            preset("ft-710", cat_match={"vendor": "10c4", "product": "ea70", "driver": "x"}),
            preset("ft-710", radio_name="Evil\"; RUN+=\"x"),
            preset("ft-710", cat_match={"vendor": "10c4", "product": "ea70", "serial": "ABC\n"}),
            [],
        ]
        for settings in bad:
            with self.subTest(settings=settings):
                r = self.run_helper(settings)
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("Settings not saved", r.stderr)
                self.assertFalse(os.path.exists(os.path.join(self.root, "etc/emcomm/station.json")))

    def test_time_zone_is_checked_and_kept(self):
        zones = os.path.join(self.root, "usr/share/zoneinfo/America")
        os.makedirs(zones)
        open(os.path.join(zones, "New_York"), "w").close()
        open(os.path.join(self.root, "passwd"), "w").close()
        r = self.run_helper(preset("ft-710", timezone="America/New_York"))
        self.assertEqual(r.returncode, 0, r.stderr)
        # tzdata's "localtime" is a link to /etc/localtime: picking it would make a loop.
        os.symlink(os.path.join(self.root, "passwd"), os.path.join(self.root, "usr/share/zoneinfo/localtime"))
        r = self.run_helper(preset("ft-710", timezone="localtime"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("time zone", r.stderr)
        self.assertEqual(json.loads(self.read("etc/emcomm/station.json"))["timezone"], "America/New_York")
        for zone in ("America/Nowhere", "../../../passwd", "America/New_York; reboot", "/etc/passwd"):
            with self.subTest(zone=zone):
                r = self.run_helper(preset("ft-710", timezone=zone))
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("time zone", r.stderr)
        # Without one, the computer's time zone is left as it is.
        r = self.run_helper(preset("ft-710"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIsNone(json.loads(self.read("etc/emcomm/station.json"))["timezone"])

    def test_check_only_writes_nothing(self):
        r = self.run_helper(preset("ft-710"), "--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, "etc/emcomm")))


if __name__ == "__main__":
    unittest.main()
