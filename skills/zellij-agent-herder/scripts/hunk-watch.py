#!/usr/bin/env python3
"""Own one Hunk child in one pane. Pause by default, recycle only by consent."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import termios
import time


def number(name: str, default: float, minimum: float = 0) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
        return value if math.isfinite(value) and value >= minimum else default
    except ValueError:
        return default


def load_stream():
    spec = importlib.util.spec_from_file_location("hunk_stream", Path(__file__).with_name("hunk-stream.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def lease(stream, session: str, pane: str):
    """Reserve before fork, release only after reap; lock FDs never reach Hunk."""
    directory = Path(stream.streams_dir()) / "processes"
    directory.mkdir(parents=True, exist_ok=True)
    handle = None
    with stream.spawn_lock():
        count = stream.active_stream_count(session, exclude_pane=(session, pane))
        if count is None or count >= stream.max_active_streams():
            raise RuntimeError("managed Hunk cap reached or pane inventory unavailable")
        # Per-pane locks reject duplicate supervisors; never truncate a held lease.
        key = hashlib.sha256(json.dumps([session, pane]).encode()).hexdigest()
        handle = (directory / f"{key}.lease").open("a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise RuntimeError("this pane already has a managed Hunk supervisor")
        handle.seek(0)
        handle.truncate()
        json.dump({"session": session, "pane_id": pane}, handle)
        handle.flush()
    try:
        yield
    finally:
        handle.close()


def rss_kib(pid: int) -> int | None:
    try:
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=3,
        )
        return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def pane_alive(stream, session: str, pane: str) -> bool | None:
    try:
        return any(stream.pane_id(item) == pane for item in stream.panes(session))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return None


def stop_child(child: subprocess.Popen, grace: float) -> None:
    if child.poll() is not None:
        return
    # A stopped process cannot handle TERM until it has been continued.
    child.send_signal(signal.SIGCONT)
    child.terminate()
    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def supervise(stream, session: str, pane: str, base: str) -> int:
    interval = number("ZAH_HUNK_SAMPLE_SECONDS", 15, 0.01)
    threshold = number("ZAH_HUNK_RSS_MIB", 512, 1) * 1024
    required = int(number("ZAH_HUNK_PRESSURE_SAMPLES", 3, 1))
    max_age = number("ZAH_HUNK_MAX_AGE_SECONDS", 0)
    grace = number("ZAH_HUNK_RESUME_GRACE_SECONDS", 300)
    restart_delay = number("ZAH_HUNK_RESTART_DELAY_SECONDS", 30, 0.01)
    max_restarts = int(number("ZAH_HUNK_MAX_RESTARTS", 3))
    stop_grace = number("ZAH_HUNK_STOP_GRACE_SECONDS", 3, 0.01)
    recycle = os.environ.get("ZAH_HUNK_RECYCLE") == "1"
    wake = threading.Event()
    stopping = False
    resume = False

    def on_stop(_signum, _frame):
        nonlocal stopping
        stopping = True
        wake.set()

    def on_resume(_signum, _frame):
        nonlocal resume
        resume = True
        wake.set()

    for signum in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, on_stop)
    signal.signal(signal.SIGUSR1, on_resume)
    child = None
    restarts = 0
    terminal = None
    try:
        terminal = termios.tcgetattr(sys.stdin.fileno())
    except (OSError, termios.error, ValueError):
        pass

    def restore_terminal():
        if terminal is not None:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, terminal)
            except (OSError, termios.error, ValueError):
                pass

    try:
        while not stopping:
            # Never fork into a closed or uninspectable pane, including recycling.
            if pane_alive(stream, session, pane) is not True:
                return 0
            child = subprocess.Popen(["hunk", "diff", base, "--watch"], close_fds=True)
            born = time.monotonic()
            eligible = born
            pressure = 0
            paused = False
            restart = False
            while not stopping:
                wake.wait(interval)
                wake.clear()
                if stopping:
                    break
                result = child.poll()
                if result is not None:
                    return result if result >= 0 else 128 - result
                alive = pane_alive(stream, session, pane)
                if alive is False:
                    return 0
                now = time.monotonic()
                if resume:
                    resume = False
                    if paused:
                        child.send_signal(signal.SIGCONT)
                        paused = False
                        pressure = 0
                        eligible = now + grace
                        # Explicit resume grants a new age interval too.
                        born = now
                        print("[hunk-watch] resumed owned child", file=sys.stderr, flush=True)
                if paused or now < eligible:
                    continue
                rss = rss_kib(child.pid)
                pressure = pressure + 1 if rss is not None and rss >= threshold else 0
                aged = bool(max_age and now - born >= max_age)
                if pressure < required and not aged:
                    continue
                reason = "maximum age" if aged else "sustained RSS pressure"
                if recycle and restarts < max_restarts and alive is True:
                    print(f"[hunk-watch] recycling after {reason}; in-memory review state is lost", file=sys.stderr, flush=True)
                    stop_child(child, stop_grace)
                    child = None
                    restore_terminal()
                    restarts += 1
                    restart = True
                    # Bounded restarts and interruptible backoff prevent storms.
                    wake.wait(restart_delay)
                    wake.clear()
                    break
                child.send_signal(signal.SIGSTOP)
                paused = True
                print(
                    f"[hunk-watch] paused child {child.pid} after {reason}; review state retained. "
                    f"Resume with: kill -USR1 {os.getpid()} (grace {grace:g}s). "
                    "Close this pane to end it. Recycling is lossy and opt-in.",
                    file=sys.stderr, flush=True,
                )
            if not restart:
                break
        return 0
    finally:
        if child is not None:
            stop_child(child, stop_grace)
        restore_terminal()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    pane = os.environ.get("ZELLIJ_PANE_ID", "")
    if not pane:
        parser.error("ZELLIJ_PANE_ID is required; launch inside a managed review pane")
    stream = load_stream()
    pane = stream.normalize_parent(pane)
    try:
        with lease(stream, args.session, pane):
            return supervise(stream, args.session, pane, args.base)
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"[hunk-watch] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
