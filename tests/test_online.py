"""Check emcomm-online's readers against sample answers from each service, and
that it keeps the last good answer and its rate limits.

Run: python3 tests/test_online.py
"""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/launcher/files/emcomm-online")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_online", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_online", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


online = load_helper()

NWS = {"features": [
    {"properties": {"event": "Wind Advisory", "severity": "Minor", "headline": "Wind Advisory until 6 PM",
                    "areaDesc": "Suffolk", "expires": "2026-10-19T22:00:00-04:00", "description": "Gusts 45 mph."}},
    {"properties": {"event": "Flood Warning", "severity": "Severe", "headline": "Flood Warning",
                    "areaDesc": "Middlesex", "ends": "2026-10-20T10:00:00-04:00", "instruction": "Turn around."}},
]}

KP_ROWS = [["time_tag", "Kp", "a_running", "station_count"],
           ["2026-10-19 12:00:00.000", "2.33", "9", "8"],
           ["2026-10-19 15:00:00.000", "3.67", "22", "8"]]
KP_OBJECTS = [{"time_tag": "2026-10-19T12:00:00", "Kp": 2.33}, {"time_tag": "2026-10-19T15:00:00", "Kp": 4.0}]

SCALES = {"0": {"DateStamp": "2026-10-19", "R": {"Scale": "1", "Text": "minor"},
                "S": {"Scale": "0", "Text": "none"}, "G": {"Scale": None, "Text": None}}}

HAMQSL = """<?xml version="1.0" encoding="ISO-8859-1"?>
<solar><solardata>
 <source url="http://www.hamqsl.com/solar.html">N0NBH</source>
 <updated> 19 Oct 2026 1800 GMT</updated>
 <solarflux>145</solarflux><aindex>8</aindex><kindex>2</kindex><xray>B6.1</xray>
 <sunspots>120</sunspots><geomagfield>QUIET</geomagfield><signalnoise>S1-S2</signalnoise>
 <calculatedconditions>
  <band name="80m-40m" time="day">Fair</band><band name="30m-20m" time="day">Good</band>
  <band name="80m-40m" time="night">Good</band><band name="30m-20m" time="night">Good</band>
 </calculatedconditions>
 <calculatedvhfconditions>
  <phenomenon name="vhf-aurora" location="northern_hemi">Band Closed</phenomenon>
 </calculatedvhfconditions>
</solardata></solar>"""

PSK = """<?xml version="1.0" encoding="UTF-8"?>
<receptionReports currentSeconds="1760900000">
 <activeReceiver callsign="K1XYZ" locator="FN42" />
 <receptionReport receiverCallsign="K1XYZ" receiverLocator="FN42ab" senderCallsign="AC1SB"
   senderLocator="FN31pr" frequency="14075123" flowStartSeconds="1760899000" mode="FT8" sNR="-12" />
 <receptionReport receiverCallsign="K1XYZ" receiverLocator="FN42ab" senderCallsign="AC1SB"
   frequency="14075200" flowStartSeconds="1760899600" mode="FT8" sNR="-5" />
 <receptionReport receiverCallsign="G4ABC" receiverLocator="IO91" senderCallsign="AC1SB"
   frequency="7078000" flowStartSeconds="1760898000" mode="JS8" />
</receptionReports>"""

QRZ_LOGIN = """<?xml version="1.0" ?><QRZDatabase version="1.34" xmlns="http://xmldata.qrz.com">
<Session><Key>abc123</Key><Count>1</Count><SubExp>non-subscriber</SubExp></Session></QRZDatabase>"""
QRZ_FOUND = """<?xml version="1.0" ?><QRZDatabase version="1.34" xmlns="http://xmldata.qrz.com">
<Callsign><call>W1AW</call><fname>Hiram</fname><name>Maxim</name><addr2>Newington</addr2><state>CT</state>
<country>United States</country><grid>FN31pq</grid><lat>41.714775</lat><lon>-72.727260</lon></Callsign>
<Session><Key>abc123</Key><SubExp>non-subscriber</SubExp></Session></QRZDatabase>"""
QRZ_NOTFOUND = """<?xml version="1.0" ?><QRZDatabase version="1.34" xmlns="http://xmldata.qrz.com">
<Session><Error>Not found: ZZ9ZZZ</Error><Key>abc123</Key></Session></QRZDatabase>"""

