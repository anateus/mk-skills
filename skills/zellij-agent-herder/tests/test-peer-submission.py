#!/usr/bin/env python3
"""Offline dispatch checks; opt in to an owned real Zellij/PTY composer."""
import json
import fcntl
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import struct
import tempfile
import threading
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "skills/zellij-agent-herder/scripts/zellij-peer.sh"
MOCK = r'''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
with open(os.environ["ACTION_LOG"], "a") as log:
    log.write(json.dumps([time.time(), args]) + "\n")
if "list-panes" in args:
    print(os.environ["PANES"])
elif "paste" in args and os.environ.get("FAIL_PASTE"):
    sys.exit(1)
'''

# A small terminal model of a paste-aware composer, not a clone of an agent.
# Unbracketed bursts absorb immediate CR; explicit paste resets that window.
COMPOSER = r'''
import json, os, select, sys, termios, time, tty
fd = sys.stdin.fileno()
tty.setraw(fd)
os.write(1, b"\x1b[?2004hREADY\r\n")
draft = bytearray()
pending = bytearray()
accepted = []
last_char = 0
in_paste = False
paste_count = 0
def save():
    with open(sys.argv[1], "w") as out:
        json.dump({"draft": draft.decode(errors="replace"), "accepted": accepted,
                   "paste_count": paste_count}, out)
save()
while True:
    select.select([fd], [], [])
    pending.extend(os.read(fd, 4096))
    while pending:
        if pending[0] == 27:
            if len(pending) < 6:
                break
            marker = bytes(pending[:6])
            del pending[:6]
            if marker == b"\x1b[200~":
                in_paste = True
                paste_count += 1
            elif marker == b"\x1b[201~":
                in_paste = False
                last_char = 0
            continue
        char = pending.pop(0)
        if char == 13 and not in_paste:
            if time.monotonic() - last_char < 0.12:
                draft.append(10)
            elif draft:
                accepted.append(draft.decode())
                draft.clear()
                os.write(1, b"TRANSCRIPT ACK\r\n")
        else:
            draft.append(char)
            if not in_paste:
                last_char = time.monotonic()
    save()
'''


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        mock = self.path / "zellij"
        mock.write_text(MOCK)
        mock.chmod(0o755)
        self.log = self.path / "actions.jsonl"
        self.env = {"PATH": str(self.path) + os.pathsep + os.environ["PATH"],
                    "HOME": str(self.path), "XDG_CACHE_HOME": str(self.path),
                    "ZJ_SESSION": "synthetic-session", "ACTION_LOG": str(self.log),
                    "PANES": json.dumps([{"id": 7, "title": "synthetic-peer"}])}

    def ask(self, prompt="Check synthetic input", **env):
        return subprocess.run(["bash", str(HELPER), "ask", "synthetic-peer", prompt],
                              env=self.env | env, capture_output=True, text=True)

    def actions(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_single_scoped_paste_and_enter_preserve_multiline_unicode(self):
        prompt = "First line\n第二行\nLiteral $(echo unsafe) and `literal`"
        result = self.ask(prompt)
        self.assertEqual(result.returncode, 0, result.stderr)
        mutations = [(stamp, args) for stamp, args in self.actions()
                     if "list-panes" not in args]
        self.assertEqual(mutations[0][1], ["--session", "synthetic-session", "action",
                                        "paste", "-p", "terminal_7", "--", prompt])
        self.assertEqual(mutations[1][1], ["--session", "synthetic-session", "action",
                                        "write", "-p", "terminal_7", "13"])
        self.assertEqual(len(mutations), 2)
        self.assertGreaterEqual(mutations[1][0] - mutations[0][0], 0.2)
        self.assertIn("acknowledgement", result.stderr)

    def test_failed_paste_never_submits(self):
        self.assertNotEqual(self.ask(FAIL_PASTE="1").returncode, 0)
        self.assertFalse(any("write" in args for _, args in self.actions()))

    def test_obsolete_double_enter_refused_before_input(self):
        result = self.ask(PEER_DOUBLE_ENTER="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PEER_DOUBLE_ENTER", result.stderr)
        self.assertFalse(self.log.exists())

    def test_ambiguous_title_never_sends(self):
        result = self.ask(PANES=json.dumps([{"id": 7, "title": "synthetic-peer"},
                                           {"id": 8, "title": "synthetic-peer"}]))
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all("list-panes" in args for _, args in self.actions()))

    def test_empty_prompt_never_sends(self):
        self.assertNotEqual(self.ask("").returncode, 0)
        self.assertFalse(self.log.exists())


