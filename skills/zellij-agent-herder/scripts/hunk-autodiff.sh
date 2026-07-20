#!/bin/sh
# PostToolUse hook: normalize host payloads through the stream controller.
set -eu
input="$(cat 2>/dev/null || true)"
[ -n "${ZELLIJ_PANE_ID:-}" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
printf '%s\n' "$input" | python3 "$SCRIPT_DIR/hunk-stream.py" edit >/dev/null 2>&1 || true
