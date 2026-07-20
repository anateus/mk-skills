#!/usr/bin/env bash
# Helper library for the zellij-agent-herder skill.
# Source this file, then call zj_* functions. Requires zellij >= 0.44 and python3.
# Target session: set ZJ_SESSION, else falls back to $ZELLIJ_SESSION_NAME.

ZJ_SESSION="${ZJ_SESSION:-${ZELLIJ_SESSION_NAME:-}}"
ZJ_IDENTITY_SCRIPT="${ZAH_IDENTITY_SCRIPT:-${ZJ_IDENTITY_SCRIPT:-}}"

# Resolve pane-identity.py when the caller did not supply its installed/source path.
if [ -z "$ZJ_IDENTITY_SCRIPT" ]; then
  _zj_source_path=""
  if [ -n "${BASH_VERSION:-}" ]; then
    _zj_source_path="${BASH_SOURCE[0]}"
  elif [ -n "${ZSH_VERSION:-}" ]; then
    _zj_source_path="$(eval 'printf %s "${(%):-%x}"')"
  fi
  for _zj_identity_candidate in \
    "${_zj_source_path:+$(cd "$(dirname "$_zj_source_path")" 2>/dev/null && pwd)/pane-identity.py}" \
    "${HOME:-}/.claude/skills/zellij-agent-herder/scripts/pane-identity.py" \
    "${HOME:-}/.agents/skills/zellij-agent-herder/scripts/pane-identity.py" \
    "${CODEX_HOME:-}/skills/zellij-agent-herder/scripts/pane-identity.py"
  do
    if [ -f "$_zj_identity_candidate" ]; then
      ZJ_IDENTITY_SCRIPT="$_zj_identity_candidate"; break
    fi
  done
  unset _zj_identity_candidate _zj_source_path
fi

zj_identity() {
  [ -n "$ZJ_IDENTITY_SCRIPT" ] && [ -f "$ZJ_IDENTITY_SCRIPT" ] || return 1
  python3 "$ZJ_IDENTITY_SCRIPT" "$@"
}

zj_normalize_pane_id() {
  case "$1" in terminal_*|plugin_*) echo "$1" ;; *) echo "terminal_$1" ;; esac
}

# Locate the controller from this file, whether sourced by bash/zsh or executed by bash
# for fish callers. Keep the shell-facing API here; pane lifecycle belongs to Python.
if [ -n "${ZSH_VERSION:-}" ]; then
  eval '_ZJ_SCRIPT_PATH=${(%):-%x}'
else
  _ZJ_SCRIPT_PATH="${BASH_SOURCE[0]}"
fi
_ZJ_SCRIPT_DIR="$(cd "$(dirname "$_ZJ_SCRIPT_PATH")" && pwd -P)"
_ZJ_HUNK_STREAM="$_ZJ_SCRIPT_DIR/hunk-stream.py"

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
    if isinstance(pid, int): p["id"] = ("plugin_%d" if p.get("is_plugin") else "terminal_%d") % pid
    print(json.dumps(p))
'
}

# zj_resolve_id <name> -> prints terminal_N (exit 1 not found, 2 ambiguous).
# Matches explicit ids, titles/bases, and stable cached identity names in this session.
zj_resolve_id() {
  _zj_panes | python3 -c '
import json, os, pathlib, sys
name, session = sys.argv[1:3]; hits = []
cache = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home()/".cache")
cache = cache/"zellij-agent-herder"/"panes"/session
for line in sys.stdin:
    p = json.loads(line); t = str(p.get("title",""))
    pid = p["id"]; identity_name = ""
    try: identity_name = str(json.loads((cache/(pid+".json")).read_text()).get("name", ""))
    except Exception: pass
    if pid == name or t == name or t.split(" · ",1)[0] == name or identity_name == name:
        hits.append(pid)
if len(hits) == 1: print(hits[0])
elif not hits: sys.exit(1)
else: sys.stderr.write("ambiguous: %d match %r\n" % (len(hits), name)); sys.exit(2)
' "$1" "${ZJ_SESSION:-${ZELLIJ_SESSION_NAME:-default}}"
}

# zj_close_pane <pane_id> -> close and remove only this session-scoped identity.
zj_close_pane() {
  local pane_id; pane_id="$(zj_normalize_pane_id "$1")"
  _zj close-pane -p "$pane_id"
  zj_identity remove --session "${ZJ_SESSION:-${ZELLIJ_SESSION_NAME:-default}}" --pane "$pane_id" \
    >/dev/null 2>&1 || true
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
    # Portable arg-strip (bash AND zsh — SKILL.md tells users to `source` this, and
    # macOS defaults to zsh whose arrays are 1-indexed). Iterate positional params via
    # shift; no indexed-array access. Drop -d/--direction (+value) and --near-current-pane.
    local a=()
    while [ "$#" -gt 0 ]; do
      case "$1" in
        -d|--direction)      shift; if [ "$#" -gt 0 ]; then shift; fi ;;
        --near-current-pane) shift ;;
        *)                   a+=("$1"); shift ;;
      esac
    done
    _zj new-pane "${a[@]}"
  fi
}

