# `zellij-agent-herder` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single skill, `zellij-agent-herder`, that gives an agent running inside zellij the multiplexer-control and peer-coding-agent capabilities of the herdr / herdr-peer-agents skills — plus a hook regime that (a) tracks agent lifecycle status and (b) auto-opens a live `hunk diff --watch` pane on the worktree the moment the agent starts changing files.

**Architecture:** Thin CLI wrappers over `zellij action` (verified against zellij 0.45.0). Panes are addressed by `(session_name, pane_id)`; `-p <pane_id>` targets any pane without stealing focus. The two capabilities zellij lacks natively — *wait-for-text* and *agent-status* — are filled by a shell helper lib (`zj.sh`) plus Claude Code lifecycle hooks. Progressive disclosure per superpowers:writing-skills: a lean `SKILL.md` (guard + concepts + core-command quick reference + pointers) with heavy material in `references/` loaded on demand.

**Tech Stack:** POSIX sh / bash + python3 (JSON parsing), the `zellij` binary (≥ 0.44 for `--block-until-exit*`; developed against 0.45.0), the `hunk` binary (0.17.0; `hunk diff --watch`, `hunk session get --repo`), Claude Code hooks (`~/.claude/settings.json`), and the vercel-labs `skills` CLI for distribution.

## Global Constraints

- Target binaries: `zellij` **0.45.0** (feature floor 0.44.0 for native `--block-until-exit*`), `hunk` **0.17.0**. State the zellij floor in `SKILL.md`.
- Single skill directory: `~/code/mk-skills/skills/zellij-agent-herder/`. This is a real git repo (`origin` = `github.com/anateus/mk-skills`); commit each task. Reference implementations to copy shape from: `~/.agents/skills/herdr/`, `~/.agents/skills/herdr-peer-agents/`, and the hunk-autodiff plugin at `~/.config/herdr/plugins/github/hunk.autodiff-0ea0904f4623/autodiff.py`.
- Distribution via the vercel-labs `skills` CLI: installable with `npx skills add anateus/mk-skills`. `SKILL.md` needs `name` + `description` frontmatter. Installs land in a dir we do not control (`~/.claude/skills/<name>/` global, `./.claude/skills/<name>/` project) — so **no SKILL.md, reference, or script may hardcode a `~/.agents/...` or `~/code/mk-skills/...` runtime path**. SKILL.md refers to `scripts/<file>` / `references/<file>` relative to the skill's base directory (the harness prints "Base directory for this skill: …" on load); scripts locate siblings via their own `$0`.
- Pane addressing is always `(session, pane_id)`; `pane_id` = `terminal_N` / `plugin_N` / bare int, monotonic per session, never reused within a session's life, never stable across restarts. `--name` sets the pane **title only** — NOT addressable; resolve name→id via `list-panes -j`.
- **CONFIRMED (Task 0, zellij 0.45.0):** `list-panes -j` is a **flat list** `[{...}]` (each pane carries its own `tab_id`/`tab_position`), NOT dict-keyed-by-tab. Pane `id` is a **bare int** (e.g. `1`); `is_plugin` is a separate bool. Exit fields are `exited` (bool) + `exit_status` (int|null); exited panes also show `is_held:true`. `ZELLIJ_PANE_ID` inside a pane is the **bare int** matching `id`. The `_zj_panes` normalizer (int→`terminal_N`) and dual dict/list handling already absorb this; `-p terminal_N` is accepted for a bare-int id. `hunk session get --repo <live>` exits **0**; nonexistent repo exits **1** (`--json` is NOT honored on the failure path — plain-text error to stderr).
- Every read/write action passes `-p <pane_id>` explicitly. Bare `dump-screen` (no `-p`) follows focus and returns **empty on headless/background sessions**. `dump-screen` on a nonexistent/closed id returns **exit 0 + empty** (silent) — verify the pane exists first.
- Default `dump-screen` is **viewport-only**; use `--full` for text that may have scrolled off. Use **plain** output (never `-a/--ansi`) for grep.
- **Spawning is adaptive via `zj_spawn` (CONFIRMED Task 0).** Relative/directional placement (`--near-current-pane`, `-d/--direction`) **SILENTLY NO-OPS in a headless/no-client session** — `new-pane` exits 0 and prints a `terminal_N` status string, but **no pane is created** (it needs a connected client for current-pane-relative layout). Every test runs headless (`attach -b`), so tests and any code that must run under test spawn through `zj_spawn`: when a client is attached it uses `--near-current-pane` (places beside the current pane, does **not** steal focus — the production path); when headless it drops `-d`/`--near-current-pane` and uses plain `new-pane` (zellij picks the biggest free space — works headless). Client detection: `list-clients | tail -n +2 | grep -c .` (0 == headless; `list-clients` has no `-j`). Never parse `new-pane`'s printed `terminal_N` as authoritative (it prints even on the no-op); recover the real id from `list-panes -j`. Plain `new-pane`/`zellij run`/`new-tab`/`focus-*`/`move-focus` steal an attached client's focus/view when used directly — go through `zj_spawn`.
- Enter is `zellij action write -p <id> 13`. Codex composers may need it twice.
- Portability: never `date +%s%3N` (fails on macOS/BSD). Use bash `$SECONDS`.
- Hooks: `hook_event_name` fields are **PascalCase**; PostToolUse matcher for edits is `"Edit|Write|MultiEdit|NotebookEdit"` (exact match, `|`-separated); `UserPromptSubmit`/`Stop`/`Notification` ignore the matcher. Hooks **inherit the parent env** (so `ZELLIJ_PANE_ID`/`ZELLIJ_SESSION_NAME` are available). A subagent invocation has an `agent_id` field — skip it (mirror herdr). `tool_input.file_path` is an **absolute** path. PostToolUse cannot block; exit 0 + no stdout = silent side-effect; register the hunk hook with `"async": true` so it never stalls a turn.

---

## File Structure

Single skill, vercel-labs flat layout:
```
~/code/mk-skills/
  README.md                                 # install instructions + skill index
  skills/zellij-agent-herder/
    SKILL.md                                # LEAN: guard, concepts, core quick-ref, pointers to references/
    scripts/
      zj.sh                                 # helper lib: session targeting, name→id, waits, status wait
      zellij-peer.sh                        # peer-agent lifecycle wrapper (sources zj.sh)
      zellij-agent-status.sh                # status hook: stamps "<base> · <status>" into pane title
      hunk-autodiff.sh                      # PostToolUse hook: open `hunk diff --watch` pane on first change
      install-hooks.sh                      # installs BOTH hook sets into ~/.claude + settings.json (idempotent)
    references/
      peer-agents.md                        # full peer-agent workflows (the bulk pulled out of SKILL.md)
      command-reference.md                  # complete herdr→zellij command mapping + flag detail
      pitfalls.md                           # sharp edges + troubleshooting
      hooks.md                              # the hook regime: status + hunk, install/uninstall, toggles

  installed at runtime by install-hooks.sh (NOT in the repo):
    ~/.claude/hooks/zellij-agent-status.sh
    ~/.claude/hooks/hunk-autodiff.sh
    ~/.claude/settings.json                 # UserPromptSubmit/Stop/Notification + PostToolUse entries
    ~/.cache/zellij-agent-herder/           # hunk per-turn/per-repo dedup state
```

