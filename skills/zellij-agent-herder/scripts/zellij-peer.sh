#!/usr/bin/env bash
# Peer-agent lifecycle wrapper for zellij. Sources zj.sh from its own dir.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
export ZAH_IDENTITY_SCRIPT="${ZAH_IDENTITY_SCRIPT:-$script_dir/pane-identity.py}"
source "$script_dir/zj.sh"
usage(){ echo "usage: zellij-peer.sh {start|ask|wait|read|list|close} ..." >&2; exit 2; }
cmd="${1:-}"; shift || usage
case "$cmd" in
  start)
    name="${1:-}"; shift || usage; cwd=""; dir="right"
    while [ $# -gt 0 ]; do case "$1" in
      --cwd) cwd="$2"; shift 2;; --direction) dir="$2"; shift 2;; --) shift; break;; *) break;; esac; done
    args=(-d "$dir" -n "$name"); [ -n "$cwd" ] && args+=(--cwd "$cwd")
    args+=(-- "$@")
    id="$(zj_spawn "${args[@]}")"                 # real terminal_N from new-pane
    id="$(zj_normalize_pane_id "$(printf '%s\n' "$id" | tail -n 1)")"
    session="${ZJ_SESSION:-${ZELLIJ_SESSION_NAME:-default}}"
    parent="$(zj_normalize_pane_id "${ZELLIJ_PANE_ID:-0}")"
    parent_title="$(_zj_panes | python3 -c '
import json, sys
want=sys.argv[1]
for line in sys.stdin:
    p=json.loads(line)
    if p.get("id") == want: print(str(p.get("title", ""))); break
' "$parent")"
    base_cwd="${cwd:-$PWD}"; repo_name=""
    repo_root="$(git -C "$base_cwd" rev-parse --show-toplevel 2>/dev/null || true)"
    [ -n "$repo_root" ] && repo_name="$(basename "$repo_root")"
    zj_identity assign --session "$session" --pane "$parent" \
      --native-name "${parent_title:-agent}" --display-label "${parent_title:-agent}" \
      --cwd "$PWD" --repo-name "$repo_name" >/dev/null
    zj_identity child --session "$session" --pane "$id" --parent "$parent" \
      --native-name "$name" --display-label "$name" --cwd "$base_cwd" \
      --repo-name "$repo_name" >/dev/null
    title="$(zj_identity render --session "$session" --pane "$id")"
    _zj rename-pane -p "$id" "$title" >/dev/null
    echo "$id" ;;                             # adaptive spawn; breadcrumb after real id
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
  close) name="${1:-}"; [ -n "$name" ] || usage; id="$(zj_resolve_id "$name")"; zj_close_pane "$id" ;;
  *) usage ;;
esac