_zj_stream() {
  local command="$1" root="$2" requested_root="$2" base="$3" label="$4"; shift 4
  local caller="$1"; shift
  command -v hunk >/dev/null 2>&1 \
    || { echo "$caller: hunk not on PATH" >&2; return 2; }
  root="$(cd "$root" 2>/dev/null && pwd -P)" \
    || { echo "$caller: root not found: $requested_root" >&2; return 1; }
  [ -n "${ZJ_SESSION:-}" ] \
    || { echo "$caller: ZJ_SESSION is not set" >&2; return 1; }
  local parent="${ZELLIJ_PANE_ID:-terminal_0}" output
  local args=("$_ZJ_HUNK_STREAM" "$command" --session "$ZJ_SESSION" --parent "$parent" \
    --root "$root" --base "$base" --label "$label")
  while [ "$#" -gt 0 ]; do args+=("$1"); shift; done
  output="$(python3 "${args[@]}")" || return 1
  [ -n "$output" ] || return 1
  printf '%s\n' "$output"
}

# zj_watch_worktree <worktree_abs_path> <base_sha> [label] -> pane_id.
zj_watch_worktree() {
  local root="$1" base="$2"
  local label="${3:-$(basename "$1")}" # Use the historical default label.
  _zj_stream ensure "$root" "$base" "$label" zj_watch_worktree --kind worktree
}

# zj_watch_session <parent_repo_root> <base_sha> <label> [worktree_pane_id...]
# Teardown counterpart to zj_watch_worktree. After the fan-out is merged into the parent
# tree and the worktrees are removed, call this once: it closes each per-worktree diff pane
# you list (their dirs are gone, so their restart loops would otherwise spin on the error)
# and opens ONE aggregate pane over the parent tree showing the whole session's work —
# parent working tree vs the SAME fixed <base_sha> the fan-out branched from, so it spans
# every merged commit plus anything still uncommitted. Same fixed-base rule as
# zj_watch_worktree: NOT HEAD, which is empty once the merges are committed. Echoes the
# aggregate pane's terminal_N.
zj_watch_session() {
  local root="$1" base="$2" label="$3"; shift 3
  local args=() id
  for id in "$@"; do args+=(--child-pane "$id"); done
  _zj_stream rollup "$root" "$base" "$label" zj_watch_session "${args[@]}"
}

# zj_review_stream <repo_root> <base_sha> [label] -> explicitly reopen its stream.
zj_review_stream() {
  local root="$1" base="$2"
  local label="${3:-$(basename "$1")}" # Use the historical default label.
  _zj_stream ensure "$root" "$base" "$label" zj_review_stream --kind worktree --explicit
}

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
  # No `trap ... RETURN` — that pseudo-signal is bash-only and errors under zsh (this file
  # is sourced, macOS defaults to zsh). Single cleanup point after the loop instead.
  local start=$SECONDS dump rc=1; dump="$(mktemp "${TMPDIR:-/tmp}/zj.XXXXXX")"
  while :; do
    _zj dump-screen -p "$pane_id" --full --path "$dump" >/dev/null 2>&1 || true
    if [ "$mode" = "--regex" ]; then grep -qE -- "$match" "$dump" 2>/dev/null && { rc=0; break; }
    else grep -qF -- "$match" "$dump" 2>/dev/null && { rc=0; break; }; fi
    (( SECONDS - start >= timeout_s )) && { rc=1; break; }
    sleep "$interval_s"
  done
  rm -f "$dump"
  return "$rc"
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

# Invocation dispatcher: when this file is EXECUTED (not sourced) with args, run the
# named helper — so non-POSIX shells (fish) that can't `source` it can still call a
# helper: `bash <dir>/zj.sh zj_spawn -n worker -- bash`. Must NEVER fire when sourced
# (the agent path, bash/zsh) — detect sourced-vs-executed robustly per shell, since a
# zsh `source` can carry preset positional params ($# > 0 is not a safe sourced signal).
if [ -n "${ZSH_VERSION:-}" ]; then
  # zsh: ZSH_EVAL_CONTEXT ends in ':file' when sourced (exec is 'toplevel'/'cmdarg').
  case "${ZSH_EVAL_CONTEXT:-}" in
    *:file) : ;;                          # sourced — never dispatch
    *) [ "$#" -gt 0 ] && "$@" ;;          # executed as a zsh script
  esac
elif [ "${BASH_SOURCE:-$0}" = "$0" ] && [ "$#" -gt 0 ]; then
  "$@"                                    # bash: BASH_SOURCE==$0 only when executed
fi