Responsibilities:
- `zj.sh` — single source of truth for zellij I/O: `_zj`, `_zj_panes`, `zj_resolve_id`, `zj_pane_exists`, `zj_client_count`, `zj_spawn`, `zj_wait_output`, `zj_wait_exit`, `zj_wait_status`. Sourced by SKILL.md usage, `zellij-peer.sh`, and (indirectly) the docs. One copy — the single-skill merge removes the two-skill vendoring problem. (Standalone hook scripts can't source it — see the adaptive-spawn note; the hunk hook inlines its own client check.)
- `zellij-peer.sh` — peer-agent lifecycle only; sources `zj.sh` from its own dir.
- `zellij-agent-status.sh` — status→title hook (UserPromptSubmit/Stop/Notification).
- `hunk-autodiff.sh` — PostToolUse hook replicating the `hunk.autodiff` herdr plugin for zellij + Claude Code.
- `install-hooks.sh` — copies both hook scripts to `~/.claude/hooks/` and idempotently registers all four events; the hunk hook is registered `async: true`.
- `references/*` — loaded only when the task needs them (keeps SKILL.md within superpowers:writing-skills token budget).

---

## Task 0: Ground-truth discovery (blocking prerequisite)

Establish, by running the binaries, the exact facts downstream code depends on. Do not guess.

**Files:** Create (scratch) `/tmp/zah/notes.md`.

**Interfaces:** Produces confirmed `list-panes -j` JSON shape, the `ZELLIJ_PANE_ID` value format, and confirmation of the `hunk diff --watch` + `hunk session get --repo` behavior.

- [ ] **Step 1: Pane-list JSON shape**

Run:
```bash
mkdir -p /tmp/zah
zellij attach -b zah-probe 2>/dev/null || true
zellij --session zah-probe action new-pane --near-current-pane -n probe1 -- bash -c 'echo READY; sleep 300'
zellij --session zah-probe action list-panes -j | tee /tmp/zah/list-panes.json | python3 -m json.tool | head -40
```
Expected: valid JSON. Record top-level shape (dict-keyed-by-tab `{"0":[{...}]}` vs flat list `[{...}]`) and the exact key names for pane **id** (string `"terminal_1"` or int), **title**, **exited**, **exit_status**.

- [ ] **Step 2: Title round-trip + Enter byte + exit reporting**

Run:
```bash
PID=$(zellij --session zah-probe action list-panes -j | python3 -c 'import sys,json;d=json.load(sys.stdin);ps=[p for v in (d.values() if isinstance(d,dict) else [d]) for p in (v if isinstance(v,list) else [v])];print([p for p in ps if str(p.get("title","")).startswith("probe1")][0]["id"])')
zellij --session zah-probe action rename-pane -p "$PID" "probe1 · working"
zellij --session zah-probe action list-panes -j | grep -o 'probe1 · working'
zellij --session zah-probe action new-pane --near-current-pane -n probe2 -- bash -c 'sleep 2; exit 5'
sleep 3; zellij --session zah-probe action list-panes -j | python3 -m json.tool | grep -iA2 exit
```
Expected: prints the id, `probe1 · working`, and `exited: true`/`exit_status: 5`. Record exact field names.

- [ ] **Step 3: hunk behavior**

Run (in any dirty git repo, e.g. a scratch one):
```bash
d=/tmp/zah/repo; rm -rf $d; mkdir -p $d; git -C $d init -q; echo a > $d/f; git -C $d add -A; git -C $d commit -qm init; echo b >> $d/f
zellij --session zah-probe action new-pane --near-current-pane -d right --cwd $d -n "hunk:repo" -- hunk diff --watch
sleep 2
hunk session get --repo $d --json 2>&1 | head; echo "exit=$?"
hunk session get --repo /tmp/zah/nonexistent 2>&1 | head; echo "exit=$?"
```
Expected: the pane runs the hunk TUI; `session get --repo $d` exits 0 (live session found); `session get` on a nonexistent repo exits nonzero. Record.

- [ ] **Step 4: In-pane env vars**

From a shell inside a zellij pane: `env | grep -E '^ZELLIJ' | sort`
Expected: `ZELLIJ=0`, `ZELLIJ_SESSION_NAME=<name>`, `ZELLIJ_PANE_ID=<value>`. Record the `ZELLIJ_PANE_ID` format (bare int vs `terminal_N`). Write findings to `/tmp/zah/notes.md`.

- [ ] **Step 5: Tear down**

Run: `zellij kill-session zah-probe 2>/dev/null || true`

---

## Task 1: Scaffold + `zj.sh` (session targeting + name resolution)

**Files:**
- Create: `~/code/mk-skills/skills/zellij-agent-herder/scripts/zj.sh`
- Test: `/tmp/zah/test_zj.sh`

**Interfaces:** Produces `_zj`, `_zj_panes`, `zj_resolve_id`, `zj_pane_exists`, `zj_client_count`, `zj_spawn`, and the `ZJ_SESSION` convention (defaults to `$ZELLIJ_SESSION_NAME`).

- [ ] **Step 1: Write the failing test**

Create `/tmp/zah/test_zj.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
source ~/code/mk-skills/skills/zellij-agent-herder/scripts/zj.sh
export ZJ_SESSION=zjtest
zellij kill-session zjtest 2>/dev/null || true
zellij attach -b zjtest
zj_spawn -n alpha -- bash -c 'sleep 300'
zj_spawn -n beta  -- bash -c 'sleep 300'
id=$(zj_resolve_id alpha); echo "resolved alpha -> $id"
[[ "$id" == terminal_* ]] || { echo "FAIL: id not terminal_*"; exit 1; }
zj_pane_exists "$id" || { echo "FAIL: pane_exists false for real id"; exit 1; }
zj_pane_exists terminal_9999 && { echo "FAIL: pane_exists true for fake id"; exit 1; } || true
zj_resolve_id nope && { echo "FAIL: resolved nonexistent name"; exit 1; } || echo "OK: nonexistent rejected"
echo "ALL OK"; zellij kill-session zjtest 2>/dev/null || true
```

- [ ] **Step 2: Run it — verify it fails** — Run `bash /tmp/zah/test_zj.sh`; Expected: FAIL (source: No such file).

- [ ] **Step 3: Write `zj.sh`**

Create `~/code/mk-skills/skills/zellij-agent-herder/scripts/zj.sh`:
```bash
#!/usr/bin/env bash
# Helper library for the zellij-agent-herder skill.
# Source this file, then call zj_* functions. Requires zellij >= 0.44 and python3.
# Target session: set ZJ_SESSION, else falls back to $ZELLIJ_SESSION_NAME.

ZJ_SESSION="${ZJ_SESSION:-${ZELLIJ_SESSION_NAME:-}}"

_zj() {  # run a zellij action against the target session
  if [ -n "${ZJ_SESSION:-}" ]; then zellij --session "$ZJ_SESSION" action "$@"
  else zellij action "$@"; fi
}

# Emit each pane object from `list-panes -j` as one JSON line, id normalized to terminal_N.
_zj_panes() {
  _zj list-panes -j 2>/dev/null | python3 -c '
import sys, json
try: data = json.load(sys.stdin)
except Exception: sys.exit(0)
panes = []
if isinstance(data, dict):
    for v in data.values(): panes.extend(v if isinstance(v, list) else [v])
elif isinstance(data, list): panes = data
for p in panes:
    if not isinstance(p, dict): continue
    pid = p.get("id")
    if isinstance(pid, int): p["id"] = "terminal_%d" % pid
    print(json.dumps(p))
'
}

# zj_resolve_id <name> -> prints terminal_N (exit 1 not found, 2 ambiguous).
# Matches full title OR base name before " · " (our status suffix).
zj_resolve_id() {
  _zj_panes | python3 -c '
import sys, json
name = sys.argv[1]; hits = []
for line in sys.stdin:
    p = json.loads(line); t = str(p.get("title",""))
    if t == name or t.split(" · ")[0] == name: hits.append(p["id"])
if len(hits) == 1: print(hits[0])
elif not hits: sys.exit(1)
else: sys.stderr.write("ambiguous: %d match %r\n" % (len(hits), name)); sys.exit(2)
' "$1"
}

# zj_pane_exists <pane_id> -> exit 0 if present, else 1.
zj_pane_exists() {
  _zj_panes | python3 -c '
import sys, json
pid = sys.argv[1]
for line in sys.stdin:
    if json.loads(line).get("id") == pid: sys.exit(0)
sys.exit(1)
' "$1"
}

# zj_client_count -> number of attached clients on the target session (0 == headless).
# `list-clients` has no -j; row 1 is a header, each further non-empty row is a client.
zj_client_count() { _zj list-clients 2>/dev/null | tail -n +2 | grep -c . ; }

# zj_spawn [new-pane args...] -> spawn a pane; echoes new-pane's status line (terminal_N).
# Attached: place near the current pane (does NOT steal focus) — the production path.
# Headless (tests/background): relative/directional placement silently no-ops with no
#   client, so strip -d/--direction/--near-current-pane and let zellij pick free space.
zj_spawn() {
  if [ "$(zj_client_count)" -gt 0 ]; then
    _zj new-pane --near-current-pane "$@"
  else
    local argv=("$@") a=() i=0
    while [ "$i" -lt "${#argv[@]}" ]; do
      case "${argv[$i]}" in
        -d|--direction)      i=$((i+2)); continue ;;
        --near-current-pane) i=$((i+1)); continue ;;
      esac
      a+=("${argv[$i]}"); i=$((i+1))
    done
    _zj new-pane "${a[@]}"
  fi
}
```

- [ ] **Step 4: Run it — verify it passes** — Expected: `resolved alpha -> terminal_N`, `OK: nonexistent rejected`, `ALL OK`.

- [ ] **Step 5: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/scripts/zj.sh
git -C ~/code/mk-skills commit -m "feat(zah): scaffold skill + zj.sh session targeting & name resolution"
```

---

## Task 2: `zj.sh` wait helpers (`zj_wait_output`, `zj_wait_exit`)

**Files:** Modify `~/code/mk-skills/skills/zellij-agent-herder/scripts/zj.sh` (append); Test `/tmp/zah/test_wait.sh`.

**Interfaces:** Consumes `_zj`/`_zj_panes`/`zj_pane_exists`. Produces `zj_wait_output <pane_id> <match> <timeout_s> [interval_s] [--regex]` (0 match / 1 timeout / 3 missing) and `zj_wait_exit <pane_id> <timeout_s> [interval_s]` (prints exit_status; 0 exited / 1 timeout / 3 missing).

- [ ] **Step 1: Write the failing test** — Create `/tmp/zah/test_wait.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
source ~/code/mk-skills/skills/zellij-agent-herder/scripts/zj.sh
export ZJ_SESSION=zjwait
zellij kill-session zjwait 2>/dev/null || true; zellij attach -b zjwait
zj_spawn -n w -- bash -c 'sleep 3; echo FRESH_MARKER; sleep 300'
id=$(zj_resolve_id w)
zj_wait_output "$id" "FRESH_MARKER" 15 && echo "OK matched" || { echo FAIL match; exit 1; }
zj_wait_output "$id" "NEVER_XYZ" 3 && { echo FAIL falsematch; exit 1; } || echo "OK timeout"
# --regex without an explicit interval must engage regex mode (regresses the positional-parse bug):
# "FRESH_[A-Z]+" matches FRESH_MARKER only as a regex; literal grep -F would false-timeout here.
zj_wait_output "$id" "FRESH_[A-Z]+" 10 --regex && echo "OK regex" || { echo FAIL regex; exit 1; }
# pane-missing must return 3:
rc=0; zj_wait_output terminal_9999 "x" 2 || rc=$?; [ "$rc" -eq 3 ] && echo "OK missing=3" || { echo "FAIL missing=$rc"; exit 1; }
zj_spawn -n e -- bash -c 'sleep 2; exit 5'
eid=$(zj_resolve_id e); st=$(zj_wait_exit "$eid" 15) && echo "OK exit=$st" || { echo FAIL exit; exit 1; }
[ "$st" = 5 ] || { echo "FAIL status $st"; exit 1; }
echo "ALL OK"; zellij kill-session zjwait 2>/dev/null || true
```

- [ ] **Step 2: Run — verify fail** (`zj_wait_output: command not found`).

- [ ] **Step 3: Append to `zj.sh`**:
```bash
# zj_wait_output <pane_id> <match> <timeout_s> [interval_s] [--regex]
# Polls dump-screen --full (plain) + grep. 0 match / 1 timeout / 3 pane missing.
# [interval_s] and [--regex] are each independently optional and may appear in
# any order after <timeout_s>; --regex selects grep -E (else grep -F literal).
zj_wait_output() {
  local pane_id="$1" match="$2" timeout_s="$3"; shift 3
  local interval_s="0.5" mode=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --regex) mode="--regex" ;;
      *)       interval_s="$1" ;;
    esac
    shift
  done
  zj_pane_exists "$pane_id" || { echo "zj_wait_output: pane $pane_id not found" >&2; return 3; }
  local start=$SECONDS dump; dump="$(mktemp "${TMPDIR:-/tmp}/zj.XXXXXX")"; trap 'rm -f "$dump"' RETURN
  while :; do
    _zj dump-screen -p "$pane_id" --full --path "$dump" >/dev/null 2>&1 || true
    if [ "$mode" = "--regex" ]; then grep -qE -- "$match" "$dump" 2>/dev/null && return 0
    else grep -qF -- "$match" "$dump" 2>/dev/null && return 0; fi
    (( SECONDS - start >= timeout_s )) && return 1
    sleep "$interval_s"
  done
}

