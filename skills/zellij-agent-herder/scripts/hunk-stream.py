#!/usr/bin/env python3
"""Stable identity and persistent state primitives for Hunk work streams."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Iterator
from typing import Any


STATE_FIELDS = (
    "version", "key", "generation", "session", "parent_pane", "pane_id",
    "root", "common_dir", "base", "kind", "label", "signature",
    "dismissed_signature", "complete",
)


def canonical_path(path: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def run_git(root: str, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", root, *args], check=True, stdout=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8", errors="surrogateescape")


def nul_git_paths(root: str, args: list[str]) -> list[str]:
    output = subprocess.run(
        ["git", "-C", root, *args], check=True, stdout=subprocess.PIPE,
    ).stdout
    return [part.decode("utf-8", errors="surrogateescape") for part in output.split(b"\0") if part]


def git_common_dir(root: str) -> str:
    root = canonical_path(root)
    common_dir = run_git(root, ["rev-parse", "--git-common-dir"]).strip()
    if not os.path.isabs(common_dir):
        common_dir = os.path.join(root, common_dir)
    return canonical_path(common_dir)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def diff_signature(root: str, base: str) -> str:
    root = canonical_path(root)
    payload = {
        "base": base,
        "tracked": run_git(root, ["diff", "--binary", "--no-ext-diff", base, "--"]),
        "untracked": [
            {"path": path, "sha256": sha256_file(os.path.join(root, path))}
            for path in sorted(nul_git_paths(root, ["ls-files", "--others", "--exclude-standard", "-z"]))
        ],
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def normalize_parent(parent: str) -> str:
    return parent if parent.startswith(("terminal_", "plugin_")) else f"terminal_{parent}"


def stream_key(session: str, parent: str, common_dir: str, identity: dict[str, str]) -> str:
    payload = {
        "session": session,
        "parent": normalize_parent(parent),
        "common_dir": canonical_path(common_dir),
        "root": canonical_path(identity["root"]),
        "kind": identity["kind"],
    }
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def empty_state(key: str) -> dict[str, Any]:
    state = {field: None for field in STATE_FIELDS}
    state.update(version=1, key=key, generation=0)
    return state


@contextlib.contextmanager
def locked_state(cache_dir: str, key: str) -> Iterator[dict[str, Any]]:
    streams_dir = os.path.join(canonical_path(cache_dir), "zellij-agent-herder", "streams")
    os.makedirs(streams_dir, exist_ok=True)
    state_path = os.path.join(streams_dir, f"{key}.json")
    lock_path = os.path.join(streams_dir, f"{key}.lock")
    with open(lock_path, "a+b") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            with open(state_path, encoding="utf-8") as source:
                state = json.load(source)
        except FileNotFoundError:
            state = empty_state(key)
        try:
            yield state
        except BaseException:
            raise
        else:
            fd, temp_path = tempfile.mkstemp(prefix=f".{key}.", dir=streams_dir)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as target:
                    json.dump(state, target, sort_keys=True, separators=(",", ":"))
                    target.write("\n")
                    target.flush()
                    os.fsync(target.fileno())
                os.replace(temp_path, state_path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)


def cache_root() -> str:
    return os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))


def review_title(session: str, parent: str) -> str:
    path = os.path.join(
        cache_root(), "zellij-agent-herder", "panes", session, f"{parent}.json",
    )
    try:
        with open(path, encoding="utf-8") as source:
            identity = json.load(source)
        lineage = [*identity["ancestors"], identity]
        emojis = [item["emoji"] for item in lineage]
        if not all(isinstance(emoji, str) and emoji for emoji in emojis):
            raise ValueError("invalid pane identity emoji")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        emojis = []
    return " ▸ ".join([*emojis, "🔍"])


def hook_host(payload: dict[str, Any]) -> str:
    return os.environ.get("ZAH_HOST") or (
        "codex" if "model" in payload or "turn_id" in payload else "claude"
    )


def is_subagent(payload: dict[str, Any]) -> bool:
    if any(payload.get(key) for key in ("agent_id", "subagent_id", "subagent")):
        return True
    context = payload.get("context")
    return isinstance(context, dict) and any(
        context.get(key) for key in ("agent_id", "subagent_id", "subagent")
    )


def origin_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id or "/" in session_id:
        return None
    path = os.path.join(
        cache_root(), "zellij-agent-herder", "origins",
        f"{hook_host(payload)}-{session_id}.json",
    )
    try:
        with open(path, encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def edit_payload(payload: dict[str, Any]) -> str:
    if is_subagent(payload) or payload.get("hook_event_name") != "PostToolUse":
        return ""
    edit_tools = (
        ("apply_patch", "Edit", "Write") if hook_host(payload) == "codex"
        else ("Edit", "Write", "MultiEdit", "NotebookEdit")
    )
    if payload.get("tool_name") not in edit_tools:
        return ""
    tool_input = payload.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    start = os.path.dirname(file_path) if isinstance(file_path, str) else payload.get("cwd")
    if not isinstance(start, str) or not os.path.isdir(start):
        start = payload.get("cwd")
    if not isinstance(start, str):
        return ""
    try:
        root = canonical_path(run_git(start, ["rev-parse", "--show-toplevel"]).strip())
    except (OSError, subprocess.CalledProcessError):
        return ""
    origin = origin_record(payload)
    if not origin:
        return ""
    session = origin.get("zellij_session")
    parent = origin.get("parent_pane")
    if not isinstance(session, str) or not session or not isinstance(parent, str):
        return ""
    common_dir = git_common_dir(root)
    key = stream_key(session, parent, common_dir, {"root": root, "kind": "worktree"})
    state_path = os.path.join(cache_root(), "zellij-agent-herder", "streams", f"{key}.json")
    try:
        with open(state_path, encoding="utf-8") as source:
            existing_base = json.load(source).get("base")
    except (OSError, ValueError, AttributeError):
        existing_base = None
    if isinstance(existing_base, str) and existing_base:
        base = existing_base
    else:
        try:
            base = run_git(root, ["merge-base", "HEAD", "@{upstream}"]).strip()
        except subprocess.CalledProcessError:
            base = run_git(root, ["rev-parse", "HEAD"]).strip()
    return ensure_stream(session, parent, root, base, "worktree", None, False)


def zellij(session: str, args: list[str]) -> str:
    result = subprocess.run(
        ["zellij", "--session", session, "action", *args],
        check=True, stdout=subprocess.PIPE, text=True,
    )
    return result.stdout.strip()


def panes(session: str) -> list[dict[str, Any]]:
    value = json.loads(zellij(session, ["list-panes", "-j", "-g", "-s", "-t"]))
    if isinstance(value, dict):
        items: list[Any] = []
        for entry in value.values():
            items.extend(entry if isinstance(entry, list) else [entry])
    else:
        items = value
    return [item for item in items if isinstance(item, dict)]


def pane_id(pane: dict[str, Any]) -> str:
    value = pane.get("id")
    if isinstance(value, int):
        return f"{'plugin' if pane.get('is_plugin') else 'terminal'}_{value}"
    return str(value)


def pane_exists(session: str, wanted: str | None) -> bool:
    return bool(wanted) and any(pane_id(item) == wanted for item in panes(session))


def clients(session: str) -> list[tuple[str, str]]:
    lines = zellij(session, ["list-clients"]).splitlines()
    rows: list[tuple[str, str]] = []
    for line in lines[1:]:
        fields = line.split()
        focused = next((field for field in fields if field.startswith(("terminal_", "plugin_"))), None)
        if focused:
            rows.append((fields[0], focused))
    return rows


def pane_map(session: str) -> dict[str, dict[str, Any]]:
    return {pane_id(item): item for item in panes(session)}


def visible_panes_in_parent_tab(items: list[dict[str, Any]], parent_id: str) -> int:
    parent = next((item for item in items if pane_id(item) == parent_id), None)
    if parent is None:
        return 0
    tab_id = parent.get("tab_id")
    tab_position = parent.get("tab_position")

    def same_tab(item: dict[str, Any]) -> bool:
        if tab_id is not None:
            return item.get("tab_id") == tab_id
        return tab_position is not None and item.get("tab_position") == tab_position

    return sum(
        same_tab(item) and not item.get("is_suppressed", False)
        for item in items
    )


def geometry(pane: dict[str, Any]) -> tuple[int, int, int, int] | None:
    values = tuple(pane.get(key) for key in ("pane_x", "pane_y", "pane_columns", "pane_rows"))
    if not all(isinstance(value, int) for value in values):
        return None
    x, y, width, height = values
    return (x, y, width, height) if width > 0 and height > 0 else None


def overlaps(start_a: int, length_a: int, start_b: int, length_b: int) -> bool:
    return start_a < start_b + length_b and start_b < start_a + length_a


def immediately_right(parent: dict[str, Any], watcher: dict[str, Any]) -> bool:
    parent_rect = geometry(parent)
    watcher_rect = geometry(watcher)
    if parent_rect is None or watcher_rect is None:
        return False
    px, py, pw, ph = parent_rect
    wx, wy, _, wh = watcher_rect
    return wx == px + pw and overlaps(py, ph, wy, wh)


def placement_direction(parent: dict[str, Any], watcher: dict[str, Any]) -> str | None:
    parent_rect = geometry(parent)
    watcher_rect = geometry(watcher)
    if parent_rect is None or watcher_rect is None:
        return None
    px, py, pw, ph = parent_rect
    wx, wy, _, wh = watcher_rect
    if not overlaps(py, ph, wy, wh):
        return None
    target_x = px + pw
    if wx > target_x:
        return "left"
    if wx < target_x:
        return "right"
    return None


def focus_direction(current: dict[str, Any], wanted: dict[str, Any]) -> str | None:
    current_rect = geometry(current)
    wanted_rect = geometry(wanted)
    if current_rect is None or wanted_rect is None:
        return None
    cx, cy, cw, ch = current_rect
    wx, wy, ww, wh = wanted_rect
    if overlaps(cy, ch, wy, wh):
        if wx + ww <= cx:
            return "left"
        if cx + cw <= wx:
            return "right"
    if overlaps(cx, cw, wx, ww):
        if wy + wh <= cy:
            return "up"
        if cy + ch <= wy:
            return "down"
    return None


def place_right(session: str, parent_id: str, watcher_id: str, limit: int = 8) -> None:
    for attempt in range(limit + 1):
        current = pane_map(session)
        parent = current.get(parent_id)
        watcher = current.get(watcher_id)
        if parent is None or watcher is None or immediately_right(parent, watcher):
            return
        direction = placement_direction(parent, watcher)
        if direction is None or attempt == limit:
            return
        zellij(session, ["move-pane", "-p", watcher_id, direction])


def restore_focus(session: str, wanted_id: str, limit: int = 8) -> None:
    for attempt in range(limit + 1):
        rows = clients(session)
        if len(rows) != 1:
            return
        current_id = rows[0][1]
        if current_id == wanted_id:
            return
        current = pane_map(session)
        focused = current.get(current_id)
        wanted = current.get(wanted_id)
        if focused is None or wanted is None:
            return
        direction = focus_direction(focused, wanted)
        if direction is None or attempt == limit:
            return
        zellij(session, ["move-focus", direction])
        for _ in range(10):
            rows = clients(session)
            if len(rows) != 1 or rows[0][1] == wanted_id:
                return
            time.sleep(0.01)


def restore_guard_focus(
    session: str, original_id: str, watcher_id: str, limit: int = 8,
    deadline: float | None = None,
) -> bool:
    for attempt in range(limit + 1):
        if deadline is not None and time.monotonic() >= deadline:
            return False
        rows = clients(session)
        if len(rows) != 1:
            return False
        focused_id = rows[0][1]
        if focused_id == original_id:
            return True
        if focused_id != watcher_id:
            return False
        current = pane_map(session)
        focused = current.get(watcher_id)
        original = current.get(original_id)
        if focused is None or original is None:
            return False
        direction = focus_direction(focused, original)
        if direction is None or attempt == limit:
            return False
        if deadline is not None and time.monotonic() >= deadline:
            return False
        rows = clients(session)
        if len(rows) != 1:
            return False
        observed = rows[0][1]
        if observed == original_id:
            return True
        if observed != watcher_id:
            return False
        zellij(session, ["move-focus", direction])
        for _ in range(10):
            if deadline is not None and time.monotonic() >= deadline:
                return False
            rows = clients(session)
            if len(rows) != 1:
                return False
            observed = rows[0][1]
            if observed == original_id:
                return True
            if observed != watcher_id:
                return False
            delay = 0.01 if deadline is None else min(0.01, max(0.0, deadline - time.monotonic()))
            time.sleep(delay)
    return False


def focus_guard(
    session: str, original_id: str, watcher_id: str,
    window: float = 1.0, interval: float = 0.02,
) -> None:
    deadline = time.monotonic() + max(0.0, window)
    while time.monotonic() < deadline:
        try:
            rows = clients(session)
            current = pane_map(session)
        except (OSError, ValueError, subprocess.CalledProcessError):
            return
        if len(rows) != 1 or original_id not in current or watcher_id not in current:
            return
        focused = rows[0][1]
        if focused == watcher_id:
            try:
                if not restore_guard_focus(
                    session, original_id, watcher_id, deadline=deadline,
                ):
                    return
            except (OSError, ValueError, subprocess.CalledProcessError):
                return
        elif focused != original_id:
            return
        remaining = max(0.0, deadline - time.monotonic())
        time.sleep(min(max(0.0, interval), remaining))


def launch_focus_guard(session: str, original_id: str, watcher_id: str) -> None:
    subprocess.Popen(
        [
            sys.executable, os.path.abspath(__file__), "focus-guard",
            "--session", session, "--original", original_id,
            "--watcher", watcher_id,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def request_matches(state: dict[str, Any], request: dict[str, Any]) -> bool:
    fields = ("session", "parent_pane", "root", "common_dir", "base", "kind", "label")
    return all(state.get(field) == request[field] for field in fields)


def spawn_hunk(request: dict[str, Any], title: str) -> str:
    session = request["session"]
    parent = request["parent_pane"]
    rows = clients(session)
    old_focus = rows[0][1] if len(rows) == 1 else None
    stack_behind_parent = visible_panes_in_parent_tab(panes(session), parent) >= 4
    args = ["new-pane",
        "--cwd", request["root"], "--name", title, "--",
        "hunk", "diff", request["base"], "--watch",
    ]
    output = zellij(session, args).splitlines()
    returned = output[-1] if output else ""
    if pane_exists(session, returned):
        spawned = returned
    else:
        matches = [pane_id(item) for item in panes(session) if item.get("title") == title]
        if len(matches) != 1:
            raise RuntimeError(f"spawned pane could not be verified: {returned!r}")
        spawned = matches[0]
    zellij(session, ["rename-pane", "-p", spawned, review_title(session, parent)])
    if stack_behind_parent:
        zellij(session, ["stack-panes", "--", parent, spawned])
    if old_focus is not None:
        try:
            current = pane_map(session)
            if parent in current and old_focus in current:
                if not stack_behind_parent:
                    place_right(session, parent, spawned)
                restore_focus(session, old_focus)
                launch_focus_guard(session, old_focus, spawned)
        except (OSError, ValueError, subprocess.CalledProcessError):
            pass
    return spawned


def ensure_stream(
    session: str, parent: str, root: str, base: str, kind: str,
    label: str | None, explicit: bool,
) -> str:
    root = canonical_path(root)
    common_dir = git_common_dir(root)
    parent = normalize_parent(parent)
    label = label or os.path.basename(root)
    request = {
        "session": session, "parent_pane": parent, "root": root,
        "common_dir": common_dir, "base": base, "kind": kind, "label": label,
    }
    key = stream_key(session, parent, common_dir, {"root": root, "kind": kind})
    signature = diff_signature(root, base)
    with locked_state(cache_root(), key) as state:
        present = pane_exists(session, state.get("pane_id"))
        if present and request_matches(state, request):
            state["signature"] = signature
            zellij(
                session,
                ["rename-pane", "-p", str(state["pane_id"]), review_title(session, parent)],
            )
            return str(state["pane_id"])
        if state.get("pane_id") and not present:
            if state.get("signature") == signature and not explicit:
                state["dismissed_signature"] = signature
                return ""
        if state.get("dismissed_signature") == signature and not explicit:
            return ""
        if present:
            zellij(session, ["close-pane", "-p", str(state["pane_id"])])
        generation = int(state.get("generation") or 0) + 1
        title = f"diff:{label}:{key[:8]}:{generation}:{uuid.uuid4().hex[:8]}"
        spawned = spawn_hunk(request, title)
        state.clear()
        state.update(empty_state(key))
        state.update(request)
        state.update(
            generation=generation, pane_id=spawned, signature=signature,
            dismissed_signature=None, complete=False,
        )
        return spawned


def mark_children_complete(session: str, child_ids: list[str]) -> None:
    streams_dir = os.path.join(cache_root(), "zellij-agent-herder", "streams")
    try:
        names = os.listdir(streams_dir)
    except FileNotFoundError:
        names = []
    remaining = set(child_ids)
    for name in names:
        if not name.endswith(".json"):
            continue
        key = name[:-5]
        with locked_state(cache_root(), key) as state:
            child = state.get("pane_id")
            if state.get("session") == session and child in remaining:
                state["complete"] = True
                remaining.discard(child)
    for child in child_ids:
        if pane_exists(session, child):
            zellij(session, ["close-pane", "-p", child])


def rollup_stream(
    session: str, parent: str, root: str, base: str, label: str,
    child_ids: list[str],
) -> str:
    mark_children_complete(session, child_ids)
    return ensure_stream(session, parent, root, base, "aggregate", label, True)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    signature = commands.add_parser("signature")
    signature.add_argument("--root", required=True)
    signature.add_argument("--base", required=True)
    state_key = commands.add_parser("state-key")
    state_key.add_argument("--session", required=True)
    state_key.add_argument("--parent", required=True)
    state_key.add_argument("--root", required=True)
    state_key.add_argument("--kind", required=True)
    ensure = commands.add_parser("ensure")
    ensure.add_argument("--session", required=True)
    ensure.add_argument("--parent", required=True)
    ensure.add_argument("--root", required=True)
    ensure.add_argument("--base", required=True)
    ensure.add_argument("--kind", required=True, choices=("worktree", "aggregate"))
    ensure.add_argument("--label")
    ensure.add_argument("--explicit", action="store_true")
    rollup = commands.add_parser("rollup")
    rollup.add_argument("--session", required=True)
    rollup.add_argument("--parent", required=True)
    rollup.add_argument("--root", required=True)
    rollup.add_argument("--base", required=True)
    rollup.add_argument("--label", required=True)
    rollup.add_argument("--child-pane", action="append", default=[])
    guard = commands.add_parser("focus-guard")
    guard.add_argument("--session", required=True)
    guard.add_argument("--original", required=True)
    guard.add_argument("--watcher", required=True)
    commands.add_parser("edit")
    args = parser.parse_args()
    if args.command == "signature":
        print(diff_signature(args.root, args.base))
    elif args.command == "state-key":
        root = canonical_path(args.root)
        print(stream_key(
            args.session, args.parent, git_common_dir(root),
            {"root": root, "kind": args.kind},
        ))
    elif args.command == "ensure":
        print(ensure_stream(
            args.session, args.parent, args.root, args.base, args.kind,
            args.label, args.explicit,
        ))
    elif args.command == "rollup":
        print(rollup_stream(
            args.session, args.parent, args.root, args.base, args.label,
            args.child_pane,
        ))
    elif args.command == "focus-guard":
        try:
            focus_guard(
                args.session, args.original, args.watcher,
                float(os.environ.get("ZAH_FOCUS_GUARD_WINDOW", "1.0")),
                float(os.environ.get("ZAH_FOCUS_GUARD_INTERVAL", "0.02")),
            )
        except (OSError, ValueError, subprocess.CalledProcessError):
            pass
    else:
        try:
            payload = json.load(sys.stdin)
        except (ValueError, OSError):
            payload = {}
        if isinstance(payload, dict):
            print(edit_payload(payload))


if __name__ == "__main__":
    main()
