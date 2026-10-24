"""Check emcomm-audio keeps the radio's sound card for radio apps: anything else that
starts playing on it moves to the listening speaker, or a silent output when there's
none, and nothing plays on the APRS radio's card.

Run: python3 tests/test_audio.py
"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/radio/files/emcomm-audio")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_audio", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_audio", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


audio = load_helper()


def sink(index, name, card=None, bus=None, **props):
    p = dict(props)
    if card is not None:
        p["api.alsa.card"] = str(card)
    if bus:
        p["device.bus"] = bus
    return {"index": index, "name": name, "description": name, "properties": p}


def stream(index, on, name, binary=None):
    p = {"application.name": name}
    if binary:
        p["application.process.binary"] = binary
    return {"index": index, "sink": on, "properties": p}


RADIO = sink(1, "alsa_output.usb-FT-710", card=2, bus="usb")
APRS = sink(2, "alsa_output.usb-Digirig-aprs", card=3, bus="usb")
BUILTIN = sink(3, "alsa_output.pci-0000_00_1f.3.analog-stereo", card=0, bus="pci")
HDMI = sink(4, "alsa_output.pci-0000_00_1f.3.hdmi-stereo", card=0, bus="pci")
HEADSET = sink(5, "alsa_output.usb-Logitech_headset", card=4, bus="usb")
BLUETOOTH = sink(6, "bluez_output.AA_BB_CC_DD_EE_FF.1", bus="bluetooth")
SILENT = sink(7, audio.SILENT)
SETTINGS = {"listen_sink": "", "radio_apps": []}


class Speaker(unittest.TestCase):
    def test_automatic_prefers_bluetooth_then_built_in_then_hdmi(self):
        cards = ["2"]
        self.assertEqual(audio.listening_speaker([RADIO, HDMI, BUILTIN], cards, "")["name"], BUILTIN["name"])
        self.assertEqual(audio.listening_speaker([RADIO, HDMI, BUILTIN, BLUETOOTH], cards, "")["name"],
                         BLUETOOTH["name"])
        self.assertEqual(audio.listening_speaker([RADIO, HDMI], cards, "")["name"], HDMI["name"])

    def test_never_a_radio_and_never_usb_unless_picked(self):
        # A second radio's USB audio looks like a headset, so automatic leaves USB alone.
        self.assertIsNone(audio.listening_speaker([RADIO, HEADSET, SILENT], ["2"], ""))
        self.assertEqual(audio.listening_speaker([RADIO, HEADSET], ["2"], HEADSET["name"])["name"],
                         HEADSET["name"])
        self.assertIsNone(audio.listening_speaker([RADIO], ["2"], RADIO["name"]))
        self.assertIsNone(audio.listening_speaker([RADIO, APRS], ["2", "3"], APRS["name"]))

    def test_a_picked_speaker_that_has_gone_falls_back_to_automatic(self):
        self.assertEqual(audio.listening_speaker([RADIO, BUILTIN], ["2"], HEADSET["name"])["name"],
                         BUILTIN["name"])


class Routing(unittest.TestCase):
    def moves(self, sinks, inputs, settings=SETTINGS, silent_ok=True):
        return audio.plan(sinks, inputs, settings, "2", "3", silent_ok)

    def test_listen_apps_move_off_the_radio(self):
        inputs = [stream(10, 1, "Scanner", "pacat"), stream(11, 1, "Chromium", "chromium"),
                  stream(12, 1, "gqrx", "gqrx")]
        self.assertEqual([(i, t) for i, t, _w in self.moves([RADIO, BUILTIN], inputs)],
                         [(10, BUILTIN["name"]), (11, BUILTIN["name"]), (12, BUILTIN["name"])])

    def test_radio_apps_stay_on_the_radio(self):
        inputs = [stream(20, 1, "WSJT-X", "wsjtx"), stream(21, 1, "fldigi", "fldigi"),
                  stream(22, 1, "ALSA plug-in [direwolf]", "direwolf"), stream(23, 1, "VARA", "VARA.exe"),
                  stream(24, 1, "wine-preloader", "wine64-preloader"), stream(25, 1, "ardopcf", "ardopcf"),
                  stream(26, 1, "JS8Call", "js8call")]
        self.assertEqual(self.moves([RADIO, BUILTIN], inputs), [])

    def test_an_app_the_operator_marked_as_a_radio_app_stays(self):
        inputs = [stream(30, 1, "QtTermTCP", "qttermtcp")]
        self.assertEqual(len(self.moves([RADIO, BUILTIN], inputs)), 1)
        self.assertEqual(self.moves([RADIO, BUILTIN], inputs, {"listen_sink": "", "radio_apps": ["qttermtcp"]}),
                         [])

    def test_no_speaker_means_silent(self):
        inputs = [stream(40, 1, "Scanner", "pacat")]
        self.assertEqual(self.moves([RADIO, HEADSET], inputs)[0][1], audio.SILENT)
        self.assertIsNone(self.moves([RADIO], inputs, silent_ok=False)[0][1])  # muted instead

    def test_silent_streams_move_to_a_speaker_once_one_is_plugged_in(self):
        inputs = [stream(50, 7, "Scanner", "pacat")]
        self.assertEqual(self.moves([RADIO, SILENT], inputs), [])
        self.assertEqual(self.moves([RADIO, SILENT, BUILTIN], inputs)[0][1], BUILTIN["name"])

    def test_nothing_plays_on_the_aprs_radio(self):
        inputs = [stream(60, 2, "WSJT-X", "wsjtx"), stream(61, 2, "Scanner", "pacat")]
        self.assertEqual([t for _i, t, _w in self.moves([RADIO, APRS, BUILTIN], inputs)],
                         [BUILTIN["name"], BUILTIN["name"]])

    def test_streams_elsewhere_are_left_alone(self):
        # The Scanner on a headset; WSJT-X on another USB card, which may be a second radio.
        inputs = [stream(70, 5, "Scanner", "pacat"), stream(71, 5, "WSJT-X", "wsjtx")]
        self.assertEqual(self.moves([RADIO, BUILTIN, HDMI, HEADSET], inputs), [])

    def test_radio_apps_on_the_computers_speaker_go_to_the_radio(self):
        # Desktop "Never": Direwolf and ARDOP open "pipewire", which is the default speaker.
        inputs = [stream(72, 3, "ALSA plug-in [direwolf]", "direwolf"), stream(73, 4, "WSJT-X", "wsjtx"),
                  stream(74, 7, "ardopcf", "ardopcf")]
        self.assertEqual([(i, t) for i, t, _w in self.moves([RADIO, BUILTIN, HDMI, SILENT], inputs)],
                         [(72, RADIO["name"]), (73, RADIO["name"]), (74, RADIO["name"])])

    def test_radio_apps_go_silent_while_the_radio_is_unplugged(self):
        # The radio's card dropped off the USB: its tones mustn't come out of the PC speaker.
        inputs = [stream(75, 3, "WSJT-X", "wsjtx"), stream(76, 7, "WSJT-X", "wsjtx")]
        self.assertEqual(audio.plan([BUILTIN, SILENT], inputs, SETTINGS, None, None),
                         [(75, audio.SILENT, "a radio app, radio unplugged")])

    def test_radio_apps_listen_to_the_radio_not_the_computers_mic(self):
        radio_in = sink(11, "alsa_input.usb-FT-710", card=2, bus="usb")
        pc_mic = sink(12, "alsa_input.pci-0000_00_1f.3.analog-stereo", card=0, bus="pci")
        usb_in = sink(13, "alsa_input.usb-Digirig-vhf", card=5, bus="usb")
        monitor = sink(14, "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor", card=0, bus="pci")
        outputs = [{"index": 80, "source": 12, "properties": {"application.name": "WSJT-X"}},
                   {"index": 81, "source": 12, "properties": {"application.name": "Recorder"}},
                   {"index": 82, "source": 13, "properties": {"application.name": "fldigi"}},
                   {"index": 83, "source": 14, "properties": {"application.name": "fldigi"}},
                   {"index": 84, "source": 11, "properties": {"application.name": "JS8Call"}}]
        sources = [radio_in, pc_mic, usb_in, monitor]
        self.assertEqual(audio.plan_sources(sources, outputs, SETTINGS, "2"),
                         [(80, radio_in["name"], "a radio app")])
        self.assertEqual(audio.plan_sources([pc_mic], outputs, SETTINGS, None), [])

    def test_without_a_radio_nothing_moves(self):
        inputs = [stream(80, 3, "Scanner", "pacat")]
        self.assertEqual(audio.plan([BUILTIN], inputs, SETTINGS, None, None), [])


class Helpers(unittest.TestCase):
    def test_settings_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "audio.json")
            self.assertEqual(audio.load_settings(path), SETTINGS)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"listen_sink": "x", "radio_apps": ["QtTermTCP"], "quiet": True}, f)
            self.assertEqual(audio.load_settings(path), {"listen_sink": "x", "radio_apps": ["qttermtcp"]})
            with open(path, "w", encoding="utf-8") as f:
                f.write("[1, 2]")
            self.assertEqual(audio.load_settings(path), SETTINGS)

    def test_volume_and_kinds(self):
        node = {"volume": {"front-left": {"value": 42598, "value_percent": "65%"}}}
        self.assertEqual(audio.volume_percent(node), 65)
        self.assertIsNone(audio.volume_percent(None))
        self.assertEqual([audio.speaker_kind(s) for s in (BUILTIN, HDMI, HEADSET, BLUETOOTH)],
                         ["builtin", "hdmi", "usb", "bluetooth"])
        self.assertTrue(audio.is_monitor({"name": "x.monitor", "properties": {}}))

    def test_card_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, "rigaudio")
            os.symlink("card2", link)
            self.assertEqual(audio.card_number(link), "2")
            self.assertIsNone(audio.card_number(os.path.join(tmp, "missing")))


if __name__ == "__main__":
    unittest.main()