# zj_wait_exit <pane_id> <timeout_s> [interval_s] -> prints exit_status. 0 exited / 1 timeout / 3 missing.
zj_wait_exit() {
  local pane_id="$1" timeout_s="$2" interval_s="${3:-0.5}"
  zj_pane_exists "$pane_id" || { echo "zj_wait_exit: pane $pane_id not found" >&2; return 3; }
  local start=$SECONDS st
  while :; do
    st="$(_zj_panes | python3 -c '
import sys, json
pid = sys.argv[1]
for line in sys.stdin:
    p = json.loads(line)
    if p.get("id") == pid and p.get("exited"): print(p.get("exit_status","")); sys.exit(0)
sys.exit(1)
' "$pane_id")" && { echo "$st"; return 0; }
    (( SECONDS - start >= timeout_s )) && return 1
    sleep "$interval_s"
  done
}
```

- [ ] **Step 4: Run — verify pass** — `OK matched`, `OK timeout`, `OK exit=5`, `ALL OK`.

- [ ] **Step 5: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/scripts/zj.sh
git -C ~/code/mk-skills commit -m "feat(zah): add zj_wait_output and zj_wait_exit"
```

---

## Task 3: Status hook + `zj_wait_status`

**Files:**
- Create: `.../scripts/zellij-agent-status.sh`
- Modify: `.../scripts/zj.sh` (append `zj_wait_status`)
- Test: `/tmp/zah/test_status.sh`

