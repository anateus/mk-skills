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
