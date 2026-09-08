#!/usr/bin/env bash
# Helper library for the zellij-agent-herder skill.
# Source this file, then call zj_* functions. Requires a zellij build with
# `new-pane --no-focus` (zellij-org/zellij#5346) and python3.
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
# Include tab and state fields so placement can count visible panes in the parent's tab.
_zj_panes() {
  _zj list-panes -j -t -s 2>/dev/null | python3 -c '
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

# zj_visible_panes_in_parent_tab -> count non-suppressed panes beside ZELLIJ_PANE_ID.
zj_visible_panes_in_parent_tab() {
  _zj_panes | python3 -c '
import json, sys
parent_id = sys.argv[1]
items = [json.loads(line) for line in sys.stdin if line.strip()]
parent = next((item for item in items if item.get("id") == parent_id), None)
if parent is None:
    print(0)
    raise SystemExit
tab_id = parent.get("tab_id")
tab_position = parent.get("tab_position")
def same_tab(item):
    if tab_id is not None:
        return item.get("tab_id") == tab_id
    return tab_position is not None and item.get("tab_position") == tab_position
print(sum(same_tab(item) and not item.get("is_suppressed", False) for item in items))
' "$(zj_normalize_pane_id "${ZELLIJ_PANE_ID:-0}")"
}

# zj_spawn [new-pane args...] -> spawn a pane; echoes new-pane's status line (terminal_N).
# Native --no-focus places relative to the issuing pane without disturbing clients.
# If its tab already has at least four visible panes, stack the new pane behind its parent.
zj_spawn() {
  if [ "$(zj_visible_panes_in_parent_tab)" -ge 4 ]; then
    # --stacked is mutually exclusive with --direction in zellij; drop any direction flag.
    local -a rest=(); local skip=0
    for a in "$@"; do
      if [ "$skip" = 1 ]; then skip=0; continue; fi
      case "$a" in -d|--direction) skip=1;; *) rest+=("$a");; esac
    done
    _zj new-pane --no-focus --stacked "${rest[@]}"
  else
    _zj new-pane --no-focus "$@"
  fi
}

# zj_spawn_grouped <Kind> [-n NAME] [--cwd DIR] [-d DIR ignored] -- CMD...
# -> prints the created terminal_N. Kind is Peers or Reviews. Group tabs are
# named after the originating tab and hold up to four visible terminal panes.
zj_spawn_grouped() {
  local kind="${1:-}"; shift || true
  case "$kind" in Peers|Reviews) ;; *) echo "zj_spawn_grouped: kind must be Peers or Reviews" >&2; return 2 ;; esac
  local name="" cwd=""; local -a cmd=()
  while [ $# -gt 0 ]; do
    case "$1" in
      -n|--name) [ $# -ge 2 ] || { echo "zj_spawn_grouped: $1 needs a value" >&2; return 2; }; name="$2"; shift 2;;
      --cwd) [ $# -ge 2 ] || { echo "zj_spawn_grouped: --cwd needs a value" >&2; return 2; }; cwd="$2"; shift 2;;
      -d|--direction) [ $# -ge 2 ] || { echo "zj_spawn_grouped: $1 needs a value" >&2; return 2; }; shift 2;;
      --) shift; cmd=("$@"); break;;
      *) echo "zj_spawn_grouped: unknown option: $1" >&2; return 2;;
    esac
  done
  [ "${#cmd[@]}" -gt 0 ] || { echo "zj_spawn_grouped: command is required after --" >&2; return 2; }

  local origin="${ZJ_ORIGIN_PANE:-${ZELLIJ_PANE_ID:-terminal_0}}"
  origin="$(zj_normalize_pane_id "$origin")"
  local before; before="$(_zj_panes)" || return 1
  local placement; placement="$(printf '%s\n' "$before" | python3 -c '
import json, re, sys
origin, kind = sys.argv[1:]
items = [json.loads(line) for line in sys.stdin if line.strip()]
parent = next((item for item in items if item.get("id") == origin), None)
if parent is None:
    raise SystemExit("zj_spawn_grouped: origin pane not found: " + origin)