**Interfaces:** The hook maps `hook_event_name` → status (`UserPromptSubmit`→`working`, `Notification`→`blocked`, `Stop`→`idle`) and rewrites the current pane's title to `"<base> · <status>"`; no-op outside zellij / for subagents / for `SubagentStop`. `zj_wait_status <pane_id> <status> <timeout_s> [interval_s]` → 0 when the title's status token equals `<status>`, 1 timeout, 3 missing.

- [ ] **Step 1: Write the failing test** — Create `/tmp/zah/test_status.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
HOOK=~/code/mk-skills/skills/zellij-agent-herder/scripts/zellij-agent-status.sh
zellij kill-session zjhook 2>/dev/null || true; zellij attach -b zjhook
zellij --session zjhook action new-pane -n reviewer -- bash -c 'sleep 300'   # plain: headless has no client, so no -d/--near-current-pane
PID=$(zellij --session zjhook action list-panes -j | python3 -c 'import sys,json;d=json.load(sys.stdin);ps=[p for v in (d.values() if isinstance(d,dict) else [d]) for p in (v if isinstance(v,list) else [v])];print([p for p in ps if str(p.get("title","")).startswith("reviewer")][0]["id"])')
run(){ echo "$1" | env ZELLIJ_PANE_ID="$PID" ZELLIJ_SESSION_NAME=zjhook bash "$HOOK"; }
run '{"hook_event_name":"UserPromptSubmit","session_id":"s1"}'
zellij --session zjhook action list-panes -j | grep -o 'reviewer · working' || { echo FAIL working; exit 1; }
run '{"hook_event_name":"Stop","session_id":"s1"}'
zellij --session zjhook action list-panes -j | grep -o 'reviewer · idle' || { echo FAIL idle; exit 1; }
run '{"hook_event_name":"UserPromptSubmit","agent_id":"sub-1"}'
zellij --session zjhook action list-panes -j | grep -o 'reviewer · working' && { echo FAIL subagent; exit 1; } || true
echo "ALL OK"; zellij kill-session zjhook 2>/dev/null || true
```
(`run(){...}` is a bash function; if the executor's shell dislikes the name, rename to `run_hook`.)

- [ ] **Step 2: Run — verify fail** (hook file missing).

- [ ] **Step 3: Write the hook** — Create `.../scripts/zellij-agent-status.sh`:
```sh
#!/bin/sh
# Installed into ~/.claude/hooks/ by install-hooks.sh.
# Stamps agent status into the current zellij pane's title: "<base> · <status>".
set -eu
input="$(cat 2>/dev/null || true)"
[ -n "${ZELLIJ_PANE_ID:-}" ] || exit 0
command -v zellij  >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
ZAH_INPUT="$input" python3 - <<'PY'
import json, os, subprocess, sys
try: h = json.loads(os.environ.get("ZAH_INPUT","") or "{}")
except Exception: h = {}
if h.get("agent_id"): sys.exit(0)                 # subagent — ignore
evt = str(h.get("hook_event_name") or "")
if evt == "SubagentStop": sys.exit(0)             # never revive idle
status = {"UserPromptSubmit":"working","Notification":"blocked","Stop":"idle"}.get(evt)
if not status: sys.exit(0)
pane = os.environ.get("ZELLIJ_PANE_ID"); sess = os.environ.get("ZELLIJ_SESSION_NAME")
if not pane: sys.exit(0)
pane_arg = pane if pane.startswith(("terminal_","plugin_")) else "terminal_%s" % pane
base_cmd = ["zellij"] + (["--session", sess] if sess else []) + ["action"]
title = ""
try:
    out = subprocess.run(base_cmd+["list-panes","-j"], capture_output=True, text=True, timeout=2).stdout
    data = json.loads(out); panes = []
    if isinstance(data, dict):
        for v in data.values(): panes.extend(v if isinstance(v,list) else [v])
    elif isinstance(data, list): panes = data
    for p in panes:
        pid = p.get("id"); pid = pid if isinstance(pid,str) else "terminal_%d" % pid
        if pid == pane_arg: title = str(p.get("title","")); break
except Exception: title = ""
base = title.split(" · ")[0] if title else "agent"
try: subprocess.run(base_cmd+["rename-pane","-p",pane_arg,"%s · %s" % (base, status)], timeout=2)
except Exception: pass
PY
```

- [ ] **Step 4: Append `zj_wait_status` to `zj.sh`**:
```bash
# zj_wait_status <pane_id> <status> <timeout_s> [interval_s]  (status: working|idle|blocked)
zj_wait_status() {
  local pane_id="$1" want="$2" timeout_s="$3" interval_s="${4:-0.5}"
  zj_pane_exists "$pane_id" || { echo "zj_wait_status: pane $pane_id not found" >&2; return 3; }
  local start=$SECONDS cur
  while :; do
    cur="$(_zj_panes | python3 -c '
import sys, json
pid = sys.argv[1]
for line in sys.stdin:
    p = json.loads(line)
    if p.get("id") == pid:
        t = str(p.get("title","")); print(t.split(" · ",1)[1] if " · " in t else ""); break
' "$pane_id")"
    [ "$cur" = "$want" ] && return 0
    (( SECONDS - start >= timeout_s )) && return 1
    sleep "$interval_s"
  done
}
```

- [ ] **Step 5: Run — verify pass** — `ALL OK` (working, idle, subagent no-op).

- [ ] **Step 6: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/scripts/zellij-agent-status.sh skills/zellij-agent-herder/scripts/zj.sh
git -C ~/code/mk-skills commit -m "feat(zah): status hook (title stamping) + zj_wait_status"
```

---

## Task 4: `hunk-autodiff.sh` — open a live diff pane on first change

Replicates the `hunk.autodiff` herdr plugin (`~/.config/herdr/plugins/github/hunk.autodiff-0ea0904f4623/autodiff.py`) for zellij + Claude Code. Fires on `PostToolUse` for edit tools; opens `hunk diff --watch` beside the agent pane, once per turn, if not already showing.

**Files:**
- Create: `.../scripts/hunk-autodiff.sh`
- Test: `/tmp/zah/test_hunk.sh`

**Interfaces:** Reads PostToolUse JSON on stdin; derives the worktree root from `tool_input.file_path`; opens the diff pane subject to guards. Idempotency keys: live hunk session probe + per-`(root, prompt_id)` dedup file under `~/.cache/zellij-agent-herder/`.

- [ ] **Step 1: Write the failing test** — Create `/tmp/zah/test_hunk.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
HOOK=~/code/mk-skills/skills/zellij-agent-herder/scripts/hunk-autodiff.sh
# HERMETIC: `hunk diff --watch` runs under a local daemon and its session OUTLIVES the
# zellij pane (killing the session does NOT reap the watcher). So (1) use a unique per-run
# scratch root — the hook's idempotency probe is keyed on the absolute repo path, and a
# stale live session at a fixed path would make it correctly skip and break a re-run; and
# (2) reap this run's watchers in an EXIT trap via lsof cwd-match. Basenames stay
# hrepo/clean/subrepo so the pane-title greps (`hunk:<basename>`) are unchanged.
RUNTAG="hunkrun$$"; R="/tmp/zah/$RUNTAG"
cleanup() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -a -c hunk -d cwd -Fpn 2>/dev/null \
      | awk '/^p/{p=substr($0,2)} /^n/{if (index($0,"'"$RUNTAG"'")>0) print p}' \
      | sort -u | while read -r pid; do kill "$pid" 2>/dev/null || true; done
  fi
  zellij kill-session zjhunk 2>/dev/null || true
  rm -rf "$R"
}
trap cleanup EXIT
mkdir -p "$R"
# scratch dirty repo
d="$R/hrepo"; mkdir -p "$d"; git -C "$d" init -q
echo a > "$d/f"; git -C "$d" add -A; git -C "$d" commit -qm init; echo change >> "$d/f"
zellij kill-session zjhunk 2>/dev/null || true; zellij attach -b zjhunk
zellij --session zjhunk action new-pane -n agent -- bash -c 'sleep 300'   # plain: headless has no client
PID=$(zellij --session zjhunk action list-panes -j | python3 -c 'import sys,json;d=json.load(sys.stdin);ps=[p for v in (d.values() if isinstance(d,dict) else [d]) for p in (v if isinstance(v,list) else [v])];print([p for p in ps if str(p.get("title","")).startswith("agent")][0]["id"])')
rm -rf ~/.cache/zellij-agent-herder
fire(){ printf '%s' "$1" | env ZELLIJ_PANE_ID="$PID" ZELLIJ_SESSION_NAME=zjhunk bash "$HOOK"; }
J='{"hook_event_name":"PostToolUse","tool_name":"Write","prompt_id":"p1","cwd":"'"$d"'","tool_input":{"file_path":"'"$d"'/f"}}'
fire "$J"; sleep 2
n1=$(zellij --session zjhunk action list-panes -j | grep -o 'hunk:hrepo' | wc -l | tr -d ' ')
[ "$n1" = "1" ] || { echo "FAIL: expected 1 hunk pane, got $n1"; exit 1; }
fire "$J"; sleep 1   # same prompt_id -> no second pane
n2=$(zellij --session zjhunk action list-panes -j | grep -o 'hunk:hrepo' | wc -l | tr -d ' ')
[ "$n2" = "1" ] || { echo "FAIL: reopened within same turn, got $n2"; exit 1; }
# clean repo (no changes) -> no pane
d2="$R/clean"; mkdir -p "$d2"; git -C "$d2" init -q; echo x>"$d2/g"; git -C "$d2" add -A; git -C "$d2" commit -qm init
fire '{"hook_event_name":"PostToolUse","tool_name":"Write","prompt_id":"p2","cwd":"'"$d2"'","tool_input":{"file_path":"'"$d2"'/g"}}'; sleep 1
zellij --session zjhunk action list-panes -j | grep -o 'hunk:clean' && { echo "FAIL: opened for clean repo"; exit 1; } || echo "OK: clean repo skipped"
# subagent -> no pane (fresh repo+prompt_id so only the agent_id guard can gate it)
d3="$R/subrepo"; mkdir -p "$d3"; git -C "$d3" init -q; echo a>"$d3/f"; git -C "$d3" add -A; git -C "$d3" commit -qm init; echo b>>"$d3/f"
fire '{"hook_event_name":"PostToolUse","tool_name":"Write","prompt_id":"p3","agent_id":"sub","cwd":"'"$d3"'","tool_input":{"file_path":"'"$d3"'/f"}}'; sleep 1
zellij --session zjhunk action list-panes -j | grep -o 'hunk:subrepo' && { echo "FAIL: opened for subagent"; exit 1; } || echo "OK: subagent skipped"
echo "ALL OK"   # cleanup runs in the EXIT trap (reaps watchers + kills session + rm scratch)
```

- [ ] **Step 2: Run — verify fail** (hook file missing).

- [ ] **Step 3: Write the hook** — Create `.../scripts/hunk-autodiff.sh`:
```sh
#!/bin/sh
# PostToolUse hook: on the agent's first file change in a worktree this turn,
# open `hunk diff --watch` beside the agent pane (no focus steal). Idempotent.
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
# Adaptive placement (mirrors zj_spawn; the hook is standalone and can't source zj.sh):
# relative/directional spawn silently no-ops with no connected client (headless/tests),
# so only pass --near-current-pane -d right when a client is attached.
def client_count():
    try:
        out = subprocess.run(base + ["list-clients"], capture_output=True, text=True, timeout=2).stdout
        return sum(1 for ln in out.splitlines()[1:] if ln.strip())
    except Exception:
        return 0
