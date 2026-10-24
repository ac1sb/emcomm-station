"""Check emcomm-stream builds Broadcastify's Icecast address and explains failures.

Run: python3 tests/test_stream.py
"""

import importlib.machinery
import importlib.util
import os
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPER = os.path.join(REPO, "roles/radio/files/emcomm-stream")


def load_helper():
    loader = importlib.machinery.SourceFileLoader("emcomm_stream", HELPER)
    spec = importlib.util.spec_from_loader("emcomm_stream", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


stream = load_helper()
FEED = {"server": "audio9.broadcastify.com", "port": 80, "mount": "abcd1234", "password": "p@ss w/rd"}


class Stream(unittest.TestCase):
    def test_complete_settings(self):
        self.assertIsNone(stream.problem(FEED))
        self.assertIn("password", stream.problem(dict(FEED, password=" ")))
        self.assertIn("port", stream.problem(dict(FEED, port="eighty")))
        self.assertIsNone(stream.problem(dict(FEED, port="")))  # 80 when left blank

    def test_icecast_url_escapes_the_password_and_tidies_the_server(self):
        url = stream.icecast_url(dict(FEED, server="http://audio9.broadcastify.com/", mount="/abcd1234"))
        self.assertEqual(url, "icecast://source:p%40ss%20w%2Frd@audio9.broadcastify.com:80/abcd1234")

    def test_broadcastify_audio_format(self):
        args = stream.ffmpeg_args(FEED, "alsa_input.usb-radio")
        self.assertEqual(args[args.index("-i") + 1], "alsa_input.usb-radio")  # the radio, not "default"
        for flag, value in (("-ac", "1"), ("-ar", "22050"), ("-b:a", "16k"), ("-c:a", "libmp3lame")):
            self.assertEqual(args[args.index(flag) + 1], value)

    def test_explains_failures(self):
        self.assertIn("password", stream.explain("Server returned 401 Unauthorized (authorization failed)"))
        self.assertIn("internet", stream.explain("Failed to resolve hostname audio9.broadcastify.com"))
        self.assertIn("sound card", stream.explain("Error opening input files: No such process"))
        self.assertEqual(stream.explain(""), "The stream stopped.")


if __name__ == "__main__":
    unittest.main()
