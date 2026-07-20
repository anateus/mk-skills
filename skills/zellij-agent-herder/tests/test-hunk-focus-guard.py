#!/usr/bin/env python3
"""Deterministic tests for the short-lived Hunk focus guard."""

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "hunk-stream.py"
SPEC = importlib.util.spec_from_file_location("hunk_stream", SCRIPT)
assert SPEC and SPEC.loader
hunk_stream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hunk_stream)


class FakeClock:
    def __init__(self, step=0.05):
        self.now = 0.0
        self.step = step

    def monotonic(self):
        value = self.now
        self.now += self.step
        return value

    def sleep(self, seconds):
        self.now += seconds


class FocusGuardTests(unittest.TestCase):
    def test_restores_delayed_watcher_switch_and_keeps_observing(self):
        clock = FakeClock()
        focused = ["terminal_9"]
        polls = 0
        restores = []

        def clients(_session):
            nonlocal polls
            polls += 1
            if polls in (3, 8):
                focused[0] = "terminal_10"
            return [("1", focused[0])]

        def restore(_session, original, watcher, deadline=None):
            self.assertEqual(watcher, "terminal_10")
            self.assertIsNotNone(deadline)
            restores.append(original)
            focused[0] = original
            return True

        with mock.patch.object(hunk_stream, "clients", clients), \
             mock.patch.object(hunk_stream, "pane_map", return_value={
                 "terminal_9": {}, "terminal_10": {},
             }), \
             mock.patch.object(hunk_stream, "restore_guard_focus", restore), \
             mock.patch.object(hunk_stream.time, "monotonic", clock.monotonic), \
             mock.patch.object(hunk_stream.time, "sleep", clock.sleep):
            hunk_stream.focus_guard("s", "terminal_9", "terminal_10", 1.0, 0.02)

        self.assertEqual(restores, ["terminal_9", "terminal_9"])
        self.assertGreaterEqual(polls, 8)

    def test_exits_without_restoring_after_third_pane_focus(self):
        clock = FakeClock()
        rows = iter([[("1", "terminal_9")], [("1", "terminal_77")]])
        restore = mock.Mock()

        with mock.patch.object(hunk_stream, "clients", side_effect=lambda _s: next(rows)), \
             mock.patch.object(hunk_stream, "pane_map", return_value={
                 "terminal_9": {}, "terminal_10": {}, "terminal_77": {},
             }), \
             mock.patch.object(hunk_stream, "restore_guard_focus", restore), \
             mock.patch.object(hunk_stream.time, "monotonic", clock.monotonic), \
             mock.patch.object(hunk_stream.time, "sleep", clock.sleep):
            hunk_stream.focus_guard("s", "terminal_9", "terminal_10", 1.0, 0.02)

        restore.assert_not_called()

    def test_never_moves_focus_if_user_switches_during_restore(self):
        move = mock.Mock()
        with mock.patch.object(hunk_stream, "clients", return_value=[("1", "terminal_77")]), \
             mock.patch.object(hunk_stream, "zellij", move):
            restored = hunk_stream.restore_guard_focus(
                "s", "terminal_9", "terminal_10",
            )

        self.assertFalse(restored)
        move.assert_not_called()

    def test_rechecks_watcher_focus_immediately_before_move(self):
        rows = iter([
            [("1", "terminal_10")],
            [("1", "terminal_77")],
        ])
        panes = {
            "terminal_9": {"pane_x": 0, "pane_y": 0, "pane_columns": 40, "pane_rows": 24},
            "terminal_10": {"pane_x": 40, "pane_y": 0, "pane_columns": 40, "pane_rows": 24},
        }
        move = mock.Mock()
        with mock.patch.object(hunk_stream, "clients", side_effect=lambda _s: next(rows)), \
             mock.patch.object(hunk_stream, "pane_map", return_value=panes), \
             mock.patch.object(hunk_stream, "zellij", move):
            restored = hunk_stream.restore_guard_focus(
                "s", "terminal_9", "terminal_10",
            )

        self.assertFalse(restored)
        move.assert_not_called()

    def test_hard_deadline_bounds_polling_and_process_exits(self):
        clock = FakeClock(step=0.1)
        clients = mock.Mock(return_value=[("1", "terminal_9")])

        with mock.patch.object(hunk_stream, "clients", clients), \
             mock.patch.object(hunk_stream, "pane_map", return_value={
                 "terminal_9": {}, "terminal_10": {},
             }), \
             mock.patch.object(hunk_stream.time, "monotonic", clock.monotonic), \
             mock.patch.object(hunk_stream.time, "sleep", clock.sleep):
            hunk_stream.focus_guard("s", "terminal_9", "terminal_10", 0.35, 0.02)

        self.assertLessEqual(clients.call_count, 4)

    def test_restore_attempt_cannot_overrun_guard_deadline(self):
        clock = FakeClock(step=0.01)
        panes = {
            "terminal_9": {"pane_x": 0, "pane_y": 0, "pane_columns": 40, "pane_rows": 24},
            "terminal_10": {"pane_x": 40, "pane_y": 0, "pane_columns": 40, "pane_rows": 24},
        }
        with mock.patch.object(hunk_stream, "clients", return_value=[("1", "terminal_10")]), \
             mock.patch.object(hunk_stream, "pane_map", return_value=panes), \
             mock.patch.object(hunk_stream, "zellij"), \
             mock.patch.object(hunk_stream.time, "monotonic", clock.monotonic), \
             mock.patch.object(hunk_stream.time, "sleep", clock.sleep):
            hunk_stream.focus_guard("s", "terminal_9", "terminal_10", 0.1, 0.02)

        self.assertLessEqual(clock.now, 0.15)

    def test_launches_one_detached_guard_with_null_stdio(self):
        with mock.patch.object(hunk_stream.subprocess, "Popen") as popen:
            hunk_stream.launch_focus_guard("s", "terminal_9", "terminal_10")

        popen.assert_called_once()
        args, kwargs = popen.call_args
        self.assertEqual(args[0], [
            sys.executable, str(SCRIPT), "focus-guard", "--session", "s",
            "--original", "terminal_9", "--watcher", "terminal_10",
        ])
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)
        self.assertTrue(kwargs["start_new_session"])
        self.assertTrue(kwargs["close_fds"])


if __name__ == "__main__":
    unittest.main()