@unittest.skipUnless(os.environ.get("RUN_ZELLIJ_PEER_SUBMISSION") == "1",
                     "set RUN_ZELLIJ_PEER_SUBMISSION=1 for isolated native PTY proof")
class NativeComposerTests(unittest.TestCase):
    def test_actual_zellij_paste_and_one_enter(self):
        binary = shutil.which("zellij")
        self.assertIsNotNone(binary)
        # Short paths also fit macOS Unix socket limits.
        with tempfile.TemporaryDirectory(prefix="peer-submit-", dir="/tmp") as temp:
            path = Path(temp)
            state = path / "state.json"
            fixture = path / "composer.py"
            fixture.write_text(COMPOSER)
            config = path / "config.kdl"
            config.write_text('show_startup_tips false\nshow_release_notes false\n')
            session = "peer-submission-test-" + str(os.getpid())
            env = {"PATH": os.environ["PATH"], "TERM": "xterm-256color",
                   "HOME": temp, "SHELL": "/bin/sh",
                   "XDG_CONFIG_HOME": temp, "XDG_CACHE_HOME": temp,
                   "XDG_DATA_HOME": temp, "ZELLIJ_SOCKET_DIR": temp + "/sockets",
                   "ZJ_SESSION": session}
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
            proc = subprocess.Popen([binary, "--session", session, "--config",
                                     str(config)],
                                    stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            stop = threading.Event()
            terminal_output = bytearray()
            def drain():
                while not stop.is_set():
                    try:
                        if select.select([master], [], [], 0.1)[0]:
                            terminal_output.extend(os.read(master, 65536))
                            del terminal_output[:-65536]
                    except OSError:
                        break
            thread = threading.Thread(target=drain, daemon=True)
            thread.start()
            def snapshot(predicate):
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    try:
                        value = json.loads(state.read_text())
                        if predicate(value):
                            return value
                    except (FileNotFoundError, json.JSONDecodeError):
                        pass
                    time.sleep(0.05)
                panes = subprocess.run([binary, "--session", session, "action",
                                        "list-panes", "-j"], env=env,
                                       capture_output=True, text=True, timeout=5)
                self.fail("owned synthetic composer did not acknowledge input: " +
                          panes.stdout + panes.stderr +
                          terminal_output[:1200].decode(errors="replace"))
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    listed = subprocess.run([binary, "--session", session, "action",
                                             "list-panes", "-j"], env=env,
                                            capture_output=True, text=True, timeout=5)
                    if listed.returncode == 0:
                        break
                    time.sleep(0.05)
                spawned = subprocess.run([binary, "--session", session, "action",
                                          "new-pane", "--name", "synthetic-peer", "--",
                                          shutil.which("python3"), str(fixture), str(state)],
                                         env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(spawned.returncode, 0, spawned.stderr)
                snapshot(lambda value: True)
                result = subprocess.run(["bash", str(HELPER), "ask", "synthetic-peer",
                                         "First line\n第二行"], env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                value = snapshot(lambda value: bool(value["accepted"]))
                self.assertEqual(value["accepted"], ["First line\n第二行"])
                self.assertEqual(value["paste_count"], 1)
                self.assertEqual(value["draft"], "")
                # A known negative proves the fixture detects immediate raw Enter.
                subprocess.run([binary, "--session", session, "action", "write",
                                "-p", "terminal_1", *map(str, b"raw burst\r")],
                               env=env, check=True, capture_output=True)
                value = snapshot(lambda value: value["draft"] == "raw burst\n")
                self.assertEqual(len(value["accepted"]), 1)
                time.sleep(0.2)
                self.assertEqual(len(snapshot(lambda value: True)["accepted"]), 1)
            finally:
                subprocess.run([binary, "kill-session", session], env=env,
                               capture_output=True, timeout=5)
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                stop.set()
                thread.join(timeout=1)
                os.close(master)


if __name__ == "__main__":
    unittest.main(verbosity=2)