tab_name = str(parent.get("tab_name") or "")
match = re.fullmatch(r"(.+) - (?:Peers|Reviews) [0-9]+", tab_name)
base = match.group(1) if match else (tab_name or "tab")
pattern = re.compile(r"^" + re.escape(base) + r" - " + re.escape(kind) + r" ([0-9]+)$")
groups = {}
for item in items:
    name = str(item.get("tab_name") or "")
    match = pattern.fullmatch(name)
    if not match:
        continue
    number = int(match.group(1))
    tab_id = item.get("tab_id")
    key = str(tab_id) if tab_id is not None else ""
    groups.setdefault(number, {"tab_id": tab_id, "key": key})
if not groups:
    print(json.dumps({"base": base, "number": 1, "reuse": False, "tab_id": None}))
    raise SystemExit
number = max(groups)
target = groups[number]
visible = sum(
    str(item.get("tab_id")) == target["key"]
    and not item.get("is_plugin", False)
    and not item.get("is_suppressed", False)
    and not item.get("is_floating", False)
    for item in items
)
reuse = visible < 4 and target["tab_id"] is not None
print(json.dumps({"base": base, "number": number if reuse else number + 1,
                  "reuse": reuse, "tab_id": target["tab_id"] if reuse else None}))
' "$origin" "$kind")" || return 1
  local base number reuse tab_id
  base="$(printf '%s' "$placement" | python3 -c 'import json,sys; print(json.load(sys.stdin)["base"])')"
  number="$(printf '%s' "$placement" | python3 -c 'import json,sys; print(json.load(sys.stdin)["number"])')"
  reuse="$(printf '%s' "$placement" | python3 -c 'import json,sys; print(1 if json.load(sys.stdin)["reuse"] else 0)')"
  tab_id="$(printf '%s' "$placement" | python3 -c 'import json,sys; v=json.load(sys.stdin)["tab_id"]; print("" if v is None else v)')"
  local target_tab="$tab_id" tab_name="$base - $kind $number" output
  local -a args
  if [ "$reuse" = 1 ]; then
    args=(new-pane --no-focus --tab-id "$target_tab")
    [ -n "$name" ] && args+=(--name "$name")
    [ -n "$cwd" ] && args+=(--cwd "$cwd")
    args+=(-- "${cmd[@]}")
    _zj "${args[@]}" >/dev/null || return 1
  else
    args=(new-tab --no-focus --name "$tab_name")
    [ -n "$cwd" ] && args+=(--cwd "$cwd")
    args+=(-- "${cmd[@]}")
    output="$(_zj "${args[@]}")" || return 1
    target_tab="$(printf '%s\n' "$output" | tail -n 1)"
    case "$target_tab" in ''|*[!0-9]*) echo "zj_spawn_grouped: new-tab returned invalid tab id: $target_tab" >&2; return 1 ;; esac
  fi

  local tries=0 candidate_count candidates new=""
  while [ "$tries" -lt 20 ]; do
    candidates="$(_zj_panes | python3 -c '
import json, sys
before = set(sys.argv[1].split()); target = str(sys.argv[2])
candidates = []
for line in sys.stdin:
    item = json.loads(line)
    if item.get("is_plugin", False) or item.get("id") in before:
        continue
    if item.get("tab_id") is None or str(item.get("tab_id")) != target:
        continue
    candidates.append(item.get("id"))
print("\n".join(str(item) for item in candidates))
' "$(printf '%s\n' "$before" | python3 -c 'import json,sys; print(" ".join(json.loads(l)["id"] for l in sys.stdin))')" "$target_tab")" || return 1
    candidate_count="$(printf '%s\n' "$candidates" | awk 'NF {n++} END {print n+0}')"
    if [ "$candidate_count" -eq 1 ]; then new="$(printf '%s\n' "$candidates")"; break; fi
    if [ "$candidate_count" -gt 1 ]; then
      echo "zj_spawn_grouped: ambiguous new pane in tab $target_tab: $candidates" >&2
      return 1
    fi
    tries=$((tries + 1)); sleep 0.25
  done
  [ -n "$new" ] || { echo "zj_spawn_grouped: could not identify new pane in tab $target_tab" >&2; return 1; }
  [ -z "$name" ] || { _zj rename-pane -p "$new" "$name" >/dev/null || return 1; }
  printf '%s\n' "$new"
}

# zj_spawn_tab is retained for callers that need the historical entrypoint.
# It now uses the same grouped Peers placement policy.
zj_spawn_tab() { zj_spawn_grouped Peers "$@"; }

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
