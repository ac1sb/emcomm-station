"""Check that emcomm-app-setup fills app settings from the station settings
and keeps what the operator set in the apps themselves.

Run: python3 tests/test_app_setup.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/apps/files/emcomm-app-setup")


class AppSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name
        self.station = os.path.join(self.home, "station.json")
        self.set_station(callsign="AC1SB", grid="FN31pr")
        self.allow(True)

    def allow(self, allowed, leave_alone=()):
        os.makedirs(os.path.join(self.home, ".config/emcomm"), exist_ok=True)
        with open(os.path.join(self.home, ".config/emcomm/app-radio.json"), "w") as f:
            json.dump({"allowed": allowed, "leave_alone": list(leave_alone)}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def set_station(self, **values):
        with open(self.station, "w") as f:
            json.dump(values, f)

    def run_helper(self, app, **extra):
        env = dict(os.environ, HOME=self.home, EMCOMM_STATION=self.station, **extra)
        result = subprocess.run([sys.executable, HELPER, app], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_pat_new_config(self):
        cfg = json.loads(self.read(self.run_helper("pat")))
        self.assertEqual(cfg["mycall"], "AC1SB")
        self.assertEqual(cfg["locator"], "FN31pr")
        self.assertEqual(cfg["hamlib_rigs"]["radio"], {"address": "127.0.0.1:4532", "network": "tcp"})
        for modem in ("ardop", "varahf", "varafm"):
            self.assertEqual(cfg[modem]["rig"], "radio")
            self.assertTrue(cfg[modem]["ptt_ctrl"])
        self.assertEqual(cfg["varahf"]["addr"], "localhost:8300")
        self.assertEqual(cfg["ax25"]["engine"], "agwpe")

    def test_pat_keeps_operator_settings_and_follows_callsign(self):
        path = os.path.join(self.home, ".config/pat/config.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({"mycall": "N0CALL", "secure_login_password": "secret",
                       "varahf": {"addr": "localhost:8400", "bandwidth": 500, "ptt_ctrl": False}}, f)
        self.set_station(callsign="W1AW", grid="FN31")
        cfg = json.loads(self.read(self.run_helper("pat")))
        self.assertEqual(cfg["mycall"], "W1AW")
        self.assertEqual(cfg["secure_login_password"], "secret")
        self.assertEqual(cfg["varahf"], {"addr": "localhost:8400", "bandwidth": 500, "ptt_ctrl": False,
                                         "rig": "radio"})

    def test_direwolf(self):
        conf = self.read(self.run_helper("direwolf"))
        self.assertIn("MYCALL AC1SB\n", conf)
        self.assertIn("ADEVICE pipewire\n", conf)
        self.assertIn("PTT RIG 2 localhost:4532\n", conf)
        self.assertIn("AGWPORT 8000\n", conf)

    def test_direwolf_custom_config_wins(self):
        custom = os.path.join(self.home, ".config/emcomm/direwolf.custom.conf")
        os.makedirs(os.path.dirname(custom), exist_ok=True)
        open(custom, "w").close()
        self.assertEqual(self.run_helper("direwolf"), custom)

    def test_js8call_new_config(self):
        path = self.run_helper("js8call")
        ini = self.read(path)
        for line in ("[Configuration]", "MyCall=AC1SB", "MyGrid=FN31pr", "Rig=Hamlib NET rigctl",
                     "CATNetworkPort=127.0.0.1:4532", "PTTMethod=PTT_method_CAT", "DataMode=data_mode_data",
                     "SplitMode=split_mode_emulate"):
            self.assertIn(line + "\n", ini)

    def test_wsjtx_keeps_operator_settings_and_backs_up(self):
        path = os.path.join(self.home, ".config/WSJT-X.ini")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        before = ("[General]\nRig=not this one\n\n[Configuration]\nMyCall=AC1SB\nRig=FLRig FLRig\n"
                  "SoundInName=USB Audio Device\nPTTMethod=PTT_method_RTS\nTxDelay=0.2\n\n[MainWindow]\nstate=1\n")
        with open(path, "w") as f:
            f.write(before)
        self.run_helper("wsjtx")
        ini = self.read(path)
        self.assertIn("[General]\nRig=not this one\n", ini)  # only [Configuration] is touched
        self.assertIn("Rig=Hamlib NET rigctl\n", ini)
        self.assertIn("PTTMethod=PTT_method_CAT\n", ini)
        self.assertIn("SoundInName=USB Audio Device\n", ini)  # sound cards are the operator's
        self.assertIn("TxDelay=0.2\n", ini)
        self.assertIn("[MainWindow]\nstate=1\n", ini)
        self.assertEqual(ini.count("Rig=Hamlib NET rigctl"), 1)
        section = ini.split("[Configuration]\n", 1)[1].split("\n[", 1)[0]
        self.assertIn("DataMode=data_mode_data", section)
        backups = os.listdir(os.path.join(self.home, ".local/state/emcomm/config-backups"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.read(os.path.join(self.home, ".local/state/emcomm/config-backups", backups[0])), before)
        # Nothing to change: no rewrite, no second backup.
        mtime = os.path.getmtime(path)
        self.run_helper("wsjtx")
        self.assertEqual(os.path.getmtime(path), mtime)
        self.assertEqual(len(os.listdir(os.path.join(self.home, ".local/state/emcomm/config-backups"))), 1)

    def test_vox_and_vhf_fm(self):
        self.set_station(callsign="AC1SB", grid="FN31", ptt_method="NONE", data_mode="none")
        ini = self.read(self.run_helper("wsjtx"))
        self.assertIn("PTTMethod=PTT_method_VOX\n", ini)
        self.assertIn("DataMode=data_mode_none\n", ini)
        self.assertIn("SplitMode=split_mode_none\n", ini)
        self.assertIn("<HAMLIBCMDPTT>0</HAMLIBCMDPTT>", self.read(self.run_helper("fldigi")))
        self.assertNotIn("PTT RIG", self.read(self.run_helper("direwolf")))

    def test_fldigi(self):
        path = self.run_helper("fldigi")
        self.assertTrue(path.endswith(".fldigi/fldigi_def.xml"))
        xml = self.read(path)
        for element in ("<CHKUSEHAMLIBIS>1</CHKUSEHAMLIBIS>", "<HAMRIGMODEL>2</HAMRIGMODEL>",
                        "<HAMRIGDEVICE>127.0.0.1:4532</HAMRIGDEVICE>", "<HAMLIBCMDPTT>1</HAMLIBCMDPTT>",
                        "<CHKUSEXMLRPCIS>0</CHKUSEXMLRPCIS>", "<MYCALL>AC1SB</MYCALL>", "<MYLOC>FN31pr</MYLOC>"):
            self.assertIn(element, xml)
        self.assertTrue(xml.rstrip().endswith("</FLDIGI_DEFS>"))
        with open(path, "w") as f:
            f.write("<?xml version=\"1.0\"?>\n<FLDIGI_DEFS>\n<WFREFLEVEL>-20</WFREFLEVEL>\n"
                    "<CHKUSEHAMLIBIS>0</CHKUSEHAMLIBIS>\n<CHKUSEXMLRPCIS>1</CHKUSEXMLRPCIS>\n</FLDIGI_DEFS>\n")
        xml = self.read(self.run_helper("fldigi"))
        self.assertIn("<WFREFLEVEL>-20</WFREFLEVEL>", xml)
        self.assertIn("<CHKUSEHAMLIBIS>1</CHKUSEHAMLIBIS>", xml)
        self.assertIn("<CHKUSEXMLRPCIS>0</CHKUSEXMLRPCIS>", xml)
        self.assertEqual(xml.count("CHKUSEHAMLIBIS>"), 2)

    def test_radio_writes_every_installed_app(self):
        bin_dir = os.path.join(self.home, "bin")
        os.makedirs(bin_dir)
        for program in ("wsjtx", "fldigi", "pat"):
            with open(os.path.join(bin_dir, program), "w") as f:
                f.write("#!/bin/sh\n")
            os.chmod(os.path.join(bin_dir, program), 0o755)
        self.allow(True, ["pat"])
        out = self.run_helper("radio", PATH=bin_dir)
        states = {r["app"]: r["state"] for r in map(json.loads, out.splitlines())}
        self.assertEqual(states, {"wsjtx": "updated", "js8call": "not installed", "fldigi": "updated",
                                  "pat": "left alone", "xastir": "not installed"})
        self.assertTrue(os.path.exists(os.path.join(self.home, ".config/WSJT-X.ini")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".config/pat/config.json")))
        out = self.run_helper("radio", PATH=bin_dir)
        states = {r["app"]: r["state"] for r in map(json.loads, out.splitlines())}
        self.assertEqual(states["wsjtx"], "unchanged")

    def test_nothing_changes_until_allowed(self):
        self.allow(False)
        path = self.run_helper("wsjtx")
        self.assertFalse(os.path.exists(path))
        self.assertFalse(os.path.exists(self.run_helper("fldigi")))
        self.assertFalse(os.path.exists(self.run_helper("pat")))
        states = {r["app"]: r["state"] for r in map(json.loads, self.run_helper("radio").splitlines())}
        self.assertEqual(set(states.values()), {"not allowed"})
        os.remove(os.path.join(self.home, ".config/emcomm/app-radio.json"))  # never asked: the same
        self.assertFalse(os.path.exists(self.run_helper("wsjtx")))
        # Emcomm-CNC's own Direwolf file and flmsg's UTC times aren't rig settings in another app.
        self.assertIn("MYCALL AC1SB", self.read(self.run_helper("direwolf")))

    def test_radio_skips_an_open_app(self):
        # A program named wsjtx that's running: it would write its own settings back on closing.
        bin_dir = os.path.join(self.home, "bin")
        os.makedirs(bin_dir)
        fake = os.path.join(bin_dir, "wsjtx")
        os.symlink("/bin/sleep", fake)
        proc = subprocess.Popen([fake, "30"])
        try:
            out = self.run_helper("radio", PATH=bin_dir)
        finally:
            proc.kill()
            proc.wait()
        states = {r["app"]: r["state"] for r in map(json.loads, out.splitlines())}
        self.assertEqual(states["wsjtx"], "open")
        self.assertFalse(os.path.exists(os.path.join(self.home, ".config/WSJT-X.ini")))

    def test_flmsg_uses_utc(self):
        path = self.run_helper("flmsg")
        prefs = self.read(path)
        self.assertTrue(path.endswith(".nbems/flmsg.prefs"))
        for line in ("[.]", "utc:2", "dtformat:0", "dt_fname:4", "UI_default:1", "UI_expert:1", "mycall:AC1SB"):
            self.assertIn(line + "\n", prefs)
        # flmsg's own settings stay; the operator's callsign wins; the time settings come back.
        with open(path, "w") as f:
            f.write("; FLTK preferences file format 1.0\n\n[.]\n\nmainx:50\nutc:0\nUI_expert:0\nmycall:W1AW\n")
        self.run_helper("flmsg")
        prefs = self.read(path)
        self.assertIn("mainx:50\n", prefs)
        self.assertIn("utc:2\n", prefs)
        self.assertNotIn("utc:0", prefs)
        self.assertIn("UI_expert:1\n", prefs)  # the Simple window has no forms to offer
        self.assertIn("mycall:W1AW\n", prefs)
        self.assertNotIn("AC1SB", prefs)
        self.assertEqual(prefs.count("utc:"), 1)

    def test_xastir_position_from_grid_and_agwpe_port(self):
        cnf = self.read(self.run_helper("xastir"))
        self.assertIn("STATION_CALLSIGN:AC1SB\n", cnf)
        self.assertIn("STATION_LAT:4143.750N\n", cnf)
        self.assertIn("STATION_LONG:07242.500W\n", cnf)
        self.assertIn("DEVICE0_TYPE:12\n", cnf)
        self.assertIn("DEVICE0_SPEED:8000\n", cnf)

    def test_xastir_uses_the_aprs_radio_when_plugged_in(self):
        card = os.path.join(self.home, "aprsaudio")
        open(card, "w").close()
        cnf = self.read(self.run_helper("xastir", EMCOMM_APRS_CARD=card))
        self.assertIn("DEVICE0_SPEED:8010\n", cnf)
        os.remove(card)  # unplugged: back to the main radio's Direwolf
        cnf = self.read(self.run_helper("xastir", EMCOMM_APRS_CARD=card)).splitlines()
        self.assertIn("DEVICE0_SPEED:8000", cnf)
        self.assertEqual(sum(line.startswith("DEVICE0_SPEED:") for line in cnf), 1)

    def test_xastir_keeps_operator_interfaces(self):
        path = os.path.join(self.home, ".xastir/config/xastir.cnf")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("STATION_CALLSIGN:N0CALL\nDEVICE0_TYPE:1\nDEVICE0_SPEED:9600\nMAP_BGCOLOR:3\n")
        self.set_station(callsign="w1aw", grid="FN31")
        cnf = self.read(self.run_helper("xastir")).splitlines()
        self.assertIn("STATION_CALLSIGN:W1AW", cnf)
        self.assertNotIn("STATION_CALLSIGN:N0CALL", cnf)
        self.assertIn("DEVICE0_SPEED:9600", cnf)
        self.assertIn("MAP_BGCOLOR:3", cnf)
        self.assertNotIn("DEVICE0_TYPE:12", cnf)


if __name__ == "__main__":
    unittest.main()
