"""Check emcomm-recorder's voice-activated recording starts with a signal (keeping
the half second before it) and stops after a few seconds of quiet.

Run: python3 tests/test_recorder.py
"""

import array
import importlib.machinery
import importlib.util
import math
import os
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

    def test_file_name(self):
        name = rec.file_name(1792447200, "14074000", "USB")
        self.assertTrue(name.endswith("Recordings/2026-10-19/220000Z 14.074 USB.wav"))
        self.assertTrue(rec.file_name(1792447200, "", "").endswith("220000Z.wav"))


if __name__ == "__main__":
    unittest.main()
