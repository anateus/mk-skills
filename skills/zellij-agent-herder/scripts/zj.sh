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
    if isinstance(pid, int): p["id"] = ("plugin_%d" if p.get("is_plugin") else "terminal_%d") % pid
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
