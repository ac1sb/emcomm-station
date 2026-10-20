"""Check the scanner reads channel lists, filters by distance, and that its FM
squelch and PL tone check work on simulated signals.

Run: python3 tests/test_scanner.py
"""

import importlib.machinery
import importlib.util
import os
import tempfile
import unittest

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/apps/files/emcomm-scanner")
VERMONT = os.path.join(REPO, "roles/apps/files/scanner/Vermont emergency channels.csv")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_scanner", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_scanner", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


sc = load_helper()


def listen(on, tone=None, snr_db=25, blocks=6):
    """Run a few blocks of simulated IQ through the demodulator; return (hiss, discriminator output)."""
    rng = np.random.default_rng(7)
    demod, start, fm_all, noise = sc.Demod(), 0, [], []
    for _ in range(blocks):
        iq = sc.fm_test_signal(sc.LISTEN, start, on, tone, rng, snr_db=snr_db)
        start += sc.LISTEN
        _audio, fm, level = demod.process(iq)
        fm_all.append(fm)
        noise.append(level)
    return float(np.median(noise)), np.concatenate(fm_all)


class Tones(unittest.TestCase):
    def test_tone_kinds(self):
        self.assertEqual(sc.parse_tone("118.8 PL"), ("pl", 118.8))
        self.assertEqual(sc.parse_tone("023 DPL"), ("dpl", "023"))
        self.assertEqual(sc.parse_tone("CSQ"), (None, None))
        self.assertEqual(sc.parse_tone(""), (None, None))
        self.assertEqual(sc.parse_tone("100.0"), ("pl", 100.0))


class Lists(unittest.TestCase):
    def test_vermont_list(self):
        channels = sc.load_channels(VERMONT)
        self.assertEqual(len(channels), 347)
        first = channels[0]
        self.assertEqual((first["name"], first["mhz"], first["group"]), ("MANCHESTER PD", 460.05, "VT Law Enf"))
        self.assertEqual((first["tone_kind"], first["tone"]), ("pl", 118.8))

    def test_distance_filter_keeps_statewide_channels(self):
        channels = sc.load_channels(VERMONT)
        sc.add_distances(channels, sc.grid_to_latlon("FN33le"))  # Manchester Center
        near = sc.scan_list(channels, dict(sc.DEFAULTS, miles=10))
        self.assertTrue(near)
        self.assertTrue(all(ch["miles"] is None or ch["miles"] <= 10 for ch in near))
        self.assertTrue(any(ch["miles"] is None for ch in near))  # statewide, no site
        self.assertLess(len(near), len(sc.scan_list(channels, dict(sc.DEFAULTS, miles=0))))

    def test_groups_and_lockouts(self):
        channels = sc.load_channels(VERMONT)
        sc.add_distances(channels, None)
        settings = dict(sc.DEFAULTS, miles=0, groups_off=["VT Fire/EMS"],
                        lockouts=[sc.channel_key(channels[0])])
        kept = sc.scan_list(channels, settings)
        self.assertNotIn(channels[0], kept)
        self.assertFalse(any(ch["group"] == "VT Fire/EMS" for ch in kept))

    def test_other_column_names_and_hz(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("Frequency Output,Description,Tag,Mode,PL Tone\n155475000,Statewide mutual aid,Interop,FMN,\n"
                    "453.1,Digital,Law,P25,\nnot a number,x,y,FM,\n")
        try:
            channels = sc.load_channels(f.name)
        finally:
            os.remove(f.name)
        self.assertEqual([ch["mhz"] for ch in channels], [155.475, 453.1])
        self.assertEqual(channels[1]["unsupported"], "P25")
        self.assertEqual(sc.scan_list(channels, dict(sc.DEFAULTS, miles=0)), [channels[0]])


class Manual(unittest.TestCase):
    def test_typed_frequencies(self):
        self.assertEqual(sc.parse_mhz("155.475"), 155.475)
        self.assertEqual(sc.parse_mhz("155,475"), 155.475)
        self.assertEqual(sc.parse_mhz("155475000"), 155.475)
        self.assertIsNone(sc.parse_mhz("14.074"))  # below what an RTL-SDR tunes
        self.assertIsNone(sc.parse_mhz("abc"))

    def test_save_to_the_users_list_keeps_its_columns(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "list.csv")
            with open(VERMONT, encoding="utf-8") as src, open(path, "w", encoding="utf-8") as dst:
                dst.write(src.read().rstrip("\n"))  # no newline at the end
            sc.append_channel(path, 155.475, "STATE MUTUAL AID")
            channels = sc.load_channels(path)
            self.assertEqual(len(channels), 348)
            last = channels[-1]
            self.assertEqual((last["mhz"], last["name"], last["group"]), (155.475, "STATE MUTUAL AID", "My channels"))
            sc.append_channel(os.path.join(d, "new.csv"), 462.5625, "FRS 1")
            self.assertEqual(sc.load_channels(os.path.join(d, "new.csv"))[0]["name"], "FRS 1")


class Gqrx(unittest.TestCase):
    def test_bookmarks_have_five_fields_and_known_tags(self):
        text = sc.gqrx_bookmarks(sc.load_channels(VERMONT))
        head, body = text.split("\n\n", 1)
        tags = {line.split(";")[0] for line in head.splitlines() if not line.startswith("#")}
        self.assertEqual(tags, {"VT Law Enf", "VT Fire/EMS", "VT Interop/EOC"})
        rows = [line.split(";") for line in body.splitlines() if not line.startswith("#")]
        self.assertEqual(len(rows), 347)
        self.assertTrue(all(len(r) == 5 and r[4].strip() in tags for r in rows))
        self.assertEqual((int(rows[0][0]), rows[0][2].strip()), (460050000, "Narrow FM"))


class Squelch(unittest.TestCase):
    def test_no_signal_is_hiss(self):
        level, _ = listen(False)
        self.assertGreater(level, sc.SQUELCH_LEVELS[4])

    def test_signal_quiets_the_hiss(self):
        level, _ = listen(True, snr_db=20)
        self.assertLess(level, sc.SQUELCH_LEVELS[6])

    def test_weak_signal_still_opens_a_loose_squelch(self):
        level, _ = listen(True, snr_db=-13)
        self.assertLess(level, sc.SQUELCH_LEVELS[2])

    def test_pl_tone(self):
        _, fm = listen(True, tone=118.8)
        self.assertTrue(sc.has_tone(fm, 118.8))
        self.assertFalse(sc.has_tone(fm, 123.0))
        self.assertFalse(sc.has_tone(fm, 114.8))
        _, plain = listen(True)
        self.assertFalse(sc.has_tone(plain, 118.8))

    def test_audio_is_the_voice_not_the_tone(self):
        rng = np.random.default_rng(3)
        demod, start, out = sc.Demod(), 0, []
        for _ in range(5):
            audio, _fm, _ = demod.process(sc.fm_test_signal(sc.LISTEN, start, True, 118.8, rng))
            start += sc.LISTEN
            out.append(audio)
        audio = np.concatenate(out)[sc.AUDIO_RATE // 4:]
        spec = np.abs(np.fft.rfft(audio))
        freqs = np.fft.rfftfreq(len(audio), 1 / sc.AUDIO_RATE)
        self.assertAlmostEqual(freqs[spec.argmax()], 1000, delta=5)
        tone = spec[np.abs(freqs - 118.8) < 2].max()
        self.assertLess(tone, spec.max() / 30)


if __name__ == "__main__":
    unittest.main()
