"""Check the scanner reads channel lists, filters by distance, and that its FM
squelch and PL tone check work on simulated signals.

Run: python3 tests/test_scanner.py
"""

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import types
import unittest

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/apps/files/emcomm-scanner")
VERMONT = os.path.join(REPO, "roles/apps/files/scanner/Vermont emergency channels.csv")
AIRBAND = os.path.join(REPO, "roles/apps/files/scanner/Airband channels.csv")


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
        self.assertEqual(sc.parse_mhz("29.6"), 29.6)  # 10 m FM, for a receiver that reaches it
        self.assertIsNone(sc.parse_mhz("0.01"))
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


class FakeRange:
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

    def minimum(self):
        return self.lo

    def maximum(self):
        return self.hi


def fake_soapy(devices, busy=()):
    """A stand-in SoapySDR module listing the given devices (dicts with driver, label, serial)."""
    class Device:
        def __init__(self, args):
            if args.get("driver") in busy:
                raise RuntimeError("device busy")
            self.args = args

        @staticmethod
        def enumerate(query):
            driver = query.split("=", 1)[1]
            return [d for d in devices if d["driver"] == driver]

        def listSampleRates(self, _dir, _ch):
            return [912000.0, 768000.0, 456000.0, 384000.0, 256000.0, 192000.0]

        def getSampleRateRange(self, _dir, _ch):
            return []

        def getFrequencyRange(self, _dir, _ch):
            return [FakeRange(9e3, 31e6), FakeRange(60e6, 260e6)]

    return types.SimpleNamespace(Device=Device, SOAPY_SDR_RX=0, SOAPY_SDR_CRITICAL=0, setLogLevel=lambda _l: None)


class Receivers(unittest.TestCase):
    DEVICES = [{"driver": "rtlsdr", "label": "Generic RTL2832U OEM :: 00000001", "serial": "00000001"},
               {"driver": "rtlsdr", "label": "RTLSDRBlog, Blog V4", "serial": "00000002"},
               {"driver": "airspyhf", "label": "AirSpy HF+ [12345]", "serial": "12345"},
               {"driver": "hackrf", "label": "HackRF One #0 abcd", "serial": "abcd"}]

    def setUp(self):
        sys.modules["SoapySDR"] = fake_soapy(self.DEVICES, busy=("hackrf",))

    def tearDown(self):
        del sys.modules["SoapySDR"]

    def test_every_receiver_with_gqrx_strings(self):
        rxs = {rx["driver"] + str(rx["rtl_index"]): rx for rx in sc.receivers()}
        self.assertEqual(rxs["rtlsdr0"]["gqrx"], "rtl=0")  # the factory serial isn't unique
        self.assertEqual(rxs["rtlsdr1"]["gqrx"], "rtl=00000002")
        self.assertEqual(rxs["rtlsdr1"]["low_mhz"], 0.5)  # V4: HF built in
        hf = rxs["airspyhf-1"]
        self.assertEqual(hf["gqrx"], "soapy=0,driver=airspyhf,serial=12345")
        self.assertEqual((hf["scan_rate"], hf["gqrx_rate"], hf["high_mhz"]), (192000, 912000, 260))
        self.assertEqual(rxs["hackrf-1"]["scan_rate"], 2000000)  # busy: the driver's usual values

    def test_gqrx_offers_hf_by_direct_sampling_only_where_needed(self):
        choices = sc.gqrx_choices(sc.receivers())
        hf = [c for c in choices if c["key"].endswith("-hf")]
        self.assertEqual([c["gqrx"] for c in hf], ["rtl=0,direct_samp=2"])
        self.assertTrue(all(c["start_hz"] == 7200000 for c in choices if c["low_mhz"] < sc.HF_BELOW))

    def test_scanner_leaves_the_weather_radio_its_dongle(self):
        rxs = sc.receivers()
        self.assertEqual(sc.pick_receiver("", rxs, nwr=False)["rtl_index"], 0)
        self.assertEqual(sc.pick_receiver("", rxs, nwr=True)["driver"], "airspyhf")
        self.assertEqual(sc.pick_receiver("hackrf-abcd", rxs, nwr=True)["driver"], "hackrf")
        self.assertIsNone(sc.pick_receiver("", [], nwr=False))


