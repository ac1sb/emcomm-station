"""Tests for emcomm-splash (the start-up screen), in a scratch tree with fake system commands."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/kiosk/files/emcomm-splash")
FAKE = """#!/bin/sh
echo "$(basename "$0") $*" >> "$EMCOMM_ROOT/calls"
if [ "$(basename "$0")" = plymouth-set-default-theme ]; then
  if [ -n "$1" ]; then echo "$1" > "$EMCOMM_ROOT/theme"; else cat "$EMCOMM_ROOT/theme"; fi
fi
"""


class Splash(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        bin_dir = os.path.join(self.root, "bin")
        os.makedirs(bin_dir)
        for name in ("plymouth-set-default-theme", "update-initramfs", "update-grub"):
            with open(os.path.join(bin_dir, name), "w", encoding="utf-8") as f:
                f.write(FAKE)
            os.chmod(os.path.join(bin_dir, name), 0o755)
        theme = os.path.join(self.root, "usr/share/plymouth/themes/emcomm")
        os.makedirs(theme)
        shutil.copy(os.path.join(REPO, "roles/kiosk/files/splash/logo.png"), theme)
        os.makedirs(os.path.join(self.root, "etc/emcomm"))
        os.makedirs(os.path.join(self.root, "etc/default/grub.d"))
        open(os.path.join(self.root, "etc/default/grub"), "w").close()
        with open(os.path.join(self.root, "theme"), "w", encoding="utf-8") as f:
            f.write("spinner\n")
        with open(os.path.join(self.root, "etc/emcomm/station.json"), "w", encoding="utf-8") as f:
            json.dump({"callsign": "ac1sb"}, f)
        self.env = dict(os.environ, EMCOMM_ROOT=self.root, PATH=bin_dir + ":" + os.environ["PATH"])

    def run_helper(self, *args):
        open(os.path.join(self.root, "calls"), "w").close()
        result = subprocess.run([sys.executable, HELPER, *args], env=self.env, capture_output=True, text=True,
                                check=False)
        with open(os.path.join(self.root, "calls"), encoding="utf-8") as f:
            return result, f.read()

    def read(self, path):
        with open(os.path.join(self.root, path), encoding="utf-8") as f:
            return f.read()

    def test_logo_is_the_default_and_rebuilds_only_once(self):
        result, calls = self.run_helper("apply")
        self.assertEqual(result.stdout.strip(), "changed")
        self.assertIn("plymouth-set-default-theme emcomm", calls)
        self.assertIn("update-initramfs -u", calls)
        self.assertIn("update-grub", calls)
        script = self.read("usr/share/plymouth/themes/emcomm/emcomm.script")
        self.assertIn('"AC1SB"', script)
        self.assertIn("whole = 0;", script)
        self.assertIn("quiet splash", self.read("etc/default/grub.d/emcomm-quiet-boot.cfg"))
        result, calls = self.run_helper("apply")
        self.assertEqual(result.stdout.strip(), "unchanged")
        self.assertNotIn("update-", calls)

    def test_text_takes_quiet_splash_off(self):
        self.run_helper("apply")
        result, calls = self.run_helper("set", "text")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plymouth-set-default-theme spinner", calls)
        self.assertIn("update-grub", calls)
        cfg = self.read("etc/default/grub.d/emcomm-quiet-boot.cfg")
        self.assertIn("s/\\bquiet\\b//", cfg)
        self.assertEqual(json.loads(self.read("etc/emcomm/splash.json")), {"style": "text"})

    def test_picture(self):
        bad = os.path.join(self.root, "x.jpg")
        with open(bad, "wb") as f:
            f.write(b"\xff\xd8 not a png")
        result, _calls = self.run_helper("set", "picture", bad)
        self.assertEqual(result.returncode, 1)
        self.assertIn("PNG", result.stderr)
        good = os.path.join(REPO, "roles/kiosk/files/splash/logo.png")
        result, calls = self.run_helper("set", "picture", good)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("whole = 1;", self.read("usr/share/plymouth/themes/emcomm/emcomm.script"))
        self.assertIn("update-initramfs -u", calls)
        result, _calls = self.run_helper()
        self.assertEqual(json.loads(result.stdout), {"style": "picture", "picture": True})

    def test_unknown_style(self):
        result, _calls = self.run_helper("set", "fireworks")
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
