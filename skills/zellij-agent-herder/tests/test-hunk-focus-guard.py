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
    def test_spawn_stacks_behind_parent_when_tab_has_four_visible_panes(self):
        visible = [
            {"id": number, "tab_id": 7, "is_suppressed": False}
            for number in range(1, 5)
        ]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            if args[0] == "new-pane":
                return "terminal_10"
            return ""

        with mock.patch.object(hunk_stream, "clients", return_value=[]), \
             mock.patch.object(hunk_stream, "panes", return_value=visible), \
             mock.patch.object(hunk_stream, "pane_exists", return_value=True), \
             mock.patch.object(hunk_stream, "pane_map", side_effect=[
                 {
                     "terminal_1": {
                         "id": 1, "pane_x": 0, "pane_y": 0,
                         "pane_columns": 40, "pane_rows": 1,
                     },
                     "terminal_10": {
                         "id": 10, "pane_x": 0, "pane_y": 1,
                         "pane_columns": 40, "pane_rows": 23,
                     },
                 },
                 {
                     "terminal_1": {
                         "id": 1, "pane_x": 0, "pane_y": 0,
                         "pane_columns": 40, "pane_rows": 23,
                     },
                     "terminal_10": {
                         "id": 10, "pane_x": 0, "pane_y": 23,
                         "pane_columns": 40, "pane_rows": 1,
                     },
                 },
             ]), \
             mock.patch.object(hunk_stream, "zellij", side_effect=zellij):
            spawned = hunk_stream.spawn_hunk({
                "session": "s", "parent_pane": "terminal_1",
                "root": "/repo", "base": "base",
            }, "review")

        self.assertEqual(spawned, "terminal_10")
        new_pane = next(command for command in commands if command[0] == "new-pane")
        self.assertIn("--floating", new_pane)
        self.assertIn(["stack-panes", "--", "terminal_1", "terminal_10"], commands)
        stack_index = commands.index(
            ["stack-panes", "--", "terminal_1", "terminal_10"],
        )
        self.assertEqual(
            commands[stack_index + 1],
            ["focus-pane-id", "terminal_1"],
        )

    def test_failed_stack_falls_back_to_floating_review(self):
        visible = [{"id": number, "tab_id": 7} for number in range(1, 5)]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "terminal_10" if args[0] == "new-pane" else ""

        with mock.patch.object(hunk_stream, "clients", return_value=[]), \
             mock.patch.object(hunk_stream, "panes", return_value=visible), \
             mock.patch.object(hunk_stream, "pane_exists", return_value=True), \
             mock.patch.object(hunk_stream, "pane_map", return_value={
                 "terminal_1": {"id": 1},
                 "terminal_10": {"id": 10, "is_floating": True},
             }), \
             mock.patch.object(hunk_stream.time, "sleep"), \
             mock.patch.object(hunk_stream, "zellij", side_effect=zellij):
            hunk_stream.spawn_hunk({
                "session": "s", "parent_pane": "terminal_1",
                "root": "/repo", "base": "base",
            }, "review")

        new_pane = next(command for command in commands if command[0] == "new-pane")
        self.assertIn("--floating", new_pane)
        self.assertFalse(any(
            command[0] == "toggle-pane-embed-or-floating"
            for command in commands
        ))

    def test_diagonal_focus_routes_toward_target(self):
        current = {
            "pane_x": 0, "pane_y": 0,
            "pane_columns": 40, "pane_rows": 20,
        }
        wanted = {
            "pane_x": 80, "pane_y": 40,
            "pane_columns": 40, "pane_rows": 20,
        }
        self.assertEqual(hunk_stream.focus_direction(current, wanted), "right")

    def test_restore_focus_recalculates_after_intermediate_pane(self):
        focused = iter([
            [("1", "terminal_0")],
            [("1", "terminal_14")],
            [("1", "terminal_14")],
            [("1", "terminal_17")],
        ])
        panes = {
            "terminal_0": {
                "pane_x": 0, "pane_y": 0,
                "pane_columns": 40, "pane_rows": 20,
            },
            "terminal_14": {
                "pane_x": 40, "pane_y": 20,
                "pane_columns": 40, "pane_rows": 20,
            },
            "terminal_17": {
                "pane_x": 40, "pane_y": 40,
                "pane_columns": 40, "pane_rows": 20,
            },
        }
        move = mock.Mock()
        with mock.patch.object(
            hunk_stream, "clients", side_effect=lambda _s: next(focused)
        ), mock.patch.object(
            hunk_stream, "pane_map", return_value=panes
        ), mock.patch.object(
            hunk_stream, "zellij", move
        ):
            restored = hunk_stream.restore_focus("s", "terminal_17")

        self.assertTrue(restored)
        self.assertEqual(move.call_count, 2)

    def test_spawn_does_not_count_suppressed_or_other_tab_panes(self):
        panes = [
            {"id": 1, "tab_id": 7},
            {"id": 2, "tab_id": 7},
            {"id": 3, "tab_id": 7},
            {"id": 4, "tab_id": 7, "is_suppressed": True},
            {"id": 5, "tab_id": 9},
        ]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "terminal_10" if args[0] == "new-pane" else ""

        with mock.patch.object(hunk_stream, "clients", return_value=[]), \
             mock.patch.object(hunk_stream, "panes", return_value=panes), \
             mock.patch.object(hunk_stream, "pane_exists", return_value=True), \
             mock.patch.object(hunk_stream, "zellij", side_effect=zellij):
            hunk_stream.spawn_hunk({
                "session": "s", "parent_pane": "terminal_1",
                "root": "/repo", "base": "base",
            }, "review")

        self.assertFalse(any(command[0] == "stack-panes" for command in commands))

    def test_spawn_targets_parent_tab_and_floats_when_adjacency_fails(self):
        panes = [
            {"id": 1, "tab_id": 7},
            {"id": 2, "tab_id": 7},
            {"id": 8, "tab_id": 9},
        ]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "terminal_10" if args[0] == "new-pane" else ""

        with mock.patch.object(
            hunk_stream, "clients", return_value=[("1", "terminal_8")]
        ), mock.patch.object(
            hunk_stream, "panes", return_value=panes
        ), mock.patch.object(
            hunk_stream, "pane_exists", return_value=True
        ), mock.patch.object(
            hunk_stream, "pane_map", return_value={
                "terminal_1": panes[0],
                "terminal_8": panes[2],
                "terminal_10": {"id": 10, "tab_id": 7},
            }
        ), mock.patch.object(
            hunk_stream, "place_right", return_value=False
        ), mock.patch.object(
            hunk_stream, "restore_focus"
        ), mock.patch.object(
            hunk_stream, "launch_focus_guard"
        ), mock.patch.object(
            hunk_stream, "zellij", side_effect=zellij
        ):
            hunk_stream.spawn_hunk({
                "session": "s", "parent_pane": "terminal_1",
                "root": "/repo", "base": "base",
            }, "review")

        new_pane = next(command for command in commands if command[0] == "new-pane")
        self.assertEqual(new_pane[1:3], ["--tab-id", "7"])
        self.assertIn(
            ["toggle-pane-embed-or-floating", "-p", "terminal_10"], commands,
        )
        self.assertIn([
            "change-floating-pane-coordinates", "-p", "terminal_10",
            "--width", "45%", "--height", "70%", "--x", "52%", "--y", "15%",
        ], commands)

    def test_moves_review_into_reserved_geometry(self):
        pane_maps = iter([
            {
                "terminal_10": {
                    "pane_x": 0, "pane_y": 30,
                    "pane_columns": 40, "pane_rows": 20,
                },
            },
            {
                "terminal_10": {
                    "pane_x": 40, "pane_y": 0,
                    "pane_columns": 40, "pane_rows": 30,
                },
            },
        ])
        move = mock.Mock()
        with mock.patch.object(
            hunk_stream, "pane_map", side_effect=lambda _s: next(pane_maps)
        ), mock.patch.object(hunk_stream, "zellij", move):
            placed = hunk_stream.move_to_reserved_slot(
                "s", "terminal_10", (40, 0, 40, 30),
            )

        self.assertTrue(placed)
        move.assert_called_once_with(
            "s", ["move-pane", "-p", "terminal_10", "up"],
        )

    def test_reserved_split_is_closed_after_review_takes_its_geometry(self):
        parent = {
            "pane_x": 0, "pane_y": 0,
            "pane_columns": 40, "pane_rows": 30,
        }
        slot = {
            "pane_x": 40, "pane_y": 0,
            "pane_columns": 40, "pane_rows": 30,
        }
        pane_maps = iter([
            {"terminal_1": parent, "terminal_20": slot},
            {"terminal_1": parent, "terminal_10": slot},
        ])
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "terminal_20" if args[0] == "new-pane" else ""

        with mock.patch.object(
            hunk_stream, "clients",
            side_effect=[
                [("1", "terminal_8")],
                [("1", "terminal_1")],
            ],
        ), mock.patch.object(
            hunk_stream, "restore_focus"
        ) as focus, mock.patch.object(
            hunk_stream, "pane_exists", return_value=True
        ), mock.patch.object(
            hunk_stream, "pane_map", side_effect=lambda _s: next(pane_maps)
        ), mock.patch.object(
            hunk_stream, "move_to_reserved_slot", return_value=True
        ) as move, mock.patch.object(
            hunk_stream, "zellij", side_effect=zellij
        ):
            placed = hunk_stream.place_via_reserved_split(
                "s", "terminal_1", "terminal_10", 7,
            )

        self.assertTrue(placed)
        focus.assert_called_once_with("s", "terminal_1")
        move.assert_called_once_with(
            "s", "terminal_10", (40, 0, 40, 30),
        )
        self.assertIn(["close-pane", "-p", "terminal_20"], commands)

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
