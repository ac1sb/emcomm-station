"""Check emcomm-recorder's voice-activated recording starts with a signal (keeping
the half second before it) and stops after a few seconds of quiet.

Run: python3 tests/test_recorder.py
"""

import array
import importlib.machinery
import importlib.util
import json
import math
import os
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/radio/files/emcomm-recorder")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_recorder", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_recorder", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


rec = load_helper()


def tone(amplitude):
    n = rec.CHUNK // 2
    samples = array.array("h", (int(amplitude * math.sin(i / 3)) for i in range(n)))
    return samples.tobytes()


QUIET, LOUD = tone(30), tone(8000)


class Recorder(unittest.TestCase):
    def test_levels(self):
        self.assertLess(rec.level_db(QUIET), -40)
        self.assertGreater(rec.level_db(LOUD), -40)
        self.assertEqual(rec.level_db(b""), -96.0)

    def test_voice_activated(self):
        seg = rec.Segmenter(-40)
        for _ in range(20):
            self.assertEqual(seg.feed(QUIET)[0], None)
        action, chunks = seg.feed(LOUD)
        self.assertEqual((action, len(chunks)), ("start", rec.PRE_ROLL + 1))
        self.assertEqual(seg.feed(LOUD)[0], "write")
        actions = [seg.feed(QUIET)[0] for _ in range(rec.HANG)]
        self.assertEqual(actions[-1], "stop")
        self.assertEqual(set(actions[:-1]), {"write"})
        self.assertEqual(seg.feed(QUIET)[0], None)

    def test_everything_splits_hourly(self):
        seg = rec.Segmenter(everything=True)
        self.assertEqual(seg.feed(QUIET)[0], "start")
        actions = [seg.feed(QUIET)[0] for _ in range(rec.MAX_CHUNKS - 1)]
        self.assertEqual(actions[-1], "stop")

    def test_prune_keeps_the_newest(self):
        with tempfile.TemporaryDirectory() as folder:
            names = ["2026-10-18/220000Z.wav", "2026-10-18/230000Z.wav", "2026-10-19/010000Z.wav",
                     "2026-10-19/020000Z.wav.part"]
            for name in names:
                os.makedirs(os.path.join(folder, os.path.dirname(name)), exist_ok=True)
                with open(os.path.join(folder, name), "wb") as f:
                    f.write(b"\0" * 1000)
            self.assertEqual(rec.prune(folder, limit=4000), 0)
            self.assertEqual(rec.prune(folder, limit=2500), 2)
            self.assertEqual(sorted(os.listdir(folder)), ["2026-10-19"])
            self.assertEqual(sorted(os.listdir(os.path.join(folder, "2026-10-19"))),
                             ["010000Z.wav", "020000Z.wav.part"])
            self.assertEqual(rec.prune(os.path.join(folder, "missing")), 0)

    def test_file_name(self):
        name = rec.file_name(1792447200, "14074000", "USB")
        self.assertTrue(name.endswith("Recordings/2026-10-19/220000Z 14.074 USB.wav"))
        self.assertTrue(rec.file_name(1792447200, "", "").endswith("220000Z.wav"))

    def test_plays_to_a_named_speaker_that_isnt_the_radio(self):
        dump = [{"id": 31, "type": "PipeWire:Interface:Node",
                 "info": {"props": {"media.class": "Audio/Sink", "api.alsa.card": "2",
                                    "node.name": "alsa_output.usb-radio"}}},
                {"id": 45, "type": "PipeWire:Interface:Node",
                 "info": {"props": {"media.class": "Audio/Sink", "api.alsa.card": "0",
                                    "node.name": "alsa_output.pci-speakers"}}}]
        real_run, real_readlink = rec.subprocess.run, rec.os.readlink
        rec.subprocess.run = lambda *a, **k: type("R", (), {"stdout": json.dumps(dump)})()
        rec.os.readlink = lambda _p: "card2"
        try:
            self.assertEqual(rec.other_sink(), "alsa_output.pci-speakers")
            rec.os.readlink = lambda _p: "card0"
            self.assertEqual(rec.other_sink(), "alsa_output.usb-radio")
            dump.pop(1)
            rec.os.readlink = lambda _p: "card2"
            self.assertIsNone(rec.other_sink())
        finally:
            rec.subprocess.run, rec.os.readlink = real_run, real_readlink


if __name__ == "__main__":
    unittest.main()