HAMQTH_FOUND = """<?xml version="1.0"?><HamQTH version="2.8" xmlns="https://www.hamqth.com">
<search><callsign>ok2cqr</callsign><nick>Petr</nick><qth>Neratovice</qth><country>Czech Republic</country>
<grid>jo70gg</grid><adr_name>Petr Hlozek</adr_name><latitude>50.07</latitude><longitude>14.42</longitude></search>
</HamQTH>"""


class Parsers(unittest.TestCase):
    def test_nws_alerts_most_severe_first(self):
        alerts = online.parse_nws(NWS)
        self.assertEqual([a["event"] for a in alerts], ["Flood Warning", "Wind Advisory"])
        self.assertEqual(alerts[0]["instruction"], "Turn around.")
        self.assertEqual(alerts[1]["ends"], "2026-10-19T22:00:00-04:00")

    def test_kp_in_either_shape(self):
        self.assertEqual(online.parse_kp(KP_ROWS)[0], 3.67)
        self.assertEqual(online.parse_kp(KP_OBJECTS), (4.0, "2026-10-19T15:00:00"))
        self.assertEqual(online.parse_kp([]), (None, None))

    def test_flux_and_scales(self):
        self.assertEqual(online.parse_flux({"Flux": "152", "TimeStamp": "x"}), 152)
        self.assertEqual(online.parse_flux([{"flux": 140.2}]), 140)
        scales = online.parse_scales(SCALES)
        self.assertEqual(scales["R"], {"level": 1, "text": "minor"})
        self.assertNotIn("G", scales)

    def test_hamqsl_bands(self):
        data = online.parse_hamqsl(ET.fromstring(HAMQSL.encode("latin-1")))
        self.assertEqual(data["sfi"], "145")
        self.assertEqual(data["bands"]["80m-40m"], {"day": "Fair", "night": "Good"})
        self.assertEqual(data["vhf"][0]["state"], "Band Closed")

    def test_pskreporter_latest_per_receiver(self):
        heard = online.parse_pskreporter(ET.fromstring(PSK))
        self.assertEqual([h["call"] for h in heard], ["K1XYZ", "G4ABC"])
        self.assertEqual(heard[0]["snr"], -5)
        self.assertEqual(heard[0]["freq"], 14075200)
        self.assertIsNone(heard[1]["snr"])

    def test_aprsfi(self):
        pos = online.parse_aprsfi({"result": "ok", "found": 1, "entries": [
            {"name": "AC1SB-9", "lat": "42.1", "lng": "-71.2", "lasttime": "1760899000", "comment": "mobile"}]})
        self.assertEqual((pos["lat"], pos["lon"], pos["time"]), (42.1, -71.2, 1760899000))
        with self.assertRaises(online.OnlineError):
            online.parse_aprsfi({"result": "fail", "description": "bad key"})


class WithHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        online.CACHE_DIR = os.path.join(self.tmp.name, "cache")
        online.ACCOUNTS_PATH = os.path.join(self.tmp.name, "accounts.json")
        online.STATION_PATH = os.path.join(self.tmp.name, "station.json")
        with open(online.STATION_PATH, "w") as f:
            json.dump({"callsign": "AC1SB", "grid": "FN42"}, f)
        self.saved = dict(online.FETCHERS), online.get_xml, online.get_json

    def tearDown(self):
        online.FETCHERS.clear()
        online.FETCHERS.update(self.saved[0])
        online.get_xml, online.get_json = self.saved[1], self.saved[2]
        self.tmp.cleanup()

    def set_accounts(self, **values):
        with open(online.ACCOUNTS_PATH, "w") as f:
            json.dump(values, f)


class Refresh(WithHome):
    def test_keeps_last_good_answer_and_waits_between_tries(self):
        answers = [["first"], online.OnlineError("no internet connection")]

        def fake():
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        online.FETCHERS["alerts"] = fake
        record = online.refresh("alerts", now=1000)
        self.assertEqual(record["data"], ["first"])
        # Too soon: not fetched again, even when forced.
        online.refresh("alerts", force=True, now=1010)
        self.assertEqual(len(answers), 1)
        record = online.refresh("alerts", force=True, now=1100)
        self.assertEqual(record["data"], ["first"])
        self.assertEqual(record["updated"], 1000)
        self.assertIn("no internet", record["error"])

    def test_pskreporter_five_minutes_even_when_forced(self):
        calls = []
        online.FETCHERS["heard"] = lambda: calls.append(1) or []
        online.refresh("heard", now=1000)
        online.refresh("heard", force=True, now=1200)
        self.assertEqual(len(calls), 1)
        online.refresh("heard", force=True, now=1301)
        self.assertEqual(len(calls), 2)



