#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../../" && pwd)"
ZJ="$ROOT_DIR/skills/zellij-agent-herder/scripts/zj.sh"

run_spawn() {
  local panes="$1"
  ZELLIJ_PANE_ID=1 PANES="$panes" bash -c '
    source "$1"
    zj_client_count() { echo 1; }
    _zj_panes() { printf "%s\n" "$PANES"; }
    _zj() { printf "%s\n" "$*"; }
    zj_spawn -d right -n worker -- bash
  ' bash "$ZJ"
}

three_in_parent_tab='{"id":"terminal_1","tab_id":7}
{"id":"terminal_2","tab_id":7}
{"id":"terminal_3","tab_id":7}
{"id":"terminal_8","tab_id":9}'
four_in_parent_tab="$three_in_parent_tab
{\"id\":\"terminal_4\",\"tab_id\":7}"
four_with_one_suppressed="$three_in_parent_tab
{\"id\":\"terminal_4\",\"tab_id\":7,\"is_suppressed\":true}"

below_threshold="$(run_spawn "$three_in_parent_tab")"
case "$below_threshold" in
  *--stacked*) echo "three visible panes unexpectedly stacked" >&2; exit 1 ;;
esac

at_threshold="$(run_spawn "$four_in_parent_tab")"
case "$at_threshold" in
  *"new-pane --near-current-pane --stacked "*) ;;
  *) echo "four visible panes were not stacked: $at_threshold" >&2; exit 1 ;;
esac

suppressed_not_visible="$(run_spawn "$four_with_one_suppressed")"
case "$suppressed_not_visible" in
  *--stacked*) echo "suppressed pane was counted as visible" >&2; exit 1 ;;
esac

echo "zj spawn placement: PASS"
