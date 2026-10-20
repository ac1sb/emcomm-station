"""Check emcomm-display reads the screen's resolutions and the touchscreens from
xrandr and xinput, and builds the right xrandr command from the saved settings.

Run: python3 tests/test_display.py
"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/kiosk/files/emcomm-display")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_display", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_display", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


display = load_helper()

XRANDR = """Screen 0: minimum 320 x 200, current 1024 x 600, maximum 16384 x 16384
eDP-1 connected 1024x600+0+0 (normal left inverted right x axis y axis) 154mm x 86mm
   1024x600      60.00*+
   800x600       60.32    56.25
   640x480       59.94
HDMI-1 connected primary 1920x1080+1024+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00 +  50.00    59.94
   1920x1080i    60.00    50.00
   1280x720      60.00*   50.00
DP-1 disconnected (normal left inverted right x axis y axis)
   1024x768 (0x4b) 65.000MHz -HSync -VSync
"""

ROTATED = """Screen 0: minimum 320 x 200, current 600 x 1024, maximum 16384 x 16384
HDMI-1 connected primary 600x1024+0+0 left (normal left inverted right x axis y axis) 154mm x 86mm
   1024x600      60.00*+
   800x480       60.00
"""

XINPUT = """⎡ Virtual core pointer                    \tid=2\t[master pointer  (3)]
\tReporting 3 classes:
⎜   ↳ Virtual core XTEST pointer              \tid=4\t[slave  pointer  (2)]
\t\tClass originated from: 4. Type: XIButtonClass
⎜   ↳ ILITEK ILITEK-TP                        \tid=10\t[slave  pointer  (2)]
\t\tClass originated from: 10. Type: XITouchClass
\t\tTouch mode: direct
\t\tMax number of touches: 10
⎜   ↳ Logitech USB Optical Mouse              \tid=11\t[slave  pointer  (2)]
\t\tClass originated from: 11. Type: XIButtonClass
⎜   ↳ Synaptics TouchPad                      \tid=12\t[slave  pointer  (2)]
\t\tClass originated from: 12. Type: XITouchClass
\t\tTouch mode: dependent
⎣ Virtual core keyboard                   \tid=3\t[master keyboard (2)]
\t\tTouch mode: direct
"""


class Outputs(unittest.TestCase):
    def test_primary_first_with_modes(self):
        outputs = display.parse_outputs(XRANDR)
        self.assertEqual([o["name"] for o in outputs], ["HDMI-1", "eDP-1"])
        hdmi = outputs[0]
        self.assertEqual(hdmi["modes"], ["1920x1080", "1280x720"])
        self.assertEqual(hdmi["preferred"], "1920x1080")
        self.assertEqual(hdmi["current"], "1920x1080")
        self.assertEqual(outputs[1]["modes"], ["1024x600", "800x600", "640x480"])

    def test_rotated_screen(self):
        out = display.parse_outputs(ROTATED)[0]
        self.assertEqual(out["rotate"], "left")
        self.assertEqual(out["current"], "1024x600")

    def test_disconnected_modes_ignored(self):
        self.assertNotIn("1024x768", sum((o["modes"] for o in display.parse_outputs(XRANDR)), []))


class Touch(unittest.TestCase):
    def test_only_touchscreens(self):
        self.assertEqual(display.touch_devices(XINPUT), ["ILITEK ILITEK-TP"])


class Command(unittest.TestCase):
    def setUp(self):
        self.out = display.parse_outputs(XRANDR)[0]

    def test_known_mode(self):
        args = display.xrandr_args(self.out, {"mode": "1280x720", "rotate": "right", "text_scale": 1.0})
        self.assertEqual(args, ["xrandr", "--output", "HDMI-1", "--mode", "1280x720", "--rotate", "right"])

    def test_unknown_mode_falls_back_to_auto(self):
        # A setting saved for another screen mustn't leave this one blank.
        args = display.xrandr_args(self.out, {"mode": "1024x600", "rotate": "normal", "text_scale": 1.0})
        self.assertEqual(args, ["xrandr", "--output", "HDMI-1", "--auto", "--rotate", "normal"])


class Config(unittest.TestCase):
    def test_bad_values_use_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "display.json")
            with open(path, "w") as f:
                json.dump({"mode": "big; rm -rf", "rotate": "sideways", "text_scale": 9}, f)
            self.assertEqual(display.load_config(path), display.DEFAULTS)
            display.save_config({"mode": "800x600", "rotate": "left", "text_scale": 1.25}, path)
            self.assertEqual(display.load_config(path), {"mode": "800x600", "rotate": "left", "text_scale": 1.25})

    def test_missing_file(self):
        self.assertEqual(display.load_config("/nonexistent/display.json"), display.DEFAULTS)


if __name__ == "__main__":
    unittest.main()
