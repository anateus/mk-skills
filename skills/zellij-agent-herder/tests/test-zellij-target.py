#!/usr/bin/env python3
"""Tests for Zellij socket-directory and session resolution."""

import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "hunk-stream.py"
SPEC = importlib.util.spec_from_file_location("hunk_stream", SCRIPT)
assert SPEC and SPEC.loader
hunk_stream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hunk_stream)


class ZellijTargetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sockets = self.root / "sockets"
        self.sockets.mkdir()
        self.bound = []
        self.addCleanup(self._close)
        hunk_stream._TARGET_CACHE.clear()
        # Pin the socket directory and mark the process as inside Zellij so
        # resolution never probes the host and recovery is exercised.
        pinned = mock.patch.dict(
            os.environ, {"ZELLIJ_SOCKET_DIR": str(self.sockets), "ZELLIJ": "0"}
        )
        pinned.start()
        self.addCleanup(pinned.stop)

    def _close(self):
        for handle in self.bound:
            handle.close()

    def make_session(self, directory, name):
        base = Path(directory) / "contract_version_1"
        base.mkdir(parents=True, exist_ok=True)
        handle = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        handle.bind(str(base / name))
        self.bound.append(handle)

    def resolve(self, session, pane=None):
        return hunk_stream.resolve_target(session, pane)

    def test_explicit_socket_dir_is_authoritative(self):
        self.make_session(self.sockets, "live-a")
        self.make_session(self.root / "other", "live-b")
        # Only the explicit directory is scanned, so live-b is invisible; the sole
        # visible live session is adopted instead of probing the other directory.
        self.assertEqual(hunk_stream.socket_dirs(), [os.path.normpath(str(self.sockets))])
        self.assertEqual(self.resolve("live-a"), (str(self.sockets), "live-a"))
        self.assertEqual(self.resolve("live-b"), (str(self.sockets), "live-a"))

    def test_socket_dirs_falls_back_to_tmpdir_without_getconf(self):
        uid = os.getuid()
        with mock.patch.dict(os.environ, {"TMPDIR": "/tmp/x"}, clear=True), \
             mock.patch.object(hunk_stream.subprocess, "run", side_effect=OSError("no getconf")):
            self.assertEqual(
                hunk_stream.socket_dirs(),
                [f"/tmp/x/zellij-{uid}", f"/tmp/zellij-{uid}"],
            )

    def test_socket_dirs_prefers_macos_user_temp_dir(self):
        uid = os.getuid()
        probe = mock.Mock(returncode=0, stdout="/var/folders/zz/T/\n")
        with mock.patch.dict(os.environ, {"TMPDIR": "/tmp/x"}, clear=True), \
             mock.patch.object(hunk_stream.subprocess, "run", return_value=probe):
            self.assertEqual(
                hunk_stream.socket_dirs(),
                [f"/tmp/x/zellij-{uid}", f"/var/folders/zz/T/zellij-{uid}", f"/tmp/zellij-{uid}"],
            )

    def test_live_sessions_reads_contract_dir_sockets(self):
        self.make_session(self.sockets, "live-a")
        self.assertEqual(hunk_stream.live_sessions(str(self.sockets)), ["live-a"])

    def test_requested_session_wins_over_recovery(self):
        self.make_session(self.sockets, "live-a")
        self.make_session(self.sockets, "live-b")
        self.assertEqual(self.resolve("live-b", "1"), (str(self.sockets), "live-b"))

    def test_stale_session_adopts_sole_live_session(self):
        self.make_session(self.sockets, "live-a")
        self.assertEqual(self.resolve("stale-name", "1"), (str(self.sockets), "live-a"))

    def test_stale_session_adopts_unique_pane_owner(self):
        self.make_session(self.sockets, "live-a")
        self.make_session(self.sockets, "live-b")

        def pane_ids(_directory, name):
            return {"terminal_1"} if name == "live-a" else {"terminal_2"}

        with mock.patch.object(hunk_stream, "session_pane_ids", side_effect=pane_ids):
            self.assertEqual(self.resolve("stale-name", "2"), (str(self.sockets), "live-b"))

    def test_ambiguous_live_sessions_are_not_guessed(self):
        self.make_session(self.sockets, "live-a")
        self.make_session(self.sockets, "live-b")
        with mock.patch.object(hunk_stream, "session_pane_ids", return_value=set()):
            self.assertEqual(self.resolve("stale-name", "9"), (None, "stale-name"))

    def test_no_live_sessions_leaves_request_unchanged(self):
        self.assertEqual(self.resolve("stale-name", "1"), (None, "stale-name"))

    def test_outside_zellij_never_adopts_another_session(self):
        self.make_session(self.sockets, "live-a")
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.dict(os.environ, {"ZELLIJ_SOCKET_DIR": str(self.sockets)}):
            self.assertEqual(hunk_stream.resolve_target("stale-name", "1"), (None, "stale-name"))
            # A live requested session still gets its socket directory.
            self.assertEqual(hunk_stream.resolve_target("live-a", "1"), (str(self.sockets), "live-a"))

    def test_zellij_passes_resolved_socket_dir(self):
        self.make_session(self.sockets, "live-a")
        calls = []

        def raw(session, args, socket_dir=None):
            calls.append((session, list(args), socket_dir))
            return "[]"

        with mock.patch.object(hunk_stream, "_zellij_raw", side_effect=raw):
            hunk_stream.zellij("stale-name", ["list-panes", "-j"])
        self.assertEqual(calls, [("live-a", ["list-panes", "-j"], str(self.sockets))])

    def test_target_is_cached_per_session(self):
        with mock.patch.object(
            hunk_stream, "resolve_target", side_effect=lambda session, pane: ("/d", session),
        ) as resolver:
            hunk_stream.zellij_target("live-a")
            hunk_stream.zellij_target("live-a")
        self.assertEqual(resolver.call_count, 1)

    def test_resolve_subcommand_prints_resolved_target(self):
        self.make_session(self.sockets, "live-a")
        env = dict(os.environ)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "resolve", "--session", "stale", "--pane", "1"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"socket_dir={self.sockets}", result.stdout)
        self.assertIn("session=live-a", result.stdout)


if __name__ == "__main__":
    unittest.main()
