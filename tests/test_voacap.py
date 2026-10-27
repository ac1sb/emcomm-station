"""Check emcomm-voacap writes VOACAP's fixed-column cards the way voacapl reads them,
reads its method 30 output back, and plans from the station's grid to a place.

The planning tests use a stand-in voacapl. With the real one installed (CI builds it),
two more run: voacapl's own sample circuit against its published output (point
EMCOMM_VOACAP_SRC at the voacapl source), and predictions that should look like HF does.

Run: python3 tests/test_voacap.py
"""

import importlib.machinery
import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/launcher/files/emcomm-voacap")


def load():
    loader = importlib.machinery.SourceFileLoader("emcomm_voacap", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_voacap", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


voacap = load()
REAL = shutil.which("voacapl") and os.path.isdir(voacap.SHARE)
if os.environ.get("EMCOMM_VOACAP_REQUIRED") and not REAL:
    sys.exit(f"voacapl or {voacap.SHARE} is missing, and EMCOMM_VOACAP_REQUIRED is set")


def output(hours=range(1, 25), rel=lambda hour, n: 0.5, muf=lambda hour: 14.5):
    """Method 30 output as voacapl prints it, for the planner's ten frequencies."""
    freqs = [f for _b, f in voacap.BANDS] + [0.0]
    lines = ["  IONOSPHERIC COMMUNICATIONS ANALYSIS AND PREDICTION PROGRAM", " METHOD 30", ""]
    for hour in hours:
        lines.append(f"{hour:6.1f}{muf(hour):5.1f}" + "".join(f"{f:5.1f}" for f in freqs) + " FREQ")
        lines.append("        1F2" + "  1F2" * 10 + "   -  MODE")
        snr = "".join(f"{40 + n:5d}" for n in range(10))
        lines.append(f"     {45:5d}{snr}    -  SNR")
        lines.append("      " + "".join(f"{rel(hour, n):5.2f}" for n in range(-1, 10)) + "    -  REL")
        lines.append(f"     {1:5d}" + "".join(f"{n:5d}" for n in range(10)) + "    -  SNRxx")
        lines.append("")
    return "\n".join(lines) + "\n"


FAKE = """#!/usr/bin/env python3
import os, sys
sys.path.insert(0, {tests!r})
import test_voacap
args = sys.argv[1:]
assert args[0] == "-s" and args[1].startswith("--run-dir="), args
run_dir, root, deck, out = args[1][10:], args[2], args[3], args[4]
assert os.path.isdir(os.path.join(root, "antennas", "samples")), root
with open(os.path.join(run_dir, deck)) as f:
    text = f.read()
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "decks"), "a") as f:
    f.write(text + "\\f")
if "FAIL" in os.environ.get("FAKE_VOACAP", ""):
    print("Input deck error -- bad card"); sys.exit(0)
with open(os.path.join(run_dir, out), "w") as f:
    f.write(test_voacap.output(rel=lambda h, n: round(0.1 * (n + 1) * (h % 2), 2)))
"""


class Cards(unittest.TestCase):
    def test_circuit_as_in_voacapls_sample(self):
        card = f"CIRCUIT   {voacap.latlon_card(35.80, -5.90, True)}{voacap.latlon_card(44.90, 20.50, False)}  S     0"
        self.assertEqual(card, "CIRCUIT   35.80N     5.90W    44.90N    20.50E  S     0")
        self.assertEqual(voacap.latlon_card(-33.87, 151.21, False), "    33.87S   151.21E")

    def test_deck(self):
        text = voacap.deck((42.36, -71.06), (51.51, -0.13), "2026-10", 104.4, "ssb", "residential", 100,
                           "emcomm/dipole10.ant")
        lines = text.splitlines()
        self.assertIn("MONTH      202610.00", lines)
        self.assertIn("SUNSPOT    104.", lines)
        self.assertIn("SYSTEM       1. 145. 0.10  90. 44.0 3.00 0.10", lines)
        self.assertIn("ANTENNA       1    1    2   30     0.000[emcomm/dipole10.ant  ]  0.0    0.1000", lines)
        self.assertIn("ANTENNA       2    2    2   30     0.000[emcomm/dipole10.ant  ]  0.0    0.0000", lines)
        self.assertIn("FREQUENCY  1.90 3.60 5.36 7.1010.1214.1018.1021.2024.9428.30 0.00", lines)
        self.assertEqual(lines[-2:], ["EXECUTE", "QUIT"])
        # voacapl reads by column: the ANTENNA card's file name sits between columns 41 and 61.
        card = next(line for line in lines if line.startswith("ANTENNA       1"))
        self.assertEqual((card[40], card[62]), ("[", "]"))
        self.assertEqual(voacap.deck((0, 0), (1, 1), "2027-03", 999, "cw", "quiet", 5, "x").splitlines()[4:6],
                         ["MONTH      2027 3.00", "SUNSPOT    300."])

    def test_antenna_files(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        self.assertEqual(voacap.antenna_file(root, "isotropic", 0), "samples/sample.00")
        name = voacap.antenna_file(root, "dipole", 5.0)
        self.assertEqual(name, "emcomm/dipole5.ant")
        self.assertLessEqual(len(name), 21)
        with open(os.path.join(root, "antennas", name)) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines[3].split()[0], "23")  # ITSA-1 horizontal dipole
        self.assertEqual(lines[8].split()[0], "5.00")  # metres; the length is in wavelengths
        self.assertEqual(lines[7].split()[0], "-.50")


class Output(unittest.TestCase):
    def test_parse(self):
        hours = voacap.parse(output(rel=lambda h, n: 0.9 if n == 5 and h == 15 else 0.05))
        self.assertEqual([h["utc"] for h in hours], list(range(24)))  # hour 24 is 00 UTC
        at15 = hours[15]
        self.assertEqual(at15["muf"], 14.5)
        self.assertEqual(at15["rel"][5], 0.9)  # 20 m
        self.assertEqual(at15["rel"][0], 0.05)
        self.assertEqual(len(at15["rel"]), 10)
        self.assertEqual(at15["snr"], [40.0 + n for n in range(10)])

    def test_rows_that_look_alike(self):
        self.assertIsNone(voacap.numbers("   1.0 2.0 SNR LW", "SNR"))
        self.assertIsNone(voacap.numbers("       45   40   41  SNRxx", "SNR"))
        self.assertEqual(voacap.numbers("   1" + "    2" * 9 + "   -    -  SNR", "SNR")[-1], None)


class Places(unittest.TestCase):
    def test_path(self):
        km, heading = voacap.path(42.36, -71.06, 51.51, -0.13)  # Boston to London
        self.assertAlmostEqual(km, 5265, delta=15)
        self.assertAlmostEqual(heading, 53, delta=1)
        lat, lon = voacap.offset(42.36, -71.06, 250)
        self.assertAlmostEqual(voacap.path(42.36, -71.06, lat, lon)[0], 250, delta=0.5)

    def test_targets(self):
        rows = voacap.targets((42.36, -71.06))
        ids = [r["id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("us:MA", ids)
        self.assertIn("dx:london", ids)
        self.assertTrue(all(-90 <= r["lat"] <= 90 and -180 <= r["lon"] <= 180 for r in rows))
        self.assertEqual(sum(1 for r in rows if r["group"] == "United States"), 54)
        grid = voacap.find_target("grid:io91wm", (42.36, -71.06))
        self.assertEqual(grid["name"], "Grid IO91wm")
        self.assertAlmostEqual(grid["lat"], 51.5, delta=0.1)
        with self.assertRaises(voacap.PlanError):
            voacap.find_target("grid:ZZ99", None)
        with self.assertRaises(voacap.PlanError):
            voacap.find_target("dx:atlantis", None)

    def test_sunspots(self):
        self.assertEqual(voacap.estimate_ssn("2026-01"), 118)
        self.assertAlmostEqual(voacap.estimate_ssn("2026-10"), 92, delta=0.1)  # 100 → 84 over six months
        self.assertEqual(voacap.estimate_ssn("2020-01"), 150)
        self.assertEqual(voacap.estimate_ssn("2040-01"), 11)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        cycle = os.path.join(tmp, "cycle.json")
        old = voacap.CYCLE
        voacap.CYCLE = cycle
        self.addCleanup(setattr, voacap, "CYCLE", old)
        self.assertTrue(voacap.sunspots("2026-10")[1].startswith("built-in estimate"))
        with open(cycle, "w") as f:
            json.dump({"updated": 1792000000, "data": [{"month": "2026-10", "ssn": 97.6}]}, f)
        self.assertEqual(voacap.sunspots("2026-10"), (98, "NOAA forecast from 2026-10-14"))
        self.assertTrue(voacap.sunspots("2027-10")[1].startswith("built-in estimate"))


class Planning(unittest.TestCase):
    """emcomm-voacap plan end to end, with a stand-in voacapl."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        share = os.path.join(self.tmp, "share")
        for folder in ("antennas/samples", "database", "coeffs", "run"):
            os.makedirs(os.path.join(share, folder))
        for name in ("antennas/samples/sample.00", "database/voacap.def", "database/cirafp.911", "coeffs/ccir.asc"):
            with open(os.path.join(share, name), "w") as f:
                f.write("data\n")
        station = os.path.join(self.tmp, "station.json")
        with open(station, "w") as f:
            json.dump({"grid": "FN42"}, f)
        fake = os.path.join(self.tmp, "voacapl")
        with open(fake, "w") as f:
            f.write(FAKE.format(tests=os.path.dirname(os.path.abspath(__file__))))
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IEXEC)
        self.fake, self.share, self.work = fake, share, os.path.join(self.tmp, "work")
        old = (voacap.STATION_PATH, voacap.CYCLE)
        voacap.STATION_PATH, voacap.CYCLE = station, os.path.join(self.tmp, "none.json")
        self.addCleanup(lambda: (setattr(voacap, "STATION_PATH", old[0]), setattr(voacap, "CYCLE", old[1])))

    def plan(self, place, **kw):
        return voacap.plan(place, voacapl=self.fake, share=self.share, work=self.work, **kw)

    def test_plan(self):
        result = self.plan("dx:london", month="2026-10", mode="winlink", antenna="dipole15", power=50)
        self.assertEqual(result["from"]["grid"], "FN42")
        self.assertEqual(result["to"]["name"], "London, England")
        self.assertAlmostEqual(result["km"], 5240, delta=80)
        self.assertEqual(result["ssn"], 92)
        self.assertTrue(result["ssn_source"].startswith("built-in"))
        self.assertEqual(len(result["hours"]), 24)
        self.assertEqual(result["hours"][1]["rel"][9], 1.0)  # odd hours open, in the stand-in
        self.assertEqual(result["hours"][2]["rel"][9], 0.0)
        with open(os.path.join(self.tmp, "decks")) as f:
            deck = f.read()
        self.assertIn("SYSTEM       1. 145. 0.10  90. 32.0 3.00 0.10", deck)
        self.assertIn("[emcomm/dipole15.ant  ]  0.0    0.0500", deck)
        root = os.path.join(self.work, "itshfbc")
        self.assertTrue(os.path.islink(os.path.join(root, "coeffs")))
        self.assertTrue(os.path.islink(os.path.join(root, "antennas", "samples")))
        self.assertFalse(os.path.islink(os.path.join(root, "database", "voacap.def")))  # VOACAP writes there
        self.assertTrue(os.path.isfile(os.path.join(root, "antennas", "emcomm", "dipole15.ant")))
        self.assertEqual([n for n in os.listdir(self.work) if n.startswith("run")], [])  # run folder removed

    def test_typed_ssn_and_grid(self):
        result = self.plan("grid:IO91", ssn=150)
        self.assertEqual((result["ssn"], result["ssn_source"]), (150, "typed in"))
        self.assertEqual(result["to"]["group"], "Grid square")

    def test_failures(self):
        os.environ["FAKE_VOACAP"] = "FAIL"
        self.addCleanup(os.environ.pop, "FAKE_VOACAP", None)
        with self.assertRaisesRegex(voacap.PlanError, "didn't finish: Input deck error"):
            self.plan("us:CA")
        with self.assertRaisesRegex(voacap.PlanError, "isn't installed"):
            voacap.plan("us:CA", voacapl=os.path.join(self.tmp, "nothing"), share=self.share, work=self.work)
        with self.assertRaisesRegex(voacap.PlanError, "isn't a month"):
            self.plan("us:CA", month="2026-13")
        with open(voacap.STATION_PATH, "w") as f:
            json.dump({}, f)
        with self.assertRaisesRegex(voacap.PlanError, "grid square"):
            self.plan("us:CA")


@unittest.skipUnless(REAL, "voacapl isn't installed")
class RealVoacap(unittest.TestCase):
    """The real voacapl: its own sample circuit, then planner predictions."""

    @unittest.skipUnless(os.environ.get("EMCOMM_VOACAP_SRC"), "EMCOMM_VOACAP_SRC isn't set")
    def test_voacapls_sample_matches_its_published_output(self):
        sample = os.path.join(os.environ["EMCOMM_VOACAP_SRC"], "tests", "p2p")
        work = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work)
        root = voacap.prepare_root(voacap.SHARE, work)
        shutil.copy(os.path.join(sample, "test01.dat"), work)
        import subprocess
        subprocess.run(["voacapl", "-s", f"--run-dir={work}", root, "test01.dat", "test01.out"], check=True,
                       timeout=120)
        with open(os.path.join(work, "test01.out")) as f:
            got = voacap.parse(f.read(), nbands=9)
        with open(os.path.join(sample, "test01.out")) as f:
            want = voacap.parse(f.read(), nbands=9)
        self.assertEqual(len(want), 24)
        for g, w in zip(got, want):
            self.assertAlmostEqual(g["muf"], w["muf"], delta=0.11, msg=f"MUF at {w['utc']}Z")
            for n in range(9):
                self.assertAlmostEqual(g["rel"][n], w["rel"][n], delta=0.011, msg=f"REL at {w['utc']}Z, {n}")
                self.assertAlmostEqual(g["snr"][n], w["snr"][n], delta=1.01, msg=f"SNR at {w['utc']}Z, {n}")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        station = os.path.join(self.tmp, "station.json")
        with open(station, "w") as f:
            json.dump({"grid": "FN42"}, f)
        old = voacap.STATION_PATH
        voacap.STATION_PATH = station
        self.addCleanup(setattr, voacap, "STATION_PATH", old)

    def plan(self, place, **kw):
        return voacap.plan(place, month="2026-10", ssn=100, work=os.path.join(self.tmp, "work"), **kw)

    @staticmethod
    def best(hour):
        return max(range(10), key=lambda n: hour["rel"][n] or 0)

    def test_transatlantic_daytime_on_the_high_bands(self):
        hours = self.plan("dx:london")["hours"]
        noon = hours[15]  # 11 am in Boston, 3 pm in London
        self.assertGreater(noon["muf"], 18)
        self.assertIn(voacap.BANDS[self.best(noon)][0], ("20 m", "17 m", "15 m", "12 m", "10 m"))
        self.assertLess(noon["rel"][0], 0.2)  # 160 m is absorbed by day
        night = hours[4]
        self.assertLess(night["muf"], noon["muf"])
        self.assertIn(voacap.BANDS[self.best(night)][0], ("160 m", "80 m", "60 m", "40 m", "30 m", "20 m"))

    def test_nvis_at_night_is_on_the_low_bands(self):
        result = self.plan("near:250", antenna="dipole5", mode="winlink")
        self.assertEqual(result["km"], 250)
        night = result["hours"][6]  # 2 am in Boston
        self.assertIn(voacap.BANDS[self.best(night)][0], ("160 m", "80 m", "60 m", "40 m"))
        self.assertLess(night["rel"][9], 0.1)  # nothing on 10 m that close
        for mode in ("ssb", "ft8"):
            self.assertEqual(len(self.plan("near:100", mode=mode)["hours"]), 24)
        for antenna in voacap.ANTENNAS:
            self.assertEqual(len(self.plan("us:CA", antenna=antenna)["hours"]), 24)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    unittest.main()
