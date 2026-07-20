#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pane-identity.py"
PEER = ROOT / "scripts" / "zellij-peer.sh"
STATUS = ROOT / "scripts" / "zellij-agent-status.sh"
ZJ = ROOT / "scripts" / "zj.sh"


class PaneIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = {**os.environ, "XDG_CACHE_HOME": self.temp.name}
        self.bin = Path(self.temp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.temp.name) / "zellij.log"
        fake = self.bin / "zellij"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "args = sys.argv[1:]\n"
            "with open(os.environ['ZJ_FAKE_LOG'], 'a') as out:\n"
            "    out.write(json.dumps(args) + '\\n')\n"
            "if 'list-panes' in args:\n"
            "    print(os.environ.get('ZJ_FAKE_PANES', '[]'))\n"
            "elif 'list-clients' in args:\n"
            "    print('CLIENT')\n"
            "elif 'new-pane' in args:\n"
            "    print(os.environ.get('ZJ_FAKE_NEW_PANE', 'terminal_2'))\n"
        )
        fake.chmod(0o755)
        self.env.update({
            "PATH": f"{self.bin}{os.pathsep}{self.env['PATH']}",
            "ZJ_FAKE_LOG": str(self.log),
            "ZJ_FAKE_PANES": "[]",
            "ZJ_FAKE_NEW_PANE": "terminal_2",
            "ZAH_IDENTITY_SCRIPT": str(SCRIPT),
        })

    def run_cli(self, *args, check=True):
        result = subprocess.run(
            ["python3", str(SCRIPT), *args],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        if check and result.returncode:
            self.fail(f"command failed ({result.returncode}): {result.stderr}")
        return result

    def assign(self, session="alpha", pane="terminal_1", **values):
        args = ["assign", "--session", session, "--pane", pane]
        for key, value in values.items():
            args.extend([f"--{key.replace('_', '-')}", value])
        return json.loads(self.run_cli(*args).stdout)

    def child(self, pane, parent, session="alpha", **values):
        args = [
            "child", "--session", session, "--pane", pane, "--parent", parent,
        ]
        for key, value in values.items():
            args.extend([f"--{key.replace('_', '-')}", value])
        return json.loads(self.run_cli(*args).stdout)

    def cache_file(self, session, pane):
        return (
            Path(self.temp.name)
            / "zellij-agent-herder" / "panes" / session / f"{pane}.json"
        )

    def test_useful_native_name_is_preferred(self):
        identity = self.assign(native_name="schema-review")
        self.assertEqual("schema-review", identity["name"])
        self.assertEqual("s-r", identity["short"])
        self.assertEqual([], identity["ancestors"])

    def test_generic_native_name_classes_use_fallback(self):
        generic = [
            "agent", "claude", "codex", "yolo", "yolo-claude", "yolo-codex",
            "⠋ claude", "⣾ codex", "mk-skills", "curated-agent-skills",
        ]
        for index, name in enumerate(generic):
            with self.subTest(name=name):
                identity = self.assign(
                    pane=f"terminal_{index}",
                    native_name=name,
                    cwd="/tmp/curated-agent-skills",
                    repo_name="mk-skills",
                )
                self.assertRegex(identity["name"], r"^[a-z]+-[a-z]+$")
                self.assertNotIn(identity["name"], {
                    "agent", "claude", "codex", "yolo-claude", "yolo-codex",
                })

    def test_fallback_is_persisted_and_deterministic(self):
        first = self.assign(native_name="agent")
        second = self.assign(native_name="different-useful-name")
        self.assertEqual(first, second)
        self.assertEqual(first, json.loads(self.cache_file("alpha", "terminal_1").read_text()))

    def test_malformed_cached_identity_is_replaced(self):
        cache = self.cache_file("alpha", "terminal_1")
        cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps({
            "emoji": "😀", "name": 3, "short": [], "ancestors": "not-a-list",
        }))
        identity = self.assign(native_name="reviewer")
        self.assertEqual("reviewer", identity["name"])
        self.assertIn(identity["emoji"], self.load_module().EMOJIS)

    def test_emoji_allowlist_contains_only_single_concrete_symbols(self):
        module = self.load_module()
        forbidden = set("😀😂🙂🤖👋👍❤️⚡⭐🔴🟦🏳🇺")
        self.assertGreater(len(module.EMOJIS), 12)
        for emoji in module.EMOJIS:
            self.assertNotIn(emoji, forbidden)
            self.assertNotIn("\ufe0f", emoji)
            self.assertNotIn("\u200d", emoji)
            self.assertEqual(1, len(emoji), emoji)

    @staticmethod
    def load_module():
        spec = importlib.util.spec_from_file_location("pane_identity", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_parent_child_and_grandchild_render_from_stored_ancestry(self):
        parent = self.assign(native_name="schema-review")
        child = self.child("terminal_2", "terminal_1", native_name="api-worker")
        grandchild = self.child("terminal_3", "terminal_2", native_name="test-runner")
        parent_summary = {k: parent[k] for k in ("emoji", "name", "short")}
        child_summary = {k: child[k] for k in ("emoji", "name", "short")}
        self.assertEqual([parent_summary], child["ancestors"])
        self.assertEqual([parent_summary, child_summary], grandchild["ancestors"])

        title = self.run_cli(
            "render", "--session", "alpha", "--pane", "terminal_3", "--status", "working",
        ).stdout.rstrip("\n")
        self.assertEqual(
            f"{parent['emoji']} s-r > {child['emoji']} a-w > "
            f"{grandchild['emoji']} test-runner · working",
            title,
        )

    def test_render_preserves_exact_status_suffix_and_long_ancestor_initials(self):
        parent = self.assign(native_name="extraordinarily-long-name")
        child = self.child("terminal_2", "terminal_1", native_name="focused-worker")
        title = self.run_cli(
            "render", "--session", "alpha", "--pane", "terminal_2", "--status", "blocked",
        ).stdout.rstrip("\n")
        self.assertEqual(
            f"{parent['emoji']} e-l-n > {child['emoji']} focused-worker · blocked",
            title,
        )
        self.assertEqual(" · blocked", title[-10:])

    def test_root_render_persists_display_label_and_parenthesizes_identity(self):
        preferred = self.assign(
            pane="terminal_8",
            native_name="agent",
            display_label="release-console",
            cwd="/tmp/curated-agent-skills",
            repo_name="mk-skills",
        )
        self.assertEqual("release-console", preferred["label"])
        preferred_title = self.run_cli(
            "render", "--session", "alpha", "--pane", "terminal_8", "--status", "idle",
        ).stdout.rstrip("\n")
        self.assertEqual(
            f"release-console ({preferred['emoji']} {preferred['name']}) · idle",
            preferred_title,
        )

        fallback = self.assign(
            pane="terminal_9",
            native_name="codex",
            display_label="⠋ codex",
            cwd="/tmp/curated-agent-skills",
            repo_name="mk-skills",
        )
        self.assertEqual("mk-skills", fallback["label"])
        persisted = self.assign(
            pane="terminal_9", native_name="new-name", display_label="changed-label",
        )
        self.assertEqual(fallback, persisted)
        fallback_title = self.run_cli(
            "render", "--session", "alpha", "--pane", "terminal_9", "--status", "working",
        ).stdout.rstrip("\n")
        self.assertEqual(
            f"mk-skills ({fallback['emoji']} {fallback['name']}) · working",
            fallback_title,
        )
        self.assertEqual(" · working", fallback_title[-10:])

    def test_pane_ids_are_session_scoped_and_removal_is_isolated(self):
        alpha = self.assign(session="alpha", native_name="agent")
        beta = self.assign(session="beta", native_name="agent")
        self.assertTrue(self.cache_file("alpha", "terminal_1").exists())
        self.assertTrue(self.cache_file("beta", "terminal_1").exists())
        self.assertNotEqual(alpha, beta)

        self.run_cli("remove", "--session", "alpha", "--pane", "terminal_1")
        self.assertFalse(self.cache_file("alpha", "terminal_1").exists())
        self.assertTrue(self.cache_file("beta", "terminal_1").exists())

    def test_status_hook_initializes_native_identity_and_preserves_suffix(self):
        env = {
            **self.env,
            "ZELLIJ_PANE_ID": "1",
            "ZELLIJ_SESSION_NAME": "alpha",
            "ZJ_FAKE_PANES": json.dumps([{"id": 1, "title": "claude"}]),
        }
        working = subprocess.run(
            ["sh", str(STATUS)],
            input=json.dumps({
                "hook_event_name": "UserPromptSubmit",
                "session_name": "schema-review",
                "cwd": "/tmp/project",
            }),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, working.returncode, working.stderr)
        identity = json.loads(self.cache_file("alpha", "terminal_1").read_text())
        self.assertEqual("schema-review", identity["name"])
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(" · working", calls[-1][-1][-10:])

        ended = subprocess.run(
            ["sh", str(STATUS)],
            input=json.dumps({"hook_event_name": "SessionEnd"}),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, ended.returncode, ended.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertNotIn(" · ", calls[-1][-1])
        self.assertIn(identity["name"], calls[-1][-1])

    def test_peer_start_assigns_child_after_spawn_and_close_removes_cache(self):
        parent = self.assign(native_name="orchestrator")
        env = {
            **self.env,
            "ZELLIJ_PANE_ID": "1",
            "ZELLIJ_SESSION_NAME": "alpha",
            "ZJ_SESSION": "alpha",
            "ZJ_FAKE_PANES": json.dumps([{"id": 2, "title": "reviewer"}]),
        }
        started = subprocess.run(
            ["bash", str(PEER), "start", "reviewer", "--cwd", "/tmp/project", "--", "claude"],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, started.returncode, started.stderr)
        self.assertEqual("terminal_2", started.stdout.strip())
        child = json.loads(self.cache_file("alpha", "terminal_2").read_text())
        self.assertEqual("reviewer", child["name"])
        self.assertEqual(
            [{k: parent[k] for k in ("emoji", "name", "short")}],
            child["ancestors"],
        )

        closed = subprocess.run(
            ["bash", str(PEER), "close", "terminal_2"],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, closed.returncode, closed.stderr)
        self.assertFalse(self.cache_file("alpha", "terminal_2").exists())

    def test_resolver_matches_stable_identity_name(self):
        self.assign(native_name="orchestrator")
        child = self.child("terminal_2", "terminal_1", native_name="reviewer")
        rendered = self.run_cli(
            "render", "--session", "alpha", "--pane", "terminal_2", "--status", "idle",
        ).stdout.strip()
        panes = json.dumps({"id": "terminal_2", "title": rendered})
        command = (
            f'source "{ZJ}"; '
            f'_zj_panes() {{ printf \'%s\\n\' \'{panes}\'; }}; '
            'zj_resolve_id reviewer'
        )
        result = subprocess.run(
            ["bash", "-c", command],
            text=True,
            capture_output=True,
            env={**self.env, "ZJ_SESSION": "alpha"},
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("terminal_2", result.stdout.strip())

    def test_sourced_helper_discovers_adjacent_identity_script(self):
        env = {**self.env, "HOME": self.temp.name}
        env.pop("ZAH_IDENTITY_SCRIPT", None)
        env.pop("ZJ_IDENTITY_SCRIPT", None)
        result = subprocess.run(
            ["bash", "-c", f'source "{ZJ}"; printf %s "$ZJ_IDENTITY_SCRIPT"'],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(SCRIPT), result.stdout)


if __name__ == "__main__":
    unittest.main()