place = ["--near-current-pane", "-d", "right"] if client_count() > 0 else []
try:
    subprocess.run(base + ["new-pane"] + place + ["--cwd",root,"-n",name,"--"] + cmd,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
except Exception: pass
PY
```

- [ ] **Step 4: Run — verify pass** — one `hunk:hrepo` pane, no second within the turn, `OK: clean repo skipped`, subagent no-op, `ALL OK`.

- [ ] **Step 5: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/scripts/hunk-autodiff.sh
git -C ~/code/mk-skills commit -m "feat(zah): hunk-autodiff PostToolUse hook (live diff pane on first change)"
```

---

## Task 5: `install-hooks.sh` — install both hook sets

**Files:** Create `.../scripts/install-hooks.sh`; Test `/tmp/zah/test_install.sh`.

**Interfaces:** Copies `zellij-agent-status.sh` + `hunk-autodiff.sh` to `~/.claude/hooks/`; idempotently adds to `~/.claude/settings.json`: `UserPromptSubmit`/`Stop`/`Notification` → status hook, and `PostToolUse` (matcher `Edit|Write|MultiEdit|NotebookEdit`, `async:true`) → hunk hook. Backs up settings first; preserves existing hooks (incl. herdr's `SessionStart`).

- [ ] **Step 1: Write the failing test** — Create `/tmp/zah/test_install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
export HOME=/tmp/zah/fakehome; rm -rf "$HOME"; mkdir -p "$HOME/.claude/hooks"
cat > "$HOME/.claude/settings.json" <<'JSON'
{"hooks":{"SessionStart":[{"matcher":"*","hooks":[{"type":"command","command":"echo herdr","timeout":10}]}]}}
JSON
bash ~/code/mk-skills/skills/zellij-agent-herder/scripts/install-hooks.sh
test -x "$HOME/.claude/hooks/zellij-agent-status.sh" || { echo FAIL status hook; exit 1; }
test -x "$HOME/.claude/hooks/hunk-autodiff.sh" || { echo FAIL hunk hook; exit 1; }
python3 - <<'PY'
import json, os
d = json.load(open(os.path.join(os.environ["HOME"], ".claude/settings.json"))); h = d["hooks"]
assert "SessionStart" in h, "clobbered herdr"
for ev in ("UserPromptSubmit","Stop","Notification"):
    assert any("zellij-agent-status.sh" in x["command"] for e in h[ev] for x in e["hooks"]), ev
pt = h["PostToolUse"]
assert any("hunk-autodiff.sh" in x["command"] and x.get("async") is True for e in pt for x in e["hooks"]), "hunk not async"
assert any(e.get("matcher")=="Edit|Write|MultiEdit|NotebookEdit" for e in pt), "matcher"
print("hooks OK")
PY
bash ~/code/mk-skills/skills/zellij-agent-herder/scripts/install-hooks.sh   # idempotency
python3 - <<'PY'
import json, os
d = json.load(open(os.path.join(os.environ["HOME"], ".claude/settings.json")))
n = sum(1 for e in d["hooks"]["Stop"] for x in e["hooks"] if "zellij-agent-status.sh" in x["command"])
assert n == 1, "dup Stop: %d" % n
print("idempotent OK")
PY
echo "ALL OK"
```

- [ ] **Step 2: Run — verify fail** (installer missing).

- [ ] **Step 3: Write the installer** — Create `.../scripts/install-hooks.sh`:
```bash
#!/usr/bin/env bash
# Installs the zellij-agent-herder Claude Code hooks. Idempotent; safe to re-run.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="$HOME/.claude/hooks"; SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$DEST_DIR"
cp "$SRC/zellij-agent-status.sh" "$DEST_DIR/zellij-agent-status.sh"; chmod +x "$DEST_DIR/zellij-agent-status.sh"
cp "$SRC/hunk-autodiff.sh"       "$DEST_DIR/hunk-autodiff.sh";       chmod +x "$DEST_DIR/hunk-autodiff.sh"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
STATUS_HOOK="bash '$DEST_DIR/zellij-agent-status.sh'" HUNK_HOOK="bash '$DEST_DIR/hunk-autodiff.sh'" \
python3 - "$SETTINGS" <<'PY'
import json, os, sys
path = sys.argv[1]; status_cmd = os.environ["STATUS_HOOK"]; hunk_cmd = os.environ["HUNK_HOOK"]
try: cfg = json.load(open(path))
except Exception: cfg = {}
hooks = cfg.setdefault("hooks", {})
def ensure(event, cmd, matcher=None, extra=None):
    groups = hooks.setdefault(event, [])
    if any(cmd in hk.get("command","") for g in groups for hk in g.get("hooks", [])): return
    entry = {"type":"command","command":cmd,"timeout":10}
    if extra: entry.update(extra)
    g = {"hooks":[entry]}
    if matcher is not None: g["matcher"] = matcher
    groups.append(g)
for ev in ("UserPromptSubmit","Stop","Notification"): ensure(ev, status_cmd)
ensure("PostToolUse", hunk_cmd, matcher="Edit|Write|MultiEdit|NotebookEdit", extra={"async": True})
json.dump(cfg, open(path,"w"), indent=2); open(path,"a").write("\n")
print("installed zellij-agent-herder hooks into", path)
PY
```

- [ ] **Step 4: Run — verify pass** — `hooks OK`, `idempotent OK`, `ALL OK`.

- [ ] **Step 5: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/scripts/install-hooks.sh
git -C ~/code/mk-skills commit -m "feat(zah): install-hooks.sh (status + hunk, async)"
```

---

## Task 6: `zellij-peer.sh` wrapper

**Files:** Create `.../scripts/zellij-peer.sh`; Test `/tmp/zah/test_peer.sh`.

**Interfaces:** Consumes all `zj_*`. Subcommands: `start <name> [--cwd DIR] [--direction right|down] -- <agent-cmd...>` (prints `terminal_N`), `ask <name> "<prompt>"` (write + Enter; twice if `PEER_DOUBLE_ENTER=1`), `wait <name> [--status idle] [--timeout S]`, `read <name> [--lines N]`, `list`, `close <name>`.

- [ ] **Step 1: Write the failing test** — Create `/tmp/zah/test_peer.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
PEER=~/code/mk-skills/skills/zellij-agent-herder/scripts/zellij-peer.sh
export ZJ_SESSION=zjpeer
zellij kill-session zjpeer 2>/dev/null || true; zellij attach -b zjpeer
id=$(bash "$PEER" start worker --cwd /tmp -- bash); echo "started -> $id"
[[ "$id" == terminal_* ]] || { echo FAIL id; exit 1; }
bash "$PEER" ask worker "echo PROMPT_ECHOED_123"; sleep 1
bash "$PEER" read worker | grep -q PROMPT_ECHOED_123 || { echo FAIL echo; exit 1; }
bash "$PEER" list | grep -q worker || { echo FAIL list; exit 1; }
bash "$PEER" close worker; sleep 1
bash "$PEER" list | grep -q worker && { echo FAIL still; exit 1; } || echo "OK closed"
echo "ALL OK"; zellij kill-session zjpeer 2>/dev/null || true
```

- [ ] **Step 2: Run — verify fail** (wrapper missing).

- [ ] **Step 3: Write the wrapper** — Create `.../scripts/zellij-peer.sh`:
```bash
#!/usr/bin/env bash
# Peer-agent lifecycle wrapper for zellij. Sources zj.sh from its own dir.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/zj.sh"
usage(){ echo "usage: zellij-peer.sh {start|ask|wait|read|list|close} ..." >&2; exit 2; }
cmd="${1:-}"; shift || usage
case "$cmd" in
  start)
    name="${1:-}"; shift || usage; cwd=""; dir="right"
    while [ $# -gt 0 ]; do case "$1" in
      --cwd) cwd="$2"; shift 2;; --direction) dir="$2"; shift 2;; --) shift; break;; *) break;; esac; done
    args=(-d "$dir" -n "$name"); [ -n "$cwd" ] && args+=(--cwd "$cwd")
    args+=(-- "$@"); zj_spawn "${args[@]}" ;;   # adaptive: near-current when attached, plain when headless
  ask)
    name="${1:-}"; prompt="${2:-}"; [ -n "$name" ] && [ -n "$prompt" ] || usage
    id="$(zj_resolve_id "$name")"; _zj write-chars -p "$id" "$prompt"; _zj write -p "$id" 13
    [ "${PEER_DOUBLE_ENTER:-0}" = "1" ] && _zj write -p "$id" 13 || true ;;
  wait)
    name="${1:-}"; shift || usage; status="idle"; timeout=300
    while [ $# -gt 0 ]; do case "$1" in --status) status="$2"; shift 2;; --timeout) timeout="$2"; shift 2;; *) shift;; esac; done
    id="$(zj_resolve_id "$name")"; zj_wait_status "$id" "$status" "$timeout" ;;
  read)
    name="${1:-}"; shift || usage; lines=200
    while [ $# -gt 0 ]; do case "$1" in --lines) lines="$2"; shift 2;; *) shift;; esac; done
    id="$(zj_resolve_id "$name")"; _zj dump-screen -p "$id" --full | tail -n "$lines" ;;
  list)
    _zj_panes | python3 -c '