class AlertMap(WithHome):
    POLYGON = {"type": "Polygon", "coordinates": [[[-73.1, 43.0], [-73.0, 43.0], [-73.0, 43.1], [-73.1, 43.0]]]}
    ZONE = {"type": "MultiPolygon", "coordinates": [[[[-72.51234, 44.0], [-72.4, 44.0], [-72.4, 44.2],
                                                      [-72.5, 44.2]]], [[[-71.0, 44.0], [-71.0, 44.1]]]]}
    DOC = {"features": [
        {"geometry": POLYGON, "properties": {"event": "Severe Thunderstorm Warning", "severity": "Severe",
                                              "areaDesc": "Bennington, VT", "ends": "2026-10-20T19:00:00-04:00"}},
        {"geometry": None, "properties": {"event": "Wind Advisory", "severity": "Minor", "areaDesc": "Orange",
                                          "affectedZones": ["https://api.weather.gov/zones/forecast/VTZ010"]}},
        {"geometry": None, "properties": {"event": "Special Marine Warning", "severity": "Moderate",
                                          "affectedZones": ["https://api.weather.gov/zones/forecast/ANZ999x"]}},
    ]}

    def test_storm_polygons_and_zone_outlines(self):
        asked = []

        def fake_get(url, params=None, headers=None):
            asked.append(url)
            if "/points/" in url:
                return {"properties": {"relativeLocation": {"properties": {"state": "VT"}}}}
            if "/alerts/active" in url:
                return self.DOC
            return {"geometry": self.ZONE}

        online.get_json = fake_get
        data = online.fetch_alertmap()
        self.assertEqual(data["states"], "VT,MA,NH,NY")
        self.assertIn("area=VT,MA,NH,NY", asked[1])
        events = [a["event"] for a in data["alerts"]]
        self.assertEqual(events, ["Wind Advisory", "Severe Thunderstorm Warning"])  # worst drawn last
        wind = data["alerts"][0]
        self.assertEqual(wind["rings"], [[[44.0, -72.512], [44.0, -72.4], [44.2, -72.4], [44.2, -72.5]]])
        # The zone and the state are kept: asked once.
        online.fetch_alertmap()
        self.assertEqual(sum(1 for u in asked if "/zones/" in u), 1)
        self.assertEqual(sum(1 for u in asked if "/points/" in u), 1)

    def test_the_map_gets_a_script(self):
        online.FETCHERS["alertmap"] = lambda: {"states": "VT", "alerts": []}
        online.refresh("alertmap", now=1000)
        with open(os.path.join(online.CACHE_DIR, "alertmap.js")) as f:
            self.assertTrue(f.read().startswith("window.ALERTMAP = {"))


class Lookup(WithHome):
    def test_qrz_then_saved_copy_when_offline(self):
        self.set_accounts(qrz_user="AC1SB", qrz_password="secret")
        replies = [QRZ_LOGIN, QRZ_FOUND]
        online.get_xml = lambda url, params=None, headers=None: ET.fromstring(replies.pop(0))
        result = online.lookup("w1aw")
        self.assertEqual((result["source"], result["name"], result["grid"]), ("QRZ", "Hiram Maxim", "FN31pq"))
        self.assertIn("non-subscribers", result["note"])
        self.assertGreater(result["miles"], 0)

        def offline(*_a, **_k):
            raise online.OnlineError("no internet connection")

        online.get_xml = offline
        result = online.lookup("W1AW")
        self.assertTrue(result["cached"])
        self.assertEqual(result["name"], "Hiram Maxim")

    def test_qrz_not_found(self):
        self.set_accounts(qrz_user="AC1SB", qrz_password="secret")
        replies = [QRZ_LOGIN, QRZ_NOTFOUND]
        online.get_xml = lambda url, params=None, headers=None: ET.fromstring(replies.pop(0))
        self.assertTrue(online.lookup("ZZ9ZZZ")["notfound"])

    def test_hamqth_with_saved_session(self):
        self.set_accounts(hamqth_user="AC1SB", hamqth_password="secret")
        online.save_session("hamqth", {"id": "s1", "time": online.time.time()})
        online.get_xml = lambda url, params=None, headers=None: ET.fromstring(HAMQTH_FOUND)
        result = online.lookup("OK2CQR")
        self.assertEqual((result["source"], result["name"], result["grid"]), ("HamQTH", "Petr Hlozek", "JO70GG"))

    def test_no_accounts(self):
        result = online.lookup("W1AW")
        self.assertIn("Accounts", result["errors"][0])


if __name__ == "__main__":
    unittest.main()
