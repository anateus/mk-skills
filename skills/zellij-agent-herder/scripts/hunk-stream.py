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
import tempfile
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


def zellij(session: str, args: list[str]) -> str:
    result = subprocess.run(
        ["zellij", "--session", session, "action", *args],
        check=True, stdout=subprocess.PIPE, text=True,
    )
    return result.stdout.strip()


def panes(session: str) -> list[dict[str, Any]]:
    value = json.loads(zellij(session, ["list-panes", "-j"]))
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


def request_matches(state: dict[str, Any], request: dict[str, Any]) -> bool:
    fields = ("session", "parent_pane", "root", "common_dir", "base", "kind", "label")
    return all(state.get(field) == request[field] for field in fields)


def spawn_hunk(request: dict[str, Any], title: str) -> str:
    session = request["session"]
    parent = request["parent_pane"]
    rows = clients(session)
    place_right = len(rows) == 1 and pane_exists(session, parent)
    old_focus = rows[0][1] if place_right else None
    args = ["new-pane"]
    if place_right:
        args.extend(["--direction", "right"])
    args.extend([
        "--cwd", request["root"], "--name", title, "--",
        "hunk", "diff", request["base"], "--watch",
    ])
    try:
        if place_right:
            zellij(session, ["focus-pane-id", parent])
        output = zellij(session, args).splitlines()
        returned = output[-1] if output else ""
    finally:
        if old_focus is not None:
            zellij(session, ["focus-pane-id", old_focus])
    if pane_exists(session, returned):
        return returned
    matches = [pane_id(item) for item in panes(session) if item.get("title") == title]
    if len(matches) != 1:
        raise RuntimeError(f"spawned pane could not be verified: {returned!r}")
    return matches[0]


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
    else:
        print(rollup_stream(
            args.session, args.parent, args.root, args.base, args.label,
            args.child_pane,
        ))


if __name__ == "__main__":
    main()
