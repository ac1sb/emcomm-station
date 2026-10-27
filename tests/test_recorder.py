"""Check emcomm-recorder's voice-activated recording starts with a signal (keeping
the half second before it) and stops after a few seconds of quiet.

Run: python3 tests/test_recorder.py
"""

import array
import importlib.machinery
import importlib.util
import math
import os
import shutil
import tempfile
import unittest
from unittest import mock

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

    def test_pauses_when_the_disk_is_nearly_full(self):
        usage = shutil._ntuple_diskusage if hasattr(shutil, "_ntuple_diskusage") else None
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(rec.shutil, "disk_usage") as du:
            gb = 1024 ** 3
            du.return_value = (100 * gb, 80 * gb, 20 * gb) if usage is None else usage(100 * gb, 80 * gb, 20 * gb)
            self.assertIsNone(rec.out_of_room(os.path.join(folder, "Recordings")))  # not made yet: its parent
            du.return_value = (100 * gb, 96 * gb, 4 * gb) if usage is None else usage(100 * gb, 96 * gb, 4 * gb)
            self.assertIn("96% full", rec.out_of_room(folder))
            small = (8 * gb, 7 * gb, gb // 4)  # under 95%, but only 256 MB free
            du.return_value = small if usage is None else usage(*small)
            self.assertIn("Paused", rec.out_of_room(folder))

    def test_file_name(self):
        name = rec.file_name(1792447200, "14074000", "USB")
        self.assertTrue(name.endswith("Recordings/2026-10-19/220000Z 14.074 USB.wav"))
        self.assertTrue(rec.file_name(1792447200, "", "").endswith("220000Z.wav"))

    def test_plays_only_to_the_listening_speaker(self):
        calls = []
        real_helper, real_run = rec.audio_helper, rec.subprocess.run
        rec.subprocess.run = lambda argv, **k: calls.append(argv) or type("R", (), {"returncode": 0})()
        try:
            rec.audio_helper = lambda cmd: "alsa_output.pci-speakers" if cmd == "speaker" else None
            self.assertEqual(rec.play("/tmp/a.wav"), 0)
            self.assertEqual(calls[-1], ["pw-play", "--target=alsa_output.pci-speakers", "/tmp/a.wav"])
            rec.audio_helper = lambda cmd: None  # only the radio: never played
            calls.clear()
            self.assertEqual(rec.play("/tmp/a.wav"), 1)
            self.assertEqual(calls, [])
        finally:
            rec.audio_helper, rec.subprocess.run = real_helper, real_run

    def test_audio_helper_reads_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = os.path.join(tmp, "emcomm-audio")
            with open(helper, "w", encoding="utf-8") as f:
                f.write('#!/bin/sh\n[ "$1" = radio-source ] && echo alsa_input.usb-radio && exit 0\nexit 1\n')
            os.chmod(helper, 0o755)
            real = rec.AUDIO_CMD
            rec.AUDIO_CMD = helper
            try:
                self.assertEqual(rec.audio_helper("radio-source"), "alsa_input.usb-radio")
                self.assertIsNone(rec.audio_helper("speaker"))
            finally:
                rec.AUDIO_CMD = real


if __name__ == "__main__":
    unittest.main()
