#!/usr/bin/env python3
"""Deterministic tests for Hunk review-tab placement."""

import importlib.util
import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "hunk-stream.py"
SPEC = importlib.util.spec_from_file_location("hunk_stream", SCRIPT)
assert SPEC and SPEC.loader
hunk_stream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hunk_stream)


class HunkPlacementTests(unittest.TestCase):
    def test_origin_tab_base_preserved_verbatim(self):
        items = [
            {"id": 1, "tab_id": 7, "tab_name": "󰚩 Bots #1"},
            {"id": 10, "tab_id": 12, "tab_name": "󰚩 Bots #1 - 󱙺 Peers #1"},
        ]
        self.assertEqual(
            hunk_stream.grouped_tab_placement(items, "terminal_1", "Peers"),
            {"base": "󰚩 Bots #1", "number": 1, "tab_id": 12, "reuse": True},
        )

    def test_grouped_tab_name_and_reuse_under_four_visible_panes(self):
        items = [
            {"id": 1, "tab_id": 7, "tab_name": "󰚩 Bots #1"},
            {"id": 2, "tab_id": 7, "tab_name": "󰚩 Bots #1"},
            {"id": 10, "tab_id": 12, "tab_name": "󰚩 Bots #1 - 󱙺 Peers #1"},
            {"id": 11, "tab_id": 12, "tab_name": "󰚩 Bots #1 - 󱙺 Peers #1"},
            {"id": 12, "tab_id": 12, "tab_name": "󰚩 Bots #1 - 󱙺 Peers #1", "is_floating": True},
            {"id": 20, "tab_id": 15, "tab_name": "󰚩 Bots #1 - 󱙺 Peers #2"},
        ]
        self.assertEqual(
            hunk_stream.grouped_tab_placement(items, "terminal_1", "Peers"),
            {"base": "󰚩 Bots #1", "number": 2, "tab_id": 15, "reuse": True},
        )

    def test_grouped_tab_starts_next_number_at_four_visible_panes(self):
        items = [
            {"id": 1, "tab_id": 7, "tab_name": "Bots"},
            *[
                {"id": number, "tab_id": 12, "tab_name": "Bots -  Reviews #1"}
                for number in range(10, 14)
            ],
        ]
        self.assertEqual(
            hunk_stream.grouped_tab_placement(items, "terminal_1", "Reviews"),
            {"base": "Bots", "number": 2, "tab_id": None, "reuse": False},
        )

    def test_spawn_opens_one_background_tab_and_returns_its_pane(self):
        initial = [
            {"id": 1, "tab_id": 7, "title": "agent", "is_plugin": False},
            {"id": 2, "tab_id": 7, "title": "shell", "is_plugin": False},
        ]
        after = [
            *initial,
            {"id": 10, "tab_id": 12, "title": "hunk", "is_plugin": False},
        ]
        commands = []

        def zellij(_session, args):
            commands.append(args)
            return "12" if args[0] == "new-tab" else ""

        request = {
            "session": "s",
            "parent_pane": "terminal_1",
            "root": "/repo",
            "base": "base",
            "label": "review",
        }
        with mock.patch.object(hunk_stream, "panes", side_effect=[initial, after]), \
             mock.patch.object(hunk_stream, "zellij", side_effect=zellij), \
             mock.patch.object(hunk_stream, "review_title", return_value="🦉 ▸ 🔍"):
            spawned, tab_id = hunk_stream.spawn_hunk(request)

        self.assertEqual((spawned, tab_id), ("terminal_10", 12))
        new_tab = next(command for command in commands if command[0] == "new-tab")
        self.assertIn("--no-focus", new_tab)
        self.assertEqual(new_tab[new_tab.index("--cwd") + 1], "/repo")
        self.assertEqual(new_tab[new_tab.index("--name") + 1], "🔍 review")
        self.assertEqual(new_tab[new_tab.index("--") + 1:], hunk_stream.watch_command(request))
        self.assertEqual(new_tab[-4:], ["--session", "s", "--base", "base"])
        self.assertFalse(any(command[0] == "new-pane" for command in commands))
        self.assertFalse(any(command[0] in {"move-pane", "stack-panes"} for command in commands))
        self.assertIn(
            ["rename-pane", "-p", "terminal_10", "🦉 ▸ 🔍"], commands,
        )

    def test_spawn_reuses_newest_review_group_below_four_panes(self):
        initial = [
            {"id": 1, "tab_id": 7, "tab_name": "Bots", "is_plugin": False},
            {"id": 10, "tab_id": 12, "tab_name": "Bots -  Reviews #1", "is_plugin": False},
            {"id": 11, "tab_id": 12, "tab_name": "Bots -  Reviews #1", "is_plugin": False},
        ]
        after = [
            *initial,
            {"id": 20, "tab_id": 12, "tab_name": "Bots -  Reviews #1", "is_plugin": False},
        ]
        commands = []

        with mock.patch.object(hunk_stream, "panes", side_effect=[initial, after]), \
             mock.patch.object(hunk_stream, "zellij", side_effect=lambda _s, args: commands.append(args) or ""), \
             mock.patch.object(hunk_stream, "review_title", return_value="🔍"):
            spawned, tab_id = hunk_stream.spawn_hunk({
                "session": "s", "parent_pane": "terminal_1", "root": "/repo",
                "base": "base", "label": "review",
            })

        self.assertEqual((spawned, tab_id), ("terminal_20", 12))
        self.assertEqual(commands[0][:4], ["new-pane", "--no-focus", "--tab-id", "12"])
        self.assertFalse(any(command[0] == "new-tab" for command in commands))

    def test_spawn_rejects_an_ambiguous_new_tab(self):
        initial = [{"id": 1, "tab_id": 7, "is_plugin": False}]
        after = [
            *initial,
            {"id": 10, "tab_id": 12, "is_plugin": False},
            {"id": 11, "tab_id": 12, "is_plugin": False},
        ]
        with mock.patch.object(hunk_stream, "panes", side_effect=[initial, after]), \
             mock.patch.object(hunk_stream, "zellij", return_value="12"):
            with self.assertRaisesRegex(RuntimeError, "exactly one pane"):
                hunk_stream.spawn_hunk({
                    "session": "s",
                    "parent_pane": "terminal_1",
                    "root": "/repo",
                    "base": "base",
                    "label": "review",
                })

    def test_tab_title_removes_control_characters_and_is_bounded(self):
        title = hunk_stream.review_tab_title({"label": "line\n" + "x" * 100})
        self.assertNotIn("\n", title)
        self.assertLessEqual(len(title), 48)
        self.assertTrue(title.startswith("🔍 "))

    def test_legacy_same_tab_state_migrates_once(self):
        state = {
            "session": "s", "parent_pane": "terminal_1",
            "root": "/repo", "common_dir": "/repo/.git", "base": "base",
            "kind": "worktree", "label": "review", "pane_id": "terminal_9",
            "signature": "signature", "generation": 1,
        }

        @contextlib.contextmanager
        def locked_state(_cache, _key):
            yield state

        @contextlib.contextmanager
        def spawn_lock():
            yield

        commands = []
        with mock.patch.object(hunk_stream, "canonical_path", return_value="/repo"), \
             mock.patch.object(hunk_stream, "git_common_dir", return_value="/repo/.git"), \
             mock.patch.object(hunk_stream, "diff_signature", return_value="signature"), \
             mock.patch.object(hunk_stream, "stream_key", return_value="key"), \
             mock.patch.object(hunk_stream, "locked_state", side_effect=locked_state), \
             mock.patch.object(hunk_stream, "spawn_lock", side_effect=spawn_lock), \
             mock.patch.object(hunk_stream, "active_stream_count", return_value=0), \
             mock.patch.object(hunk_stream, "prune_stream_states"), \
             mock.patch.object(hunk_stream, "pane_exists", return_value=True), \
             mock.patch.object(hunk_stream, "spawn_hunk", return_value=("terminal_10", 12)), \
             mock.patch.object(hunk_stream, "zellij", side_effect=lambda _s, args: commands.append(args) or ""):
            pane = hunk_stream.ensure_stream(
                "s", "terminal_1", "/repo", "base", "worktree", "review", False,
            )

        self.assertEqual(pane, "terminal_10")
        self.assertIn(["close-pane", "-p", "terminal_9"], commands)
        self.assertTrue(state["dedicated_tab"])
        self.assertEqual(state["tab_id"], 12)

    def test_prune_removes_dead_state_and_lock_but_keeps_live_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            streams = Path(temporary) / "zellij-agent-herder" / "streams"
            streams.mkdir(parents=True)
            dead = streams / "dead.json"
            dead.write_text(json.dumps({"session": "dead", "pane_id": "terminal_9"}))
            dead_lock = streams / "dead.lock"
            dead_lock.touch()
            orphan_lock = streams / "orphan.lock"
            orphan_lock.touch()
            live = streams / "live.json"
            live.write_text(json.dumps({"session": "live", "pane_id": "terminal_1"}))
            live_lock = streams / "live.lock"
            live_lock.touch()
            with mock.patch.object(hunk_stream, "cache_root", return_value=temporary), \
                 mock.patch.object(hunk_stream, "zellij_session_status", return_value=({"live"}, {"dead"})), \
                 mock.patch.object(hunk_stream, "panes", return_value=[{"id": 1}]):
                hunk_stream.prune_stream_states("live")
            self.assertFalse(dead.exists())
            self.assertFalse(dead_lock.exists())
            self.assertFalse(orphan_lock.exists())
            self.assertTrue(live.exists())
            self.assertTrue(live_lock.exists())

    def test_ensure_refuses_new_stream_at_global_cap(self):
        with tempfile.TemporaryDirectory() as temporary:
            streams = Path(temporary) / "zellij-agent-herder" / "streams"
            streams.mkdir(parents=True)
            for number in range(4):
                (streams / f"active-{number}.json").write_text(json.dumps({
                    "session": "s" if number == 0 else "other", "pane_id": f"terminal_{number}", "complete": False,
                }))
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ZAH_MAX_ACTIVE_STREAMS", None)
                with mock.patch.object(hunk_stream, "cache_root", return_value=temporary), \
                     mock.patch.object(hunk_stream, "git_common_dir", return_value="/repo/.git"), \
                     mock.patch.object(hunk_stream, "stream_key", return_value="new"), \
                     mock.patch.object(hunk_stream, "diff_signature", return_value="signature"), \
                     mock.patch.object(hunk_stream, "prune_stream_states"), \
                     mock.patch.object(hunk_stream, "zellij_session_status", return_value=({"s", "other"}, set())), \
                     mock.patch.object(hunk_stream, "panes", return_value=[
                         {"id": number} for number in range(4)
                     ]), \
                     mock.patch.object(hunk_stream, "pane_exists", return_value=False), \
                     mock.patch.object(hunk_stream, "spawn_hunk") as spawn:
                    pane = hunk_stream.ensure_stream(
                        "s", "terminal_1", "/repo", "base", "worktree", "review", False,
                    )
            self.assertEqual(pane, "")
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