class OtherRates(unittest.TestCase):
    def test_squelch_and_tone_at_other_receivers_rates(self):
        for rate in (192000, 768000, 2000000, 2500000):
            demod, rng, start, levels, fms = sc.Demod(rate), np.random.default_rng(5), 0, [], []
            n = rate // 10
            for _ in range(6):
                _audio, fm, level = demod.process(sc.fm_test_signal(n, start, True, 118.8, rng, rate=rate))
                start += n
                levels.append(level)
                fms.append(fm)
            self.assertLess(np.median(levels), sc.SQUELCH_LEVELS[6], rate)
            self.assertTrue(sc.has_tone(np.concatenate(fms), 118.8, demod.audio_rate), rate)
            quiet = sc.Demod(rate)
            noise = [quiet.process(sc.fm_test_signal(n, 0, False, None, rng, rate=rate))[2] for _ in range(4)]
            self.assertGreater(np.median(noise), sc.SQUELCH_LEVELS[4], rate)


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


def am_listen(on, snr_db=25, rate=sc.RATE, blocks=6):
    """(median level, audio) from simulated AM IQ through the AM demodulator."""
    rng = np.random.default_rng(11)
    demod, start, levels, out = sc.AMDemod(rate), 0, [], []
    n = int(sc.LISTEN * rate / sc.RATE)
    for _ in range(blocks):
        audio, _env, level = demod.process(sc.am_test_signal(n, start, on, rng, snr_db=snr_db, rate=rate))
        start += n
        levels.append(level)
        out.append(audio)
    return float(np.median(levels)), np.concatenate(out), demod.audio_rate


