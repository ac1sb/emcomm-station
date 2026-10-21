"""Tests for emcomm-map-prepare's US town names (Census gazetteer files)."""

import importlib.machinery
import importlib.util
import json
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


SQUARE = [[0, 0], [0.0005, 0.5], [0, 1], [1, 1], [1, 0.0004], [1, 0], [0, 0]]


class Simplify(unittest.TestCase):
    def test_points_off_the_line_by_less_than_the_tolerance_go(self):
        self.assertEqual(mp.simplify_line(SQUARE, 0.002), [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]])
        self.assertEqual(mp.simplify_line(SQUARE, 0), SQUARE)
        self.assertEqual(mp.simplify_line([[0, 0], [1, 1]], 0.1), [[0, 0], [1, 1]])
        # A real bend stays.
        bent = [[0, 0], [0.5, 0.3], [1, 0]]
        self.assertEqual(mp.simplify_line(bent, 0.1), bent)

    def test_every_depth_of_geometry(self):
        self.assertEqual(mp.simplified([1.5, 2.5], 0.1), [1.5, 2.5])
        self.assertEqual(mp.simplified([[SQUARE], [SQUARE]], 0.002)[1][0][1], [0, 1])

    def test_writes_the_base_map_and_the_detail_apart(self):
        feature = {"type": "Feature", "properties": {"NAME": "A", "REGION": "B", "type": "Major Highway",
                                                     "continent": "North America", "name": "A", "scalerank": 1},
                   "geometry": {"type": "LineString", "coordinates": SQUARE}}
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("ne_50m_admin_0_countries", "ne_50m_lakes", "ne_50m_admin_1_states_provinces_lines",
                         "ne_10m_admin_2_counties", "ne_10m_roads", "ne_10m_populated_places_simple"):
                with open(os.path.join(tmp, name + ".geojson"), "w", encoding="utf-8") as f:
                    json.dump({"type": "FeatureCollection", "features": [feature]}, f)
            dest = os.path.join(tmp, "out", "basemap.js")
            os.makedirs(os.path.dirname(dest))
            self.assertEqual(mp.main([tmp, dest]), 0)
            with open(dest, encoding="utf-8") as f:
                base = f.read()
            with open(os.path.join(tmp, "out", "basemap-detail.js"), encoding="utf-8") as f:
                detail = f.read()
        self.assertTrue(base.startswith("window.BASEMAP = {"))
        self.assertTrue(detail.startswith("window.BASEMAP_DETAIL = {"))
        base, detail = json.loads(base[len("window.BASEMAP = "):-2]), json.loads(detail[len("window.BASEMAP_DETAIL = "):-2])
        self.assertEqual(sorted(base), ["countries", "lakes", "places", "states", "towns"])
        self.assertEqual(sorted(detail), ["counties", "roads"])
        self.assertEqual(detail["counties"]["features"][0]["geometry"]["coordinates"],
                         [[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]])
        self.assertEqual(len(base["places"]["features"][0]["geometry"]["coordinates"]), len(SQUARE))


if __name__ == "__main__":
    unittest.main()
