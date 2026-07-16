#!/bin/sh
# PostToolUse hook: on the agent's first file change in a worktree this turn,
# open `hunk diff --watch` in a plain tiled pane. Idempotent.
# Skips: outside zellij, subagents, non-git / clean trees, a live hunk session
# already open for the repo, or a pane already opened this turn for this root.
set -eu
input="$(cat 2>/dev/null || true)"
[ -n "${ZELLIJ_PANE_ID:-}" ] || exit 0
command -v git    >/dev/null 2>&1 || exit 0
command -v zellij >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
ZAH_INPUT="$input" python3 - <<'PY'
import hashlib, json, os, subprocess, sys
from shutil import which
try: h = json.loads(os.environ.get("ZAH_INPUT","") or "{}")
except Exception: sys.exit(0)
if h.get("agent_id"): sys.exit(0)                       # subagent — ignore
tin = h.get("tool_input") or {}
fp = tin.get("file_path")
start = os.path.dirname(fp) if fp and os.path.isdir(os.path.dirname(fp)) else (h.get("cwd") or os.getcwd())
def git(args, cwd):
    r = subprocess.run(["git","-C",cwd,*args], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return r.stdout if r.returncode == 0 else None
root = (git(["rev-parse","--show-toplevel"], start) or "").strip()
if not root: sys.exit(0)
if not (git(["status","--porcelain"], root) or "").strip(): sys.exit(0)   # clean tree
def hunk_bin():
    b = which("hunk")
    if b: return b
    for c in ("/opt/homebrew/bin/hunk","/usr/local/bin/hunk", os.path.expanduser("~/.local/bin/hunk")):
        if os.access(c, os.X_OK): return c
    return None
hb = hunk_bin()
# live hunk session already tracks this repo (its --watch stays fresh)
if hb and subprocess.run([hb,"session","get","--repo",root],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
    sys.exit(0)
# per-(root, prompt_id) dedup: at most one open attempt per turn per repo
prompt_id = str(h.get("prompt_id") or h.get("session_id") or "")
state_dir = os.path.expanduser("~/.cache/zellij-agent-herder")
os.makedirs(state_dir, exist_ok=True)
mark = os.path.join(state_dir, "turn-" + hashlib.sha1(root.encode()).hexdigest()[:16])
try:
    if open(mark).read().strip() == prompt_id: sys.exit(0)
except OSError: pass
with open(mark, "w") as f: f.write(prompt_id)         # record BEFORE opening
sess = os.environ.get("ZELLIJ_SESSION_NAME")
base = ["zellij"] + (["--session", sess] if sess else []) + ["action"]
cmd = ["hunk","diff","--watch"] if hb else ["bunx","hunkdiff","diff","--watch"]
name = "hunk:" + os.path.basename(root)
# Always a plain tiled new-pane — never --near-current-pane/-d. That flag silently
# no-ops with no connected client (headless), AND misbehaves even when a client IS
# attached if the issuing pane (this agent's) isn't the client's *focused* pane: it
# prints a terminal_N but the pane never actually appears (see pitfalls.md). Since
# this hook fires from a background agent the human likely isn't looking at, that
# mismatch is the common case, not the edge case — so it's never safe here. A
# passive watcher pane has no focus to steal, so plain placement costs nothing
# (zj_watch_worktree in zj.sh applies the same rule for the same reason).
try:
    subprocess.run(base + ["new-pane","--cwd",root,"-n",name,"--"] + cmd,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
except Exception: pass
PY
