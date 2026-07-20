#!/usr/bin/env python3
"""Stable identity and persistent state primitives for Hunk work streams."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Iterator
from typing import Any


STATE_FIELDS = (
    "version", "key", "generation", "session", "parent_pane", "pane_id",
    "root", "common_dir", "base", "kind", "signature", "dismissed_signature",
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
    args = parser.parse_args()
    if args.command == "signature":
        print(diff_signature(args.root, args.base))
    else:
        root = canonical_path(args.root)
        print(stream_key(
            args.session, args.parent, git_common_dir(root),
            {"root": root, "kind": args.kind},
        ))


if __name__ == "__main__":
    main()
