# How long each step of Update station takes, so a slow one can be seen rather
# than guessed at. After a step that took a while it prints "took 1m 12s"; while
# one is still running it says so every 30 seconds, and names the other program
# when it is waiting for the package lock (Ubuntu's own updates, for instance).
# At the end it lists the slowest steps.
from __future__ import annotations

import os
import threading
import time

from ansible.plugins.callback import CallbackBase

DOCUMENTATION = """
    name: emcomm_times
    type: aggregate
    short_description: Times each step of Update station
    description: Prints how long slow steps took, a note every 30 seconds while one runs, and the slowest steps at the end.
"""

SHOW_OVER = 5  # seconds: quicker steps aren't worth a line
TICK = 30
# The locks apt and dpkg hold while they work.
APT_LOCKS = ["/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock", "/var/lib/apt/lists/lock",
             "/var/cache/apt/archives/lock"]


def took(seconds):
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m {seconds:02d}s"


def _ancestors(pid):
    """pid and the processes that started it."""
    seen = []
    while pid > 1 and pid not in seen:
        seen.append(pid)
        try:
            with open(f"/proc/{pid}/stat") as f:
                pid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return seen


def _name(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            args = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
    except OSError:
        return ""
    # "/usr/bin/python3 /usr/bin/unattended-upgrade" names the script, not python.
    words = [os.path.basename(a) for a in args[:2] if not a.startswith("-")]
    if len(words) > 1 and words[0].startswith("python"):
        return words[1]
    return words[0] if words else ""


def lock_holders(me=None, locks_file="/proc/locks", lock_paths=APT_LOCKS):
    """Names of the programs, other than this update, holding apt's or dpkg's lock."""
    inodes = set()
    for path in lock_paths:
        try:
            inodes.add(os.stat(path).st_ino)
        except OSError:
            pass
    me = os.getpid() if me is None else me
    names = []
    try:
        with open(locks_file) as f:
            lines = f.read().splitlines()
    except OSError:
        return names
    for line in lines:
        # "1: POSIX  ADVISORY  WRITE 1234 fd:01:5243 0 EOF"
        fields = line.split()
        if len(fields) < 6 or fields[1] != "POSIX" or not fields[4].isdigit():
            continue
        try:
            inode = int(fields[5].rsplit(":", 1)[1])
        except (IndexError, ValueError):
            continue
        pid = int(fields[4])
        if inode in inodes and me not in _ancestors(pid):
            name = _name(pid)
            if name and name not in names:
                names.append(name)
    return names


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "emcomm_times"
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super().__init__()
        self.started = time.monotonic()
        self.steps = []  # (seconds, name)
        self.current = None  # (name, start)
        self.stop = threading.Event()
        self.ticker = None

    def _finish(self, show=True):
        if self.ticker:
            self.stop.set()
            self.ticker.join()
            self.ticker = None
        if not self.current:
            return
        name, start = self.current
        self.current = None
        seconds = time.monotonic() - start
        self.steps.append((seconds, name))
        if show and seconds >= SHOW_OVER:
            self._display.display(f"  took {took(seconds)}")

    def _tick(self, name, start):
        while not self.stop.wait(TICK):
            waited = took(time.monotonic() - start)
            holders = lock_holders()
            if holders:
                self._display.display(
                    f"  ... waiting {waited} for {', '.join(holders)} to finish: another program is "
                    "installing or updating software. This carries on by itself when it's done.")
            else:
                self._display.display(f"  ... still working on it: {waited}")

    def _start(self, task):
        self._finish()
        name = task.get_name().strip()
        self.current = (name, time.monotonic())
        self.stop = threading.Event()
        self.ticker = threading.Thread(target=self._tick, args=self.current, daemon=True)
        self.ticker.start()

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._start(task)

    def v2_playbook_on_handler_task_start(self, task):
        self._start(task)

    def v2_runner_on_ok(self, result):
        self._finish()

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._finish()

    def v2_runner_on_unreachable(self, result):
        self._finish()

    def v2_runner_on_skipped(self, result):
        self._finish(show=False)

    def v2_playbook_on_stats(self, stats):
        self._finish(show=False)
        slow = sorted((s for s in self.steps if s[0] >= SHOW_OVER), reverse=True)[:8]
        self._display.display("")
        self._display.display(f"== The rebuild took {took(time.monotonic() - self.started)} ==")
        if slow:
            self._display.display("The slowest steps:")
            for seconds, name in slow:
                self._display.display(f"  {took(seconds):>8}  {name}")
