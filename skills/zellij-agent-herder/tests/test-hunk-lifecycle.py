#!/usr/bin/env python3
"""Synthetic installed-entrypoint and real owned-child lifecycle regression tests."""
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("stream", SCRIPTS / "hunk-stream.py")
stream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stream)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patch = mock.patch.object(stream, "cache_root", return_value=self.temp.name)
        patch.start()
        self.addCleanup(patch.stop)
        self.directory = Path(stream.streams_dir())
        self.directory.mkdir(parents=True)

    def record(self, name, session, pane, **values):
        (self.directory / f"{name}.json").write_text(json.dumps({
            "session": session, "pane_id": pane, **values,
        }))

    def test_launch_clears_stale_server_policy_and_never_forwards_origin_pane(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            command = stream.watch_command({"session": "a", "base": "fixed"})
        self.assertIn("ZAH_HUNK_RECYCLE=", command)
        self.assertIn("ZAH_HUNK_MAX_AGE_SECONDS=", command)
        self.assertFalse(any(value.startswith("ZELLIJ_PANE_ID=") for value in command))
        self.assertEqual(command[-4:], ["--session", "a", "--base", "fixed"])

    def test_cross_session_completed_live_and_deduplicated(self):
        self.record("one", "a", "terminal_1")
        self.record("two", "b", "terminal_2", complete=True)
        self.record("duplicate", "b", "terminal_2")
        self.record("closed", "b", "terminal_3")
        with mock.patch.object(stream, "zellij_session_status", return_value=({"a", "b"}, set())), \
             mock.patch.object(stream, "panes", side_effect=lambda name: [{"id": 1 if name == "a" else 2}]):
            self.assertEqual(stream.active_stream_count("a"), 2)

    def test_missing_inventory_and_corrupt_state_fail_closed(self):
        self.record("other", "b", "terminal_2")
        with mock.patch.object(stream, "zellij_session_status", return_value=None), \
             mock.patch.object(stream, "panes", side_effect=OSError("unavailable")):
            self.assertIsNone(stream.active_stream_count("a"))
        (self.directory / "other.json").write_text("{")
        self.assertIsNone(stream.active_stream_count("a"))

    def test_empty_state_still_requires_inventory(self):
        with mock.patch.object(stream, "zellij_session_status", return_value=None), \
             mock.patch.object(stream, "panes", side_effect=OSError("unavailable")):
            self.assertIsNone(stream.active_stream_count("a"))

    def test_locked_lease_survives_missing_pane_and_state(self):
        directory = self.directory / "processes"
        directory.mkdir()
        with (directory / "owned.lease").open("w+") as lease:
            json.dump({"session": "gone", "pane_id": "terminal_9"}, lease)
            lease.flush()
            fcntl.flock(lease, fcntl.LOCK_EX)
            with mock.patch.object(stream, "zellij_session_status", return_value=({"a"}, set())), \
                 mock.patch.object(stream, "panes", return_value=[]):
                self.assertEqual(stream.active_stream_count("a"), 1)
                fcntl.flock(lease, fcntl.LOCK_UN)
                self.assertEqual(stream.active_stream_count("a"), 0)

    def test_closed_review_state_kept_for_dismissal(self):
        self.record("closed", "a", "terminal_8", signature="same")
        with mock.patch.object(stream, "zellij_session_status", return_value=({"a"}, set())), \
             mock.patch.object(stream, "panes", return_value=[]):
            stream.prune_stream_states("a")
        self.assertTrue((self.directory / "closed.json").exists())

    def test_malformed_inventory_is_not_empty_inventory(self):
        for value in ('"wrong"', '{"panes":[{"wrong":1}]}', 'null'):
            with self.subTest(value=value), mock.patch.object(stream, "zellij", return_value=value):
                with self.assertRaises(ValueError):
                    stream.panes("a")


class RealChildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "installed" / "scripts"
        self.install.mkdir(parents=True)
        for name in ("hunk-stream.py", "hunk-watch.py", "zj.sh"):
            shutil.copy2(SCRIPTS / name, self.install / name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.inventory = self.root / "panes.json"
        self.inventory.write_text(json.dumps([{"id": 1, "tab_id": 1}, {"id": 10, "tab_id": 2}]))
        self.events = self.root / "children.jsonl"
        self.log = self.root / "watch.log"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("ZAH_")}
        self.env.update({
            "PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": str(self.root),
            "XDG_CACHE_HOME": str(self.root / "cache"), "ZELLIJ_PANE_ID": "10",
            "ZJ_SESSION": "a", "TEST_ROOT": str(self.root),
            "ZAH_HUNK_SAMPLE_SECONDS": "0.04", "ZAH_HUNK_RSS_MIB": "1",
            "ZAH_HUNK_PRESSURE_SAMPLES": "3", "ZAH_HUNK_RESUME_GRACE_SECONDS": "2",
            "ZAH_HUNK_RESTART_DELAY_SECONDS": "0.08", "ZAH_HUNK_STOP_GRACE_SECONDS": "0.1",
        })
        self.executable("zellij", '''
import json, os, pathlib, subprocess, sys
root = pathlib.Path(os.environ["TEST_ROOT"])
if "list-sessions" in sys.argv:
    print("a [Created now]\\nb [Created now]")
elif "list-panes" in sys.argv:
    if (root / "inventory-failed").exists(): sys.exit(1)
    print((root / "panes.json").read_text())
elif "new-tab" in sys.argv or "new-pane" in sys.argv:
    env = dict(os.environ, ZELLIJ_PANE_ID="10")
    with (root / "watch.log").open("a") as log:
        child = subprocess.Popen(sys.argv[sys.argv.index("--") + 1:], env=env,
            cwd=sys.argv[sys.argv.index("--cwd") + 1], stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, start_new_session=True)
    (root / "supervisor.pid").write_text(str(child.pid))
    (root / "panes.json").write_text(json.dumps([{"id":1,"tab_id":1},{"id":10,"tab_id":2}]))
    print("2")
''')
        self.executable("hunk", '''
import json, os, pathlib, signal, sys, time
root = pathlib.Path(os.environ["TEST_ROOT"])
time.sleep(float(os.environ.get("TEST_STARTUP_DELAY", "0")))
with (root / "children.jsonl").open("a") as log:
    log.write(json.dumps({"pid":os.getpid(),"args":sys.argv[1:],"cwd":os.getcwd()}) + "\\n")
if os.environ.get("TEST_EXIT"): sys.exit(int(os.environ["TEST_EXIT"]))
# A real allocation ensures ps observes a positive RSS without mocking it.
memory = bytearray(4 * 1024 * 1024)
while True: time.sleep(0.01)
''')
        self.processes = []
        self.addCleanup(self.stop_all)

    def executable(self, name, source):
        path = self.bin / name
        path.write_text(f"#!{sys.executable}\n" + source)
        path.chmod(0o755)

    def stop_all(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        # Also contain failures in the shell-entrypoint test, whose process is detached.
        path = self.root / "supervisor.pid"
        if path.exists():
            try: os.kill(int(path.read_text()), signal.SIGTERM)
            except ProcessLookupError: pass

    def children(self):
        return [json.loads(line) for line in self.events.read_text().splitlines()] if self.events.exists() else []

    def wait_for(self, predicate, timeout=6):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(0.02)
        self.fail(f"condition timed out; log={self.log.read_text() if self.log.exists() else ''}")

    def start(self, **settings):
        env = dict(self.env, **settings)
        with self.log.open("a") as log:
            child = subprocess.Popen([sys.executable, str(self.install / "hunk-watch.py"),
                "--session", settings.get("TEST_SESSION", "a"), "--base", "fixed-base"],
                env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
        self.processes.append(child)
        return child

    def state(self, pid):
        result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
        return result.stdout.strip()

    def test_default_pressure_pauses_resumes_same_child_and_shutdown_reaps(self):
        process = self.start()
        self.wait_for(lambda: len(self.children()) == 1 and "paused child" in self.log.read_text())
        pid = self.children()[0]["pid"]
        self.wait_for(lambda: "T" in self.state(pid))
        self.assertEqual(len(self.children()), 1)
        self.assertIn(f"kill -USR1 {process.pid}", self.log.read_text())
        process.send_signal(signal.SIGUSR1)
        self.wait_for(lambda: "resumed owned child" in self.log.read_text() and "T" not in self.state(pid))
        self.assertEqual(self.children()[0]["pid"], pid)
        process.terminate()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertEqual(self.state(pid), "")

    def test_stopped_child_is_reaped_when_pane_closes(self):
        process = self.start()
        self.wait_for(lambda: len(self.children()) == 1 and "paused child" in self.log.read_text())
        pid = self.children()[0]["pid"]
        self.inventory.write_text("[]")
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertEqual(self.state(pid), "")
        self.assertEqual(len(self.children()), 1)

    def test_recycle_is_opt_in_bounded_and_preserves_fixed_command(self):
        process = self.start(ZAH_HUNK_RECYCLE="1", ZAH_HUNK_MAX_RESTARTS="1")
        self.wait_for(lambda: len(self.children()) == 2 and "paused child" in self.log.read_text())
        first, second = self.children()
        self.assertNotEqual(first["pid"], second["pid"])
        self.assertEqual(self.state(first["pid"]), "")
        self.assertEqual(first["args"], ["diff", "fixed-base", "--watch"])
        self.assertEqual(second["args"], first["args"])
        self.assertEqual(second["cwd"], first["cwd"])
        self.assertIsNone(process.poll())

    def test_crash_never_restarts(self):
        process = self.start(TEST_EXIT="7", ZAH_HUNK_RECYCLE="1")
        self.assertEqual(process.wait(timeout=5), 7)
        self.assertEqual(len(self.children()), 1)

    def test_age_optional_and_explicit_age_recycles(self):
        # Keep age above the deliberately delayed startup. A sub-startup age can
        # correctly pause the child before it emits the record asserted below.
        process = self.start(ZAH_HUNK_RSS_MIB="99999", ZAH_HUNK_MAX_AGE_SECONDS="1",
                             ZAH_HUNK_RECYCLE="1", ZAH_HUNK_MAX_RESTARTS="1", TEST_STARTUP_DELAY="0.2")
        self.wait_for(lambda: len(self.children()) == 2 and "paused child" in self.log.read_text(), timeout=10)
        self.assertIn("maximum age", self.log.read_text())
        self.assertIsNone(process.poll())

    def test_global_cap_and_duplicate_supervisor_admission(self):
        first = self.start(ZAH_MAX_ACTIVE_STREAMS="1", ZAH_HUNK_RSS_MIB="99999")
        self.wait_for(lambda: len(self.children()) == 1)
        duplicate = self.start(ZAH_MAX_ACTIVE_STREAMS="1")
        self.assertEqual(duplicate.wait(timeout=5), 1)
        other = self.start(ZAH_MAX_ACTIVE_STREAMS="1", TEST_SESSION="b")
        self.assertEqual(other.wait(timeout=5), 1)
        self.assertEqual(len(self.children()), 1)
        self.assertIsNone(first.poll())

    def test_pressure_requires_consecutive_samples_and_does_not_touch_other_child(self):
        # Exercise the public CLI with a deterministic sampler sequence, not a
        # copied supervisor loop. Other tests use the actual system ps RSS.
        self.executable("ps", """
import os, pathlib
path = pathlib.Path(os.environ["TEST_ROOT"]) / "samples"
count = int(path.read_text()) if path.exists() else 0
path.write_text(str(count + 1))
print([99999, 99999, 0, 99999, 99999, 99999][min(count, 5)])
""")
        unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        self.processes.append(unrelated)
        process = self.start()
        self.wait_for(lambda: "paused child" in self.log.read_text())
        self.assertEqual((self.root / "samples").read_text(), "6")
        self.assertNotIn("T", self.state(unrelated.pid))
        self.assertIsNone(unrelated.poll())
        self.assertEqual(len(self.children()), 1)
        self.assertIsNone(process.poll())

    def test_unknown_inventory_blocks_recycle_without_losing_child(self):
        process = self.start(ZAH_HUNK_RECYCLE="1", ZAH_HUNK_PRESSURE_SAMPLES="5")
        self.wait_for(lambda: len(self.children()) == 1)
        (self.root / "inventory-failed").touch()
        self.wait_for(lambda: "paused child" in self.log.read_text())
        self.assertEqual(len(self.children()), 1)
        self.assertIsNone(process.poll())

    def test_unknown_inventory_never_starts_child(self):
        (self.root / "inventory-failed").touch()
        process = self.start()
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertEqual(self.children(), [])

    def test_installed_public_review_entrypoint_launches_supervisor(self):
        repo = self.root / "repo"
        repo.mkdir()
        for args in (["init", "-q"], ["-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                      "commit", "--allow-empty", "-qm", "base"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
        base = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        self.inventory.write_text('[{"id":1,"tab_id":1}]')
        env = dict(self.env, ZELLIJ_PANE_ID="1", ZAH_HUNK_RSS_MIB="99999")
        result = subprocess.run(["bash", "-c", 'source "$1"; zj_review_stream "$2" "$3" test',
            "test", str(self.install / "zj.sh"), str(repo), base],
            env=env, text=True, capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "terminal_10")
        self.wait_for(lambda: len(self.children()) == 1)
        child = self.children()[0]
        self.assertEqual(child["args"], ["diff", base, "--watch"])
        self.assertEqual(child["cwd"], str(repo))
        self.inventory.write_text('[{"id":1,"tab_id":1}]')
        self.wait_for(lambda: self.state(child["pid"]) == "")
        self.assertEqual(len(self.children()), 1)
        automatic = subprocess.run([sys.executable, str(self.install / "hunk-stream.py"),
            "ensure", "--session", "a", "--parent", "1", "--root", str(repo),
            "--base", base, "--kind", "worktree", "--label", "test"],
            env=env, capture_output=True, text=True, timeout=8)
        self.assertEqual(automatic.returncode, 0, automatic.stderr)
        self.assertEqual(automatic.stdout.strip(), "")
        self.assertEqual(len(self.children()), 1)


if __name__ == "__main__":
    unittest.main()
