"""Check that emcomm-find-radio names a radio from its answer, Yaesu/Kenwood "ID;" or
Icom CI-V, using a pseudo-terminal as the radio's port.

Run: python3 tests/test_find_radio.py
"""

import json
import os
import pty
import subprocess
import sys
import tempfile
import threading
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/radio/files/emcomm-find-radio")


class FakeRadio(threading.Thread):
    """Answers on the master side of a pty: reply(bytes received) -> bytes to send, or b""."""

    def __init__(self, reply):
        super().__init__(daemon=True)
        self.master, slave = pty.openpty()
        self.path = os.ttyname(slave)
        self.slave = slave  # kept open so the pty stays up between the helper's opens
        self.reply = reply
        self.heard = b""

    def run(self):
        while True:
            try:
                data = os.read(self.master, 256)
            except OSError:
                return
            self.heard += data
            answer = self.reply(self.heard)
            if answer:
                self.heard = b""
                os.write(self.master, answer)


class FindRadioTest(unittest.TestCase):
    def find(self, radio, *args):
        radio.start()
        tmp = tempfile.mkdtemp()
        env = dict(os.environ, EMCOMM_FIND_TEST="1", EMCOMM_FIND_TIMEOUT="0.2", PATH=tmp,
                   EMCOMM_RIG_CAT=os.path.join(tmp, "rig-cat"))
        result = subprocess.run([sys.executable, HELPER, radio.path, *args], env=env, capture_output=True,
                                text=True, timeout=30)
        return result.returncode, json.loads(result.stdout)

    def test_yaesu_by_id(self):
        code, found = self.find(FakeRadio(lambda heard: b"ID0800;" if b"ID;" in heard else b""))
        self.assertEqual(code, 0)
        self.assertTrue(found["found"])
        self.assertEqual(found["name"], "FT-710")
        self.assertEqual(found["baud"], 4800)

    def test_kenwood_unknown_number_still_reported(self):
        code, found = self.find(FakeRadio(lambda heard: b"ID999;" if b"ID;" in heard else b""))
        self.assertEqual(found["name"], "radio ID 999")
        self.assertIsNone(found["model"])

    def test_icom_civ(self):
        def civ(heard):
            if heard.endswith(b"\xfe\xfe\x00\xe0\x19\x00\xfd"):
                return b"\xfe\xfe\xe0\x94\x19\x00\x94\xfd"
            return b""
        code, found = self.find(FakeRadio(civ))
        self.assertEqual(code, 0)
        self.assertEqual(found["name"], "IC-7300")

    def test_nothing_answers(self):
        code, found = self.find(FakeRadio(lambda heard: b""))
        self.assertEqual(code, 1)
        self.assertFalse(found["found"])
        self.assertIn("No radio answered", found["why"])

    def test_refuses_other_paths_for_real(self):
        result = subprocess.run([sys.executable, HELPER, "/etc/passwd"], capture_output=True, text=True,
                                env=dict(os.environ, EMCOMM_FIND_TEST="0"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("isn't plugged in", result.stdout)


if __name__ == "__main__":
    unittest.main()
