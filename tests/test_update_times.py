"""Check Update station's step timer: how it writes times, and that it spots another
program holding the package lock but not the update's own apt.

Run: python3 tests/test_update_times.py
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("emcomm_times", os.path.join(REPO, "callback_plugins/emcomm_times.py"))
times = importlib.util.module_from_spec(spec)
spec.loader.exec_module(times)

HOLD = "import fcntl, sys, time; f = open(sys.argv[1], 'w'); fcntl.lockf(f, fcntl.LOCK_EX); print('locked', flush=True); time.sleep(30)"


class Took(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(times.took(4.4), "4s")
        self.assertEqual(times.took(72), "1m 12s")
        self.assertEqual(times.took(3725), "1h 02m")


class LockHolders(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.lock = os.path.join(self.dir.name, "lock-frontend")
        self.proc = subprocess.Popen([sys.executable, "-c", HOLD, self.lock], stdout=subprocess.PIPE, text=True)
        self.assertEqual(self.proc.stdout.readline().strip(), "locked")

    def tearDown(self):
        self.proc.kill()
        self.proc.wait()
        self.proc.stdout.close()
        self.dir.cleanup()

    def test_names_another_program(self):
        # Seen from a process that didn't start it, as unattended-upgrades is to the update.
        self.assertEqual(times.lock_holders(me=2 ** 22 + 7, lock_paths=[self.lock]),
                         [os.path.basename(sys.executable)])

    def test_leaves_out_the_updates_own(self):
        self.assertEqual(times.lock_holders(lock_paths=[self.lock]), [])

    def test_unlocked(self):
        other = os.path.join(self.dir.name, "lists-lock")
        open(other, "w").close()
        self.assertEqual(times.lock_holders(me=2 ** 22 + 7, lock_paths=[other]), [])


class Playbook(unittest.TestCase):
    def test_times_slow_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = os.path.join(tmp, "t.yml")
            with open(book, "w") as f:
                f.write("- hosts: localhost\n  gather_facts: false\n  tasks:\n"
                        "    - name: Quick step\n      ansible.builtin.command: 'true'\n"
                        "    - name: Slow step\n      ansible.builtin.command: sleep 6\n")
            env = dict(os.environ, ANSIBLE_CONFIG=os.path.join(REPO, "ansible.cfg"))
            start = time.monotonic()
            out = subprocess.run(["ansible-playbook", "-c", "local", "-i", "localhost,", book],
                                 env=env, capture_output=True, text=True, cwd=REPO).stdout
            self.assertGreater(time.monotonic() - start, 6)
        self.assertIn("  took 6s", out)
        self.assertIn("== The rebuild took", out)
        slowest = out.split("The slowest steps:")[1]
        self.assertIn("Slow step", slowest)
        self.assertNotIn("Quick step", slowest)


if __name__ == "__main__":
    unittest.main()
