#!/usr/bin/env python3
"""Persist and render stable zellij agent-pane identities."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


EMOJIS = (
    "🦀", "🐙", "🦊", "🐢", "🐳", "🦉", "🐝", "🐞",
    "🌿", "🌵", "🍄", "🌲", "🍎", "🍋", "🍞", "🧀",
    "🔨", "🔧", "🪚", "🚲", "🚗", "🚂", "🚀", "📚",
    "🔑", "💡", "🎒", "🧭",
)
ADJECTIVES = (
    "brisk", "calm", "clever", "cosmic", "daring", "eager", "funky",
    "gentle", "glamorous", "lively", "lucid", "nimble", "patient",
    "quiet", "steady", "sunny", "vivid", "witty",
)
NOUNS = (
    "badger", "crab", "falcon", "gecko", "heron", "lemur", "otter",
    "panda", "rabbit", "raven", "tiger", "turtle", "walrus", "yak",
)
GENERIC = re.compile(
    r"^(?:yolo(?:-(?:agent|claude|codex))?|(?:yolo-)?(?:agent|claude|codex)"
    r"(?:-(?:code|cli|session|worker|\d+))?)$",
    re.IGNORECASE,
)
SPINNER = re.compile(r"^[\u2800-\u28ff⠋⣾⣽⣻⢿⡿⣟⣯⣷|/\\\-]+\s*")
SAFE_KEY = re.compile(r"^[A-Za-z0-9_.-]+$")


def cache_root():
    base = os.environ.get("XDG_CACHE_HOME")
    if not base:
        base = str(Path.home() / ".cache")
    return Path(base) / "zellij-agent-herder" / "panes"


def identity_path(session, pane):
    if not SAFE_KEY.fullmatch(session) or not SAFE_KEY.fullmatch(pane):
        raise ValueError("session and pane must be simple identifiers")
    return cache_root() / session / f"{pane}.json"


def read_identity(session, pane):
    try:
        value = json.loads(identity_path(session, pane).read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    required = {"emoji", "name", "short", "ancestors"}
    if not isinstance(value, dict) or not required <= value.keys():
        return None
    if (
        value["emoji"] not in EMOJIS
        or not all(isinstance(value[key], str) for key in ("name", "short"))
        or not isinstance(value["ancestors"], list)
    ):
        return None
    if "label" not in value:
        value["label"] = value["name"]
        atomic_write(identity_path(session, pane), value)
    return value


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def slug(value):
    value = value.split(" · ", 1)[0].strip()
    value = SPINNER.sub("", value).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value


def useful_native_name(native_name, cwd=None, repo_name=None):
    candidate = slug(native_name or "")
    rejected = {slug(repo_name or "")}
    if cwd:
        rejected.add(slug(Path(cwd).name))
    if not candidate or candidate in rejected or GENERIC.fullmatch(candidate):
        return None
    return candidate


def display_name(display_label, native_name, cwd, repo_name, identity_name):
    candidate = slug(display_label or native_name or "")
    if candidate and not GENERIC.fullmatch(candidate):
        return candidate
    for fallback_label in (repo_name, Path(cwd).name if cwd else None):
        candidate = slug(fallback_label or "")
        if candidate:
            return candidate
    return identity_name


def initials(name):
    return "-".join(part[0] for part in name.split("-") if part)


def pane_id(value):
    raw = value.get("id")
    if isinstance(raw, int):
        return f"{'plugin' if value.get('is_plugin') else 'terminal'}_{raw}"
    raw = str(raw)
    if raw.startswith(("terminal_", "plugin_")):
        return raw
    return f"{'plugin' if value.get('is_plugin') else 'terminal'}_{raw}"


def open_pane_emojis(session, excluded_pane):
    try:
        result = subprocess.run(
            ["zellij", "--session", session, "action", "list-panes", "-j"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        value = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return set()
    if isinstance(value, dict):
        panes = []
        for entry in value.values():
            panes.extend(entry if isinstance(entry, list) else [entry])
    else:
        panes = value
    used = set()
    for open_pane in panes:
        if not isinstance(open_pane, dict) or pane_id(open_pane) == excluded_pane:
            continue
        title = str(open_pane.get("title", ""))
        identity = read_identity(session, pane_id(open_pane))
        if identity:
            used.add(identity["emoji"])
        elif not title.endswith("🔍"):
            used.update(emoji for emoji in EMOJIS if emoji in title)
    return used


def fallback(session, pane, used_emojis=None):
    digest = hashlib.sha256(f"{session}\0{pane}".encode()).digest()
    adjective = ADJECTIVES[int.from_bytes(digest[0:2], "big") % len(ADJECTIVES)]
    noun = NOUNS[int.from_bytes(digest[2:4], "big") % len(NOUNS)]
    start = int.from_bytes(digest[4:6], "big") % len(EMOJIS)
    used_emojis = set(used_emojis or ())
    emoji = next(
        (
            EMOJIS[(start + offset) % len(EMOJIS)]
            for offset in range(len(EMOJIS))
            if EMOJIS[(start + offset) % len(EMOJIS)] not in used_emojis
        ),
        EMOJIS[start],
    )
    return emoji, f"{adjective}-{noun}"


def summary(identity):
    return {key: identity[key] for key in ("emoji", "name", "short")}


def assign(
    session, pane, native_name=None, display_label=None, cwd=None, repo_name=None,
    ancestors=None,
):
    used_emojis = open_pane_emojis(session, pane)
    existing = read_identity(session, pane)
    if existing:
        if existing["emoji"] in used_emojis:
            existing = dict(existing)
            existing["emoji"] = fallback(
                session, pane, used_emojis,
            )[0]
            atomic_write(identity_path(session, pane), existing)
        return existing
    name = useful_native_name(native_name, cwd, repo_name)
    emoji, fallback_name = fallback(session, pane, used_emojis)
    name = name or fallback_name
    identity = {
        "emoji": emoji,
        "name": name,
        "short": initials(name),
        "ancestors": list(ancestors or []),
        "label": display_name(display_label, native_name, cwd, repo_name, name),
    }
    atomic_write(identity_path(session, pane), identity)
    return identity


def assign_child(session, pane, parent, **values):
    parent_identity = read_identity(session, parent)
    if not parent_identity:
        raise ValueError(f"parent identity not found: {session}/{parent}")
    ancestors = list(parent_identity["ancestors"]) + [summary(parent_identity)]
    return assign(session, pane, ancestors=ancestors, **values)


def render(identity, status=None):
    parts = [f"{ancestor['emoji']} {ancestor['short']}" for ancestor in identity["ancestors"]]
    leaf = f"{identity['emoji']} {identity['name']}"
    parts.append(leaf if parts else f"{identity['label']} ({leaf})")
    title = " > ".join(parts)
    return title if status is None else f"{title} · {status}"


def parser():
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)
    for command in ("assign", "child"):
        sub = commands.add_parser(command)
        sub.add_argument("--session", required=True)
        sub.add_argument("--pane", required=True)
        if command == "child":
            sub.add_argument("--parent", required=True)
        sub.add_argument("--native-name")
        sub.add_argument("--display-label")
        sub.add_argument("--cwd")
        sub.add_argument("--repo-name")
    render_command = commands.add_parser("render")
    render_command.add_argument("--session", required=True)
    render_command.add_argument("--pane", required=True)
    render_command.add_argument("--status", choices=("working", "idle", "blocked"))
    remove = commands.add_parser("remove")
    remove.add_argument("--session", required=True)
    remove.add_argument("--pane", required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "remove":
        try:
            identity_path(args.session, args.pane).unlink()
        except FileNotFoundError:
            pass
        return 0
    if args.command == "render":
        identity = read_identity(args.session, args.pane)
        if not identity:
            raise SystemExit(f"identity not found: {args.session}/{args.pane}")
        print(render(identity, args.status))
        return 0
    values = {
        "native_name": args.native_name,
        "display_label": args.display_label,
        "cwd": args.cwd,
        "repo_name": args.repo_name,
    }
    identity = (
        assign_child(args.session, args.pane, args.parent, **values)
        if args.command == "child"
        else assign(args.session, args.pane, **values)
    )
    print(json.dumps(identity, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
