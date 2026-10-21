"""Check emcomm-backup keeps the station's files, leaves out passwords, and
restores only into the home folder.

Run: python3 tests/test_backup.py
"""

import importlib.machinery
import importlib.util
import io
import json
import os
import tarfile
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/launcher/files/emcomm-backup")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_backup", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_backup", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


backup = load_helper()


def write(path, text="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


class Backup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.stick = os.path.join(self.tmp.name, "stick")
        self.station = os.path.join(self.tmp.name, "station.json")
        write(self.station, json.dumps({"callsign": "AC1SB"}))
        for rel in (".local/share/emcomm/contacts.log", ".local/share/emcomm/nets/20261019-220000.json",
                    "ICS forms/ICS-309.html", ".config/emcomm/accounts.json", ".config/emcomm/theme",
                    ".config/WSJT-X.ini", ".local/share/WSJT-X/ALL.TXT", ".config/pat/config.json"):
            write(os.path.join(self.home, rel), rel)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_without_passwords(self):
        path = backup.create(self.stick, self.home, self.station, now=1792447200)
        self.assertEqual(os.path.basename(path), "emcomm-backup-AC1SB-20261019-2200Z.tar.gz")
        self.assertEqual(backup.backups(self.stick), [path])
        with tarfile.open(path) as tar:
            names = tar.getnames()
        self.assertIn("station.json", names)
        self.assertIn("home/.local/share/emcomm/nets/20261019-220000.json", names)
        self.assertIn("home/ICS forms/ICS-309.html", names)
        self.assertNotIn("home/.config/emcomm/accounts.json", names)
        self.assertNotIn("home/.config/pat/config.json", names)
        self.assertNotIn("home/.local/share/WSJT-X/ALL.TXT", names)

        fresh = os.path.join(self.tmp.name, "fresh")
        report, _ok = backup.restore(path, fresh, apply_settings=False)
        self.assertIn("Restored 5 files", report)
        with open(os.path.join(fresh, ".local/share/emcomm/contacts.log")) as f:
            self.assertEqual(f.read(), ".local/share/emcomm/contacts.log")

    def test_restore_stays_in_home(self):
        evil = os.path.join(self.tmp.name, "emcomm-backup-X-20261019-2200Z.tar.gz")
        with tarfile.open(evil, "w:gz") as tar:
            for name in ("home/../outside.txt", "/etc/passwd-x", "home/ICS forms/ok.txt",
                         "home/.config/emcomm/accounts.json", "home/.bashrc", "home/.config/autostart/x.desktop",
                         "home/.ssh/authorized_keys", "home/.fldigi/macros/evil.mdf"):
                info = tarfile.TarInfo(name)
                info.size = 2
                tar.addfile(info, io.BytesIO(b"hi"))
            link = tarfile.TarInfo("home/link")
            link.type, link.linkname = tarfile.SYMTYPE, "/etc"
            tar.addfile(link)
        fresh = os.path.join(self.tmp.name, "fresh")
        # A folder the backup covers that is really a link elsewhere (Wine's dosdevices/z: -> /).
        elsewhere = os.path.join(self.tmp.name, "elsewhere")
        os.makedirs(os.path.join(fresh, ".fldigi"))
        os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(fresh, ".fldigi", "macros"))
        backup.restore(evil, fresh, apply_settings=False)
        self.assertEqual(sorted(os.listdir(fresh)), [".fldigi", "ICS forms"])
        self.assertEqual(os.listdir(os.path.join(fresh, "ICS forms")), ["ok.txt"])
        self.assertEqual(os.listdir(elsewhere), [])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "outside.txt")))


if __name__ == "__main__":
    unittest.main()
