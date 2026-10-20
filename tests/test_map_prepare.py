"""Tests for emcomm-map-prepare's US town names (Census gazetteer files)."""

import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/apps/files/emcomm-map-prepare")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_map_prepare", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_map_prepare", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


mp = load_helper()
HEADER = ("USPS\tGEOID\tGEOIDFQ\tANSICODE\tNAME\tLSAD\tFUNCSTAT\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI"
          "\tINTPTLAT\tINTPTLONG                  \n")


def gazetteer(folder, kind, rows):
    with zipfile.ZipFile(os.path.join(folder, f"2024_Gaz_{kind}_national.zip"), "w") as z:
        z.writestr(f"2024_Gaz_{kind}_national.txt", HEADER + "".join(
            f"{st}\t1\tx\t0\t{name}\t25\t{fs}\t0\t0\t0\t0\t{lat}\t{lon}\n" for st, name, fs, lat, lon in rows))


class Towns(unittest.TestCase):
    def test_names_tiers_and_new_england_towns(self):
        with tempfile.TemporaryDirectory() as tmp:
            gazetteer(tmp, "place", [("VT", "Manchester village", "A", 43.1637, -73.0722),
                                     ("VT", "Manchester Center CDP", "S", 43.1770, -73.0571),
                                     ("VT", "Rutland city", "A", 43.6106, -72.9726),
                                     ("NH", "Manchester city", "A", 42.9956, -71.4548)])
            gazetteer(tmp, "cousubs", [("VT", "Manchester town", "A", 43.1650, -73.0750),
                                       ("VT", "Dorset town", "A", 43.2548, -73.0973),
                                       ("PA", "Adams township", "A", 40.0, -77.0),
                                       ("VT", "Avery's gore", "F", 44.9, -72.5)])
            towns = mp.towns(tmp)
        names = sorted((t[2], t[3]) for t in towns)
        self.assertEqual(names, [("Dorset", 1), ("Manchester", 1), ("Manchester", 1),
                                 ("Manchester Center", 2), ("Rutland", 1)])
        # Manchester, VT once (the town); Manchester, NH is a different place.
        self.assertEqual(len([t for t in towns if t[2] == "Manchester" and t[1] < -72]), 1)

    def test_no_census_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(mp.towns(tmp), [])


if __name__ == "__main__":
    unittest.main()
