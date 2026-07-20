#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../../../" && pwd)"
CTL="$ROOT_DIR/skills/zellij-agent-herder/scripts/hunk-stream.py"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export HOME="$T/home" XDG_CACHE_HOME="$T/cache"; mkdir -p "$HOME"
git -C "$T" init -q repo
git -C "$T/repo" config user.email test@example.com
git -C "$T/repo" config user.name Test
printf 'one\n' > "$T/repo/a.txt"
git -C "$T/repo" add a.txt && git -C "$T/repo" commit -qm base
BASE="$(git -C "$T/repo" rev-parse HEAD)"
S1="$(python3 "$CTL" signature --root "$T/repo" --base "$BASE")"
printf 'two\n' >> "$T/repo/a.txt"
S2="$(python3 "$CTL" signature --root "$T/repo" --base "$BASE")"
[ "$S1" != "$S2" ]
printf 'new\n' > "$T/repo/new.txt"
S3="$(python3 "$CTL" signature --root "$T/repo" --base "$BASE")"
[ "$S2" != "$S3" ]
K1="$(python3 "$CTL" state-key --session s --parent terminal_1 --root "$T/repo" --kind worktree)"
K2="$(python3 "$CTL" state-key --session s --parent terminal_1 --root "$T/repo" --kind worktree)"
[ "$K1" = "$K2" ]
echo 'identity/signature: PASS'
