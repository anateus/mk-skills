#!/usr/bin/env python3
"""Stable identity and persistent state primitives for Hunk work streams."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from typing import Any


STATE_FIELDS = (
    "version", "key", "generation", "session", "parent_pane", "pane_id", "tab_id",
    "root", "common_dir", "base", "kind", "label", "signature",
    "dismissed_signature", "complete", "dedicated_tab",
)
# Bound managed review processes across all sessions sharing this cache.
DEFAULT_MAX_ACTIVE_STREAMS = 4
MAX_ACTIVE_STREAMS_ENV = "ZAH_MAX_ACTIVE_STREAMS"


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


def streams_dir() -> str:
    return os.path.join(canonical_path(cache_root()), "zellij-agent-herder", "streams")


@contextlib.contextmanager
def spawn_lock() -> Iterator[None]:
    """Serialize the cap check and pane creation across concurrent hooks."""
    directory = streams_dir()
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, ".spawn.lock"), "a+b") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield


def stream_state_paths() -> list[str]:
    try:
        names = os.listdir(streams_dir())
    except FileNotFoundError:
        return []
    return [
        os.path.join(streams_dir(), name)
        for name in names
        if name.endswith(".json")
    ]


def read_stream_state(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def zellij_session_status() -> tuple[set[str], set[str]] | None:
    """Return active and exited sessions, or None when the CLI cannot answer."""
    try:
        result = subprocess.run(
            ["zellij", "list-sessions", "--no-formatting"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    active: set[str] = set()
    exited: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        name = line.split(" [", 1)[0]
        if "(EXITED" in line:
            exited.add(name)
        else:
            active.add(name)
    return active, exited


def remove_stream_state(path: str) -> None:
    """Remove a stale state and an idle companion lock, without disturbing a writer."""
    lock_path = os.path.splitext(path)[0] + ".lock"
    try:
        with open(lock_path, "a+b") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            try:
                os.unlink(lock_path)
            except FileNotFoundError:
                pass
    except OSError:
        return


def remove_orphan_locks(exclude_key: str | None = None) -> None:
    try:
        names = os.listdir(streams_dir())
    except FileNotFoundError:
        return
    for name in names:
        if not name.endswith(".lock"):
            continue
        if name == ".spawn.lock":
            continue
        key = name[:-5]
        if key == exclude_key or os.path.exists(os.path.join(streams_dir(), f"{key}.json")):
            continue
        path = os.path.join(streams_dir(), name)
        try:
            with open(path, "a+b") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                os.unlink(path)
        except (BlockingIOError, FileNotFoundError, OSError):
            continue


def prune_stream_states(session: str, exclude_key: str | None = None) -> None:
    """Drop state for panes that no longer exist, including dead sessions."""
    paths = stream_state_paths()
    remove_orphan_locks(exclude_key)
    if not paths:
        return
    records: list[tuple[str, str, str]] = []
    for path in paths:
        key = os.path.basename(path)[:-5]
        if key == exclude_key:
            continue
        state = read_stream_state(path)
        if not state:
            continue
        state_session = state.get("session")
        pane = state.get("pane_id")
        if (
            not state.get("complete")
            and isinstance(state_session, str)
            and isinstance(pane, str)
            and pane
        ):
            records.append((path, state_session, pane))

    if not records:
        return
    status = zellij_session_status()
    # Liveness is a socket fact, but `list-sessions` marks the ambient
    # ZELLIJ_SESSION_NAME as current even when no server exists for it. Union the
    # socket inventory in so a reachable stream is never pruned.
    active: set[str] | None = None
    if status is not None:
        active = status[0] | {name for directory in socket_dirs() for name in live_sessions(directory)}
    panes_by_session: dict[str, set[str] | None] = {}
    for path, state_session, pane in records:
        stale = False
        if active is not None:
            if state_session not in active:
                stale = True
            elif state_session not in panes_by_session:
                try:
                    panes_by_session[state_session] = set(pane_id(item) for item in panes(state_session, quiet=True))
                except (OSError, subprocess.SubprocessError, ValueError, TypeError, json.JSONDecodeError):
                    panes_by_session[state_session] = None
            if panes_by_session.get(state_session) is not None:
                stale = pane not in panes_by_session[state_session]
        elif state_session == session:
            if state_session not in panes_by_session:
                try:
                    panes_by_session[state_session] = set(pane_id(item) for item in panes(state_session, quiet=True))
                except (OSError, subprocess.SubprocessError, ValueError, TypeError, json.JSONDecodeError):
                    panes_by_session[state_session] = None
            if panes_by_session.get(state_session) is not None:
                stale = pane not in panes_by_session[state_session]
        if stale and active is not None and state_session not in active:
            remove_stream_state(path)
    remove_orphan_locks(exclude_key)


def max_active_streams() -> int:
    value = os.environ.get(MAX_ACTIVE_STREAMS_ENV)
    if value is None:
        return DEFAULT_MAX_ACTIVE_STREAMS
    try:
        parsed = int(value)
    except ValueError:
        return DEFAULT_MAX_ACTIVE_STREAMS
    return parsed if parsed > 0 else DEFAULT_MAX_ACTIVE_STREAMS


def active_stream_count(
    session: str, exclude_key: str | None = None,
    exclude_pane: tuple[str, str] | None = None,
) -> int | None:
    """Count all managed panes and locked supervisor leases, failing closed.

    Completed streams still consume resources until their pane actually closes.
    An unknown inventory is not evidence that a process has stopped.
    """
    identities: set[tuple[str, str]] = set()
    sessions = {session}
    for path in stream_state_paths():
        if os.path.basename(path)[:-5] == exclude_key:
            continue
        state = read_stream_state(path)
        if state is None:
            return None
        if state.get("pane_id"):
            if not isinstance(state.get("session"), str):
                return None
            identities.add((state["session"], str(state["pane_id"])))
            sessions.add(state["session"])
    status = zellij_session_status()
    live: set[tuple[str, str]] = set()
    for name in sessions:
        if status is not None and name != session and name not in status[0]:
            continue
        try:
            inventory = {pane_id(item) for item in panes(name, quiet=True)}
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            return None
        live.update(identity for identity in identities if identity[0] == name and identity[1] in inventory)
    # A lease outlives stale/missing stream state and remains counted until the
    # supervisor has reaped its child. Unlocked files are harmless tombstones.
    directory = os.path.join(streams_dir(), "processes")
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        names = []
    for name in names:
        if not name.endswith(".lease"):
            continue
        try:
            with open(os.path.join(directory, name), "r+") as lease:
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    record = json.load(lease)
                    live.add((record["session"], record["pane_id"]))
        except (OSError, ValueError, KeyError, TypeError):
            return None
    if exclude_pane is not None:
        live.discard(exclude_pane)
    return len(live)


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


def review_tab_title(request: dict[str, Any]) -> str:
    label = str(request.get("label") or os.path.basename(request["root"]))
    cleaned = " ".join(label.split()) or "review"
    return f"🔍 {cleaned}"[:48]


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


def _zellij_raw(
    session: str, args: list[str], socket_dir: str | None = None, quiet: bool = False,
) -> str:
    env = dict(os.environ)
    if socket_dir:
        env["ZELLIJ_SOCKET_DIR"] = socket_dir
    result = subprocess.run(
        ["zellij", "--session", session, "action", *args],
        check=True, stdout=subprocess.PIPE, text=True, timeout=5, env=env,
        # Best-effort probes must not leak Zellij's diagnostics into the caller's
        # output; a real failure still raises and is handled by the caller.
        stderr=subprocess.PIPE if quiet else None,
    )
    return result.stdout.strip()


def socket_dirs() -> list[str]:
    """Candidate Zellij socket directories, most explicit first.

    Zellij resolves its socket directory from ZELLIJ_SOCKET_DIR when set, else
    $TMPDIR/zellij-$UID (holding contract_version_1/ since Zellij 0.44). A harness
    that overrides TMPDIR for its subprocesses breaks the plain lookup, so probe the
    platform locations too. An explicit ZELLIJ_SOCKET_DIR is authoritative.
    """
    explicit = os.environ.get("ZELLIJ_SOCKET_DIR")
    if explicit:
        return [os.path.normpath(explicit)]
    uid = os.getuid()
    candidates = []
    tmp = os.environ.get("TMPDIR")
    if tmp:
        candidates.append(os.path.join(tmp, f"zellij-{uid}"))
    try:
        probe = subprocess.run(
            ["getconf", "DARWIN_USER_TEMP_DIR"],
            check=True, stdout=subprocess.PIPE, text=True, timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        probe = ""
    if probe:
        candidates.append(os.path.join(probe, f"zellij-{uid}"))
    candidates.append(f"/tmp/zellij-{uid}")
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        candidate = os.path.normpath(candidate)
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def live_sessions(socket_dir: str) -> list[str]:
    """Names of live sessions whose socket exists in this directory."""
    for base in (os.path.join(socket_dir, "contract_version_1"), socket_dir):
        names = []
        try:
            entries = os.listdir(base)
        except OSError:
            continue
        for name in sorted(entries):
            try:
                mode = os.stat(os.path.join(base, name)).st_mode
            except OSError:
                continue
            if stat.S_ISSOCK(mode):
                names.append(name)
        if names:
            return names
    return []


def session_pane_ids(socket_dir: str, session: str) -> set[str]:
    try:
        value = json.loads(_zellij_raw(session, ["list-panes", "-j"], socket_dir, quiet=True))
    except (OSError, ValueError, subprocess.SubprocessError):
        return set()
    items: list[Any] = []
    if isinstance(value, dict):
        for entry in value.values():
            items.extend(entry if isinstance(entry, list) else [entry])
    elif isinstance(value, list):
        items = value
    ids: set[str] = set()
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), (str, int)):
            raw = item["id"]
            ids.add(
                f"{'plugin' if item.get('is_plugin') else 'terminal'}_{raw}"
                if isinstance(raw, int) else str(raw)
            )
    return ids


def resolve_target(session: str, pane: str | None, explicit: bool = False) -> tuple[str | None, str]:
    """Resolve (socket_dir, session) for the requested Zellij session.

    Prefers the requested session wherever a live socket exists. When that name is
    stale (a long-lived host process can outlive its session) and this process is
    inside Zellij, adopts the single live session that owns ZELLIJ_PANE_ID, else the
    sole live session. An explicitly requested session is never substituted, and
    neither is one requested from outside Zellij. Never guesses between several
    candidates; falls back to the requested name with no socket dir.
    """
    directories = socket_dirs()
    for directory in directories:
        if session and session in live_sessions(directory):
            return directory, session
    # Recovery only makes sense inside a pane, where ZELLIJ_PANE_ID is meaningful,
    # and only for an environment-derived name the caller did not choose.
    if explicit or "ZELLIJ" not in os.environ:
        return None, session
    live = [(directory, name) for directory in directories for name in live_sessions(directory)]
    if not live:
        return None, session
    if len(live) == 1:
        return _adopt(session, live[0])
    if pane:
        wanted = normalize_parent(pane)
        matches = [entry for entry in live if wanted in session_pane_ids(*entry)]
        if len(matches) == 1:
            return _adopt(session, matches[0])
    return None, session


def _adopt(session: str, target: tuple[str, str]) -> tuple[str, str]:
    directory, name = target
    if session and session != name:
        sys.stderr.write(
            f"hunk-stream: session {session!r} is not live; using {name!r} in {directory}\n"
        )
    return directory, name


_TARGET_CACHE: dict[str, tuple[str | None, str]] = {}


def zellij_target(session: str) -> tuple[str | None, str]:
    """Return the cached (socket_dir, resolved_session) for a requested session.

    Honors ZAH_ZELLIJ_EXPLICIT_SESSION, which zj.sh exports when the caller chose
    the session deliberately; the controller must then apply the same
    no-substitution rule to its own zellij calls or it would place a pane in a
    different session than the state it records.
    """
    cached = _TARGET_CACHE.get(session)
    if cached is None:
        # "0" is a truthful string, so compare explicitly rather than truthy-test.
        explicit = os.environ.get("ZAH_ZELLIJ_EXPLICIT_SESSION") == "1"
        cached = resolve_target(session, os.environ.get("ZELLIJ_PANE_ID"), explicit)
        _TARGET_CACHE[session] = cached
    return cached


def zellij(session: str, args: list[str], quiet: bool = False) -> str:
    socket_dir, resolved = zellij_target(session)
    return _zellij_raw(resolved, args, socket_dir, quiet)


def panes(session: str, quiet: bool = False) -> list[dict[str, Any]]:
    value = json.loads(zellij(session, ["list-panes", "-j", "-g", "-s", "-t"], quiet))
    if isinstance(value, dict):
        items: list[Any] = []
        for entry in value.values():
            items.extend(entry if isinstance(entry, list) else [entry])
    else:
        items = value
    if not isinstance(items, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), (str, int))
        for item in items
    ):
        raise ValueError("invalid Zellij pane inventory")
    return items


def pane_id(pane: dict[str, Any]) -> str:
    value = pane.get("id")
    if isinstance(value, int):
        return f"{'plugin' if pane.get('is_plugin') else 'terminal'}_{value}"
    return str(value)


def pane_exists(session: str, wanted: str | None) -> bool:
    return bool(wanted) and any(pane_id(item) == wanted for item in panes(session))


def pane_map(session: str) -> dict[str, dict[str, Any]]:
    return {pane_id(item): item for item in panes(session)}


def request_matches(state: dict[str, Any], request: dict[str, Any]) -> bool:
    fields = ("session", "parent_pane", "root", "common_dir", "base", "kind", "label")
    return all(state.get(field) == request[field] for field in fields)


def grouped_tab_placement(
    items: list[dict[str, Any]], origin: str, kind: str,
) -> dict[str, Any] | None:
    """Return the newest matching group and whether it can accept another pane."""
    parent = next((item for item in items if pane_id(item) == origin), None)
    if parent is None:
        return None
    tab_name = parent.get("tab_name")
    if not isinstance(tab_name, str) or not tab_name:
        return None
    origin_match = re.fullmatch(r"(.+) - (?:(?:󱙺 )?Peers|(?: )?Reviews) #?[0-9]+", tab_name)
    base = origin_match.group(1) if origin_match else tab_name
    icon = {"Peers": "󱙺", "Reviews": ""}[kind]
    pattern = re.compile(r"^" + re.escape(base) + rf" - (?:{icon} )?{re.escape(kind)} #?([0-9]+)$")
    groups: dict[int, dict[str, Any]] = {}
    for item in items:
        match = pattern.fullmatch(str(item.get("tab_name") or ""))
        if match:
            number = int(match.group(1))
            groups.setdefault(number, {"tab_id": item.get("tab_id")})
    if not groups:
        return {"base": base, "number": 1, "tab_id": None, "reuse": False}
    number = max(groups)
    tab_id = groups[number]["tab_id"]
    visible = sum(
        str(item.get("tab_id")) == str(tab_id)
        and not item.get("is_plugin", False)
        and not item.get("is_suppressed", False)
        and not item.get("is_floating", False)
        for item in items
    )
    reuse = visible < 4 and tab_id is not None
    return {
        "base": base,
        "number": number if reuse else number + 1,
        "tab_id": tab_id if reuse else None,
        "reuse": reuse,
    }


def watch_command(request: dict[str, Any]) -> list[str]:
    # Carry lifecycle settings through Zellij server environments, not origin pane IDs.
    settings = [f"XDG_CACHE_HOME={canonical_path(cache_root())}"]
    names = (
        "PATH", MAX_ACTIVE_STREAMS_ENV, "ZAH_HUNK_RSS_MIB",
        "ZAH_HUNK_SAMPLE_SECONDS", "ZAH_HUNK_PRESSURE_SAMPLES",
        "ZAH_HUNK_RESUME_GRACE_SECONDS", "ZAH_HUNK_RECYCLE",
        "ZAH_HUNK_MAX_AGE_SECONDS", "ZAH_HUNK_RESTART_DELAY_SECONDS",
        "ZAH_HUNK_MAX_RESTARTS", "ZAH_HUNK_STOP_GRACE_SECONDS",
    )
    settings.extend(f"{name}={os.environ.get(name, os.defpath if name == 'PATH' else '')}" for name in names)
    return [
        "env", *settings, sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hunk-watch.py"),
        "--session", request["session"], "--base", request["base"],
    ]


def spawn_hunk(request: dict[str, Any]) -> tuple[str, int]:
    session = request["session"]
    parent = normalize_parent(request["parent_pane"])
    initial_panes = panes(session)
    initial_ids = {pane_id(item) for item in initial_panes}
    placement = grouped_tab_placement(initial_panes, parent, "Reviews")
    use_existing = bool(placement and placement["reuse"])
    if use_existing:
        tab_id = placement["tab_id"]
        args = [
            "new-pane", "--no-focus", "--tab-id", str(tab_id), "--cwd", request["root"], "--",
            *watch_command(request),
        ]
        zellij(session, args)
        returned = str(tab_id)
    else:
        tab_id = None
        tab_name = (
            f"{placement['base']} -  Reviews #{placement['number']}"
            if placement else review_tab_title(request)
        )
        args = [
            "new-tab", "--no-focus", "--cwd", request["root"],
            "--name", tab_name, "--", *watch_command(request),
        ]
        output = zellij(session, args).splitlines()
        returned = output[-1] if output else ""
        try:
            tab_id = int(returned)
        except ValueError:
            tab_id = None

    matches: list[dict[str, Any]] = []
    for _ in range(20):
        new_panes = [
            item for item in panes(session)
            if pane_id(item) not in initial_ids and not item.get("is_plugin", False)
        ]
        if tab_id is not None:
            matches = [item for item in new_panes if str(item.get("tab_id")) == str(tab_id)]
        elif len(new_panes) == 1:
            # Keep the existing recovery path for a malformed new-tab response.
            matches = new_panes
            tab_id = new_panes[0].get("tab_id")
        if len(matches) == 1 and isinstance(tab_id, int):
            break
        if len(matches) > 1:
            raise RuntimeError(f"new review tab must contain exactly one pane: {returned!r}")
        time.sleep(0.25)
    if len(matches) != 1 or not isinstance(tab_id, int):
        raise RuntimeError(
            f"new review tab must contain exactly one pane: {returned!r} "
            "(Zellij only materialises new tabs and panes after a client attaches; "
            "check that a client is attached to this session)"
        )
    spawned = pane_id(matches[0])
    zellij(session, ["rename-pane", "-p", spawned, review_title(session, parent)])
    return spawned, tab_id


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
    prune_stream_states(session, exclude_key=key)
    with spawn_lock():
        state_path = os.path.join(streams_dir(), f"{key}.json")
        existing = read_stream_state(state_path)
        if existing is None and not os.path.exists(state_path):
            active = active_stream_count(session)
            if active is None or active >= max_active_streams():
                return ""
        elif (
            existing
            and not existing.get("pane_id")
            and not existing.get("generation")
        ):
            active = active_stream_count(session)
            if active is None or active >= max_active_streams():
                remove_stream_state(state_path)
                return ""
        with locked_state(cache_root(), key) as state:
            present = pane_exists(session, state.get("pane_id"))
            if (
                present
                and request_matches(state, request)
                and state.get("dedicated_tab") is True
            ):
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
            active = active_stream_count(session, exclude_key=key)
            if active is None or active >= max_active_streams():
                return ""
            generation = int(state.get("generation") or 0) + 1
            spawned, tab_id = spawn_hunk(request)
            state.clear()
            state.update(empty_state(key))
            state.update(request)
            state.update(
                generation=generation, pane_id=spawned, tab_id=tab_id,
                signature=signature, dismissed_signature=None, complete=False,
                dedicated_tab=True,
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
    commands.add_parser("edit")
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--session", default="")
    resolve.add_argument("--pane")
    resolve.add_argument("--explicit-session", action="store_true")
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
    elif args.command == "resolve":
        socket_dir, session = resolve_target(args.session, args.pane, args.explicit_session)
        print(f"socket_dir={socket_dir or ''}")
        print(f"session={session or ''}")
    else:
        try:
            payload = json.load(sys.stdin)
        except (ValueError, OSError):
            payload = {}
        if isinstance(payload, dict):
            print(edit_payload(payload))


if __name__ == "__main__":
    main()
