#!/usr/bin/env python3
"""Deterministic tests for Hunk pane placement."""

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "hunk-stream.py"
SPEC = importlib.util.spec_from_file_location("hunk_stream", SCRIPT)
assert SPEC and SPEC.loader
hunk_stream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hunk_stream)


class HunkPlacementTests(unittest.TestCase):
    def test_spawn_stacks_behind_parent_when_tab_has_four_visible_panes(self):
        visible = [
            {"id": number, "tab_id": 7, "is_suppressed": False}
            for number in range(1, 5)
        ]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "terminal_10" if args[0] == "new-pane" else ""

        with mock.patch.dict(hunk_stream.os.environ, {"ZELLIJ_PANE_ID": "1"}), \
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
        self.assertIn("--no-focus", new_pane)
        self.assertIn("--floating", new_pane)
        self.assertNotIn("--direction", new_pane)
        self.assertIn(["stack-panes", "--", "terminal_1", "terminal_10"], commands)

    def test_failed_stack_keeps_initial_floating_review(self):
        visible = [{"id": number, "tab_id": 7} for number in range(1, 5)]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "terminal_10" if args[0] == "new-pane" else ""

        with mock.patch.object(hunk_stream, "panes", return_value=visible), \
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
        self.assertIn("--no-focus", new_pane)
        self.assertIn("--floating", new_pane)
        self.assertFalse(any(
            command[0] == "toggle-pane-embed-or-floating"
            for command in commands
        ))

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

        with mock.patch.object(hunk_stream, "panes", return_value=panes), \
             mock.patch.object(hunk_stream, "pane_exists", return_value=True), \
             mock.patch.object(hunk_stream, "pane_map", return_value={}), \
             mock.patch.object(hunk_stream, "zellij", side_effect=zellij):
            hunk_stream.spawn_hunk({
                "session": "s", "parent_pane": "terminal_1",
                "root": "/repo", "base": "base",
            }, "review")

        self.assertFalse(any(command[0] == "stack-panes" for command in commands))

    def test_spawn_targets_parent_tab_and_keeps_tiled_when_adjacency_fails(self):
        panes = [
            {"id": 1, "tab_id": 7},
            {"id": 2, "tab_id": 7},
            {"id": 8, "tab_id": 9},
        ]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "terminal_10" if args[0] == "new-pane" else ""

        with mock.patch.dict(hunk_stream.os.environ, {"ZELLIJ_PANE_ID": "1"}), \
             mock.patch.object(hunk_stream, "panes", return_value=panes), \
             mock.patch.object(hunk_stream, "pane_exists", return_value=True), \
             mock.patch.object(hunk_stream, "pane_map", return_value={
                 "terminal_1": panes[0],
                 "terminal_10": {"id": 10, "tab_id": 7},
             }), \
             mock.patch.object(hunk_stream, "place_right", return_value=False), \
             mock.patch.object(hunk_stream, "zellij", side_effect=zellij):
            hunk_stream.spawn_hunk({
                "session": "s", "parent_pane": "terminal_1",
                "root": "/repo", "base": "base",
            }, "review")

        new_pane = next(command for command in commands if command[0] == "new-pane")
        self.assertEqual(new_pane[1:3], ["--tab-id", "7"])
        self.assertIn("--no-focus", new_pane)
        self.assertIn("--direction", new_pane)
        self.assertEqual(
            new_pane[new_pane.index("--direction") + 1],
            "right",
        )
        self.assertNotIn(
            ["toggle-pane-embed-or-floating", "-p", "terminal_10"], commands,
        )


if __name__ == "__main__":
    unittest.main()