class Airband(unittest.TestCase):
    def test_airband_is_am(self):
        channels = sc.load_channels(AIRBAND)
        self.assertTrue(all(ch["mode"] == "AM" and not ch.get("unsupported") for ch in channels))
        self.assertIn(121.5, [ch["mhz"] for ch in channels])
        self.assertEqual(sc.default_mode(121.5), "AM")
        self.assertEqual(sc.default_mode(155.475), "FM")
        self.assertEqual(sc.manual_channel(119.5)["mode"], "AM")

    def test_airband_joins_the_operators_list_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            mine = os.path.join(tmp, "Scanner channels.csv")
            with open(mine, "w") as f:
                f.write("Frequency,Alpha Tag,Group\n155.4750,NATIONAL EMS,EMS\n121.5000,MY GUARD,Air\n")
            old = sc.CHANNELS, sc.AIRBAND_LIST
            sc.CHANNELS, sc.AIRBAND_LIST = mine, AIRBAND
            try:
                channels = sc.load_channels()
                self.assertEqual(len(sc.load_channels(mine)), len(channels))  # the same path either way
            finally:
                sc.CHANNELS, sc.AIRBAND_LIST = old
            guard = [ch for ch in channels if ch["mhz"] == 121.5]
            self.assertEqual([ch["name"] for ch in guard], ["MY GUARD"])
            self.assertEqual(guard[0]["mode"], "AM")  # no Mode column: the band decides
            self.assertIn("Airband", {ch["group"] for ch in channels})
            self.assertEqual(len(channels), 2 + len(sc.load_channels(AIRBAND)) - 1)

    def test_am_squelch(self):
        self.assertGreater(am_listen(False)[0], sc.SQUELCH_LEVELS[4])
        self.assertLess(am_listen(True, snr_db=20)[0], sc.SQUELCH_LEVELS[6])
        self.assertLess(am_listen(True, snr_db=-13)[0], sc.SQUELCH_LEVELS[2])

    def test_am_squelch_ignores_a_busy_neighbour(self):
        rng = np.random.default_rng(2)
        n = sc.LISTEN
        t = np.arange(n) / sc.RATE
        neighbour = (sc.am_test_signal(n, 0, False, rng)
                     + 3 * np.exp(2j * np.pi * (sc.OFFSET + 25000) * t)).astype(np.complex64)
        self.assertGreater(sc.am_level(neighbour, sc.RATE), sc.SQUELCH_LEVELS[4])

    def test_am_audio_is_the_voice(self):
        for rate in (sc.RATE, 2000000):
            _level, audio, audio_rate = am_listen(True, rate=rate)
            audio = audio[int(audio_rate) // 4:]
            spec = np.abs(np.fft.rfft(audio))
            freqs = np.fft.rfftfreq(len(audio), 1 / audio_rate)
            self.assertAlmostEqual(freqs[spec.argmax()], 1000, delta=5, msg=rate)
            self.assertGreater(np.abs(audio).max(), 0.5, rate)

    def test_the_scanner_picks_the_demodulator_by_mode(self):
        demods = {"FM": sc.Demod(), "AM": sc.AMDemod()}
        self.assertIs(sc.demod_for({"mode": "AM"}, demods), demods["AM"])
        self.assertIs(sc.demod_for({"mode": "FM"}, demods), demods["FM"])


class HangTime(unittest.TestCase):
    """How long the scanner stays on an active channel, on a simulated clock."""

    class Clock:
        now = 1000.0

        def time(self):
            return self.now

    class Dongle:
        rate = sc.RATE

        def __init__(self, clock, talk_for):
            self.clock, self.until, self.n = clock, clock.now + talk_for, 0
            self.rng = np.random.default_rng(5)

        def tune(self, mhz):
            pass

        def read(self, samples):
            self.clock.now += samples / sc.RATE
            on = self.clock.now < self.until
            return sc.fm_test_signal(samples, self.n, on, None, self.rng, advance=self)

    def stay(self, hang, talk_for, held=None):
        clock = self.Clock()
        real_time = sc.time
        sc.time = clock
        try:
            scanner = sc.Scanner(lambda _state: None)
            scanner._play = lambda _audio: None
            scanner.dongle = self.Dongle(clock, talk_for)
            settings = dict(sc.DEFAULTS, hang=hang)
            scanner.settings = settings
            start = clock.now
            self.assertTrue(scanner._visit({"mhz": 155.0, "tone_kind": None}, sc.Demod(), settings, held))
            return clock.now - start
        finally:
            sc.time = real_time

    def test_rules(self):
        self.assertEqual(sc.hang_rule("quiet2"), (None, 2.0))
        self.assertEqual(sc.hang_rule("quiet10"), (None, 10.0))
        self.assertEqual(sc.hang_rule("15"), (15.0, None))
        for odd in (None, "", "0", "abc", "quietx"):
            self.assertEqual(sc.hang_rule(odd), (None, sc.HANG))

    def test_until_quiet_then_a_wait(self):
        self.assertAlmostEqual(self.stay("quiet2", 3), 5, delta=0.5)
        self.assertAlmostEqual(self.stay("quiet10", 3), 13, delta=0.5)

    def test_set_time_moves_on_while_still_talking(self):
        self.assertAlmostEqual(self.stay("10", 40), 10, delta=0.5)

    def test_set_time_stays_after_it_goes_quiet(self):
        self.assertAlmostEqual(self.stay("15", 3), 15, delta=0.5)

    def test_held_channel_ignores_the_set_time(self):
        self.assertAlmostEqual(self.stay("5", 12, held={"mhz": 155.0}), 14, delta=0.5)


class GqrxWithoutReceiver(unittest.TestCase):
    def test_network_receiver(self):
        self.assertEqual(sc.network_choice("shack-pi.local")["gqrx"], "rtl_tcp=shack-pi.local:1234")
        choice = sc.network_choice(" 192.168.1.20:5555 ")
        self.assertEqual(choice["gqrx"], "rtl_tcp=192.168.1.20:5555")
        self.assertEqual(choice["key"], "net-192.168.1.20-5555")
        self.assertEqual(choice["rtl_index"], -1)

    def test_practice_recording_has_the_fm_signal_where_it_says(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = sc.practice_recording(os.path.join(tmp, "p.cf32"), rate=48000, seconds=2)
            iq = np.fromfile(path, dtype=np.complex64)
        self.assertEqual(len(iq), 96000)
        spec = np.abs(np.fft.fftshift(np.fft.fft(iq[:48000])))
        freqs = np.fft.fftshift(np.fft.fftfreq(48000, 1 / 48000))
        self.assertAlmostEqual(abs(freqs[np.argmax(spec)]), 20000, delta=4000)


if __name__ == "__main__":
    unittest.main()