import sys, json
for line in sys.stdin:
    p = json.loads(line); t = str(p.get("title","")); base,_,st = t.partition(" · ")
    print("%-14s %-16s %s" % (p["id"], base, st or "-"))' ;;
  close) name="${1:-}"; [ -n "$name" ] || usage; id="$(zj_resolve_id "$name")"; _zj close-pane -p "$id" ;;
  *) usage ;;
esac
```

- [ ] **Step 4: Run — verify pass** — `started -> terminal_N`, `OK closed`, `ALL OK`.

- [ ] **Step 5: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/scripts/zellij-peer.sh
git -C ~/code/mk-skills commit -m "feat(zah): zellij-peer.sh lifecycle wrapper"
```

---

## Task 7: `references/` docs

**Files:** Create `.../references/{peer-agents.md,command-reference.md,pitfalls.md,hooks.md}`.

**Interfaces:** Consumed on demand by SKILL.md pointers. No runtime code.

- [ ] **Step 1: `command-reference.md`** — the complete herdr→zellij mapping table (from this plan's research), every `zj_*` helper signature, and the session/pane addressing model. Include the "capabilities that do not exist in zellij" list and the native `--block-until-exit*` note.

- [ ] **Step 2: `peer-agents.md`** — full peer-agent workflows ported from herdr-peer-agents: one-shot review, implementation helper, bidirectional messaging, the four-level model, per-role prompt guidance ("Do not edit files", explicit stop conditions), and the `zellij-peer.sh` subcommand reference with the `PEER_DOUBLE_ENTER` note. End with "inspect file changes yourself before reporting success."

- [ ] **Step 3: `hooks.md`** — the hook regime: what each event maps to (status) and the hunk-autodiff behavior; how to install (`bash "<skill-base-dir>/scripts/install-hooks.sh"`), what it writes, and how to uninstall (remove the two `~/.claude/hooks/*.sh` and the settings entries). Document the two toggles: (a) hunk trigger on first-change (`PostToolUse`, default) vs on turn-end (move the hunk hook to `Stop`); (b) reference the original `hunk.autodiff` diff-signature "stay-closed" behavior as an alternative to per-turn dedup. Note that a live hunk session can be driven by an agent via the `hunk-review` skill (`hunk session review --repo <root> --json`).

- [ ] **Step 4: `pitfalls.md`** — the Global Constraints sharp edges as a troubleshooting reference: silent bad-id, `--full`/ANSI, focus theft, `$SECONDS`, session-per-fleet, prompt-visible-but-not-submitted (send Enter again), ambiguous names (use `terminal_N`), status stuck (confirm hooks installed + Claude-family agent), hunk pane not opening (git repo? dirty? live session already? cache marker).

- [ ] **Step 5: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/references/
git -C ~/code/mk-skills commit -m "docs(zah): reference docs (peer-agents, command-reference, hooks, pitfalls)"
```

---

## Task 8: `SKILL.md` (lean) + skill-level verification

**Files:** Create `.../SKILL.md`.

**Interfaces:** The entry point; ≤ ~500 words body per superpowers:writing-skills; `description` is triggering-conditions-only (no workflow summary).

- [ ] **Step 1: Write SKILL.md** — frontmatter:
```yaml
---
name: zellij-agent-herder
description: "Use when running inside zellij (the ZELLIJ env var is set) and you need to control panes/tabs/sessions, spawn or coordinate peer coding agents, wait on their output or status, or watch changes in a live diff. Not for use outside zellij."
---
```
Body sections (lean; push detail to references):
1. **Guard.** Check `$ZELLIJ` is set; if not, say you are not inside zellij and stop.
2. **Concepts (brief).** sessions→tabs→panes; addressing = `(session, pane_id)`; `--name` is title-only (resolve via `zj_resolve_id`); session via `--session`/`$ZELLIJ_SESSION_NAME`. Non-focus-stealing spawn = `new-pane --near-current-pane`.
3. **Helpers.** `source "<skill-base-dir>/scripts/zj.sh"` → `_zj`, `zj_resolve_id`, `zj_pane_exists`, `zj_wait_output`, `zj_wait_exit`, `zj_wait_status`. One-line note: all paths are relative to this skill's base directory; never hardcode an install path.
4. **Core quick reference** (table, ~10 rows): list panes; read `dump-screen -p <id> [--full]`; spawn via `zj_spawn -d right --cwd DIR -n NAME -- CMD` (adaptive: near-current when attached, plain when headless — never call `new-pane --near-current-pane`/`-d` directly, it no-ops with no client); send `write-chars -p <id>` + Enter `write -p <id> 13`; close `close-pane -p <id>`; tabs `go-to-tab-name`; wait output/exit/status via `zj_*`; native one-shot wait `zellij run --block-until-exit-success -- CMD`.
5. **Peer agents.** One sentence + `**REQUIRED SUB-SKILL / see** references/peer-agents.md` and the `scripts/zellij-peer.sh` one-liner.
6. **Hooks (status + hunk).** Two sentences: run `install-hooks.sh` once to get pane-title status and the auto `hunk diff --watch` pane on first change; see `references/hooks.md`. Cross-reference the `hunk-review` skill for driving a live session.
7. **Pointers.** `references/command-reference.md` (full mapping), `references/pitfalls.md` (sharp edges).
Keep under budget; verify with `wc -w`.

- [ ] **Step 2: RED/GREEN skill verification (superpowers:writing-skills)** — Dispatch a fresh subagent (Sonnet) given ONLY the skill dir path and this task: *"You are inside a zellij session `<name>` with a pane running a peer agent. Using only the zellij-agent-herder skill, spawn a `bash` peer named tester, make it echo a unique token, wait for it, and read it back."* Do NOT hint the commands. Expected (GREEN): the subagent reads SKILL.md → follows the peer-agents reference → succeeds. If it stalls or misuses commands, record the gap and fix SKILL.md/references (REFACTOR), then re-run. (Run against a real scratch session; unique session name; do not pkill anything.)

- [ ] **Step 3: Commit**
```bash
git -C ~/code/mk-skills add skills/zellij-agent-herder/SKILL.md
git -C ~/code/mk-skills commit -m "docs(zah): lean SKILL.md + skill-level verification"
```

---

## Task 9: Repo packaging + `skills add` install verification

**Files:** Modify `~/code/mk-skills/README.md`.

- [ ] **Step 1: Confirm layout + frontmatter**
```bash
find ~/code/mk-skills/skills -name SKILL.md
sed -n '1,6p' ~/code/mk-skills/skills/zellij-agent-herder/SKILL.md
```
Expected: exactly `skills/zellij-agent-herder/SKILL.md`, with `name:` + `description:`.

- [ ] **Step 2: Install from local path into a scratch target**
```bash
mkdir -p /tmp/zah/installtest && cd /tmp/zah/installtest
npx -y skills add ~/code/mk-skills --skill '*' -a claude-code 2>&1 | tail -20
find . -path '*zellij-agent-herder*' -name '*.sh' -o -path '*zellij-agent-herder*' -name '*.md' | sort
bash ./.claude/skills/zellij-agent-herder/scripts/zellij-peer.sh list 2>&1 | head -3
```
Expected: the skill lands under `./.claude/skills/zellij-agent-herder/` with `scripts/` + `references/` intact; the wrapper sources `zj.sh` and runs (a "no zellij session" error is fine; a "cannot find zj.sh"/source error is a FAIL).

- [ ] **Step 3: Write the README** — Overwrite `~/code/mk-skills/README.md`: one-line description; **Install** (`npx skills add anateus/mk-skills`, `-g` global, single-skill example); **Skills** table (zellij-agent-herder · what it does · requires zellij ≥ 0.44, hunk for the diff feature); **Setup** note pointing at `install-hooks.sh` for status + hunk hooks.

- [ ] **Step 4: Commit and push (on user go-ahead)**
```bash
git -C ~/code/mk-skills add README.md
git -C ~/code/mk-skills commit -m "docs: install instructions and skills index"
git -C ~/code/mk-skills push origin HEAD   # only after the user confirms; `skills add anateus/mk-skills` needs it pushed
```

---

## Optional Task 10 (deferred): WASM status/wait plugin

Not part of v1. If poll latency/CPU matters, replace poll loops with a Rust WASM plugin (subscribe `PaneUpdate`/`CommandPaneExited`, reply over a blocking `zellij pipe`). Prior art: `mrshu/zjctl` (ships `pane wait-idle`), `thisisryanswift/zellij-agent-tools`. Resolve first: non-interactive plugin permission pre-approval; correct wasm target (`wasm32-wasip1` vs `wasm32-wasi`). The hook-based status path makes this pure optimization.

---

## Self-Review

**Spec coverage:**
- Merge two skills → one → single `zellij-agent-herder/` (Tasks 1–8), one `zj.sh` (no vendoring).
- Progressive disclosure → lean SKILL.md (Task 8) + `references/` loaded on demand (Task 7); `description` is triggers-only.
- Multiplexer control (list/read/spawn/send/close/tabs/waits) → `zj.sh` (Tasks 1–3) + SKILL.md quick-ref (Task 8) + `command-reference.md` (Task 7).
- Peer agents → `zellij-peer.sh` (Task 6) + `peer-agents.md` (Task 7).
- Agent status → status hook + `zj_wait_status` (Task 3), installed by Task 5.
- **New hunk-on-change feature** → `hunk-autodiff.sh` (Task 4) replicating the `hunk.autodiff` plugin, on the same hook regime (Task 5), documented in `hooks.md` (Task 7). Trigger honors "once changes begin" (PostToolUse) with an idle-based toggle documented.
- Distribution via `skills add` → flat layout, relative self-location, README, verified installs (Task 9).

**Placeholder scan:** code tasks (1–6) carry complete scripts + runnable tests with expected output; doc tasks (7–8) specify exact section content and the required facts. Task 0 de-risks the unknowns (JSON shape, `ZELLIJ_PANE_ID` format, hunk session behavior) before code depends on them; scripts absorb either `list-panes -j` shape.

**Type/name consistency:** helper names stable across tasks (`_zj`, `_zj_panes`, `zj_resolve_id`, `zj_pane_exists`, `zj_wait_output`, `zj_wait_exit`, `zj_wait_status`); status suffix separator `" · "` identical in the status hook (Task 3), `zj_wait_status` (Task 3), and `zellij-peer.sh list` (Task 6); Enter is `write -p <id> 13` in the hook test, wrapper, and constraints; hunk pane title prefix `hunk:` consistent between `hunk-autodiff.sh` and its test (Task 4); PostToolUse matcher string identical in the installer and its test (Task 5).
