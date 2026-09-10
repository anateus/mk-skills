#!/usr/bin/env bash
# Offline tests for codex-run: no real `codex` process is spawned or
# required. Exercises CLI parsing, job-file bookkeeping in an isolated
# state dir, and worktree auto-root detection via --print-policy.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/codex-run.mjs"
T="$(mktemp -d)"
T="$(cd "$T" && pwd -P)"  # canonicalize (macOS mktemp is under /var, a symlink to /private/var)
trap 'rm -rf "$T"' EXIT

STATE_DIR="$T/state"
export CODEX_RUN_STATE_DIR="$STATE_DIR"

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

# --- usage error: missing -p ---
set +e
OUT="$(node "$SCRIPT" -o "$T/out.md" 2>&1)"
RC=$?
set -e
[ "$RC" -eq 2 ] || fail "missing -p: expected rc 2, got $RC"
echo "$OUT" | grep -q "missing -p" || fail "missing -p: expected usage message, got: $OUT"
echo "$OUT" | grep -q "^codex-run -p prompt.md" || fail "missing -p: expected usage text on stderr"
echo "PASS: missing -p prints usage, rc 2"

# --- -h prints usage, rc 0 ---
set +e
OUT="$(node "$SCRIPT" -h 2>&1)"
RC=$?
set -e
[ "$RC" -eq 0 ] || fail "-h: expected rc 0, got $RC"
echo "$OUT" | grep -q "^codex-run -p prompt.md" || fail "-h: expected usage text"
echo "PASS: -h prints usage, rc 0"

# --- list with empty state dir: no output, rc 0 ---
set +e
OUT="$(node "$SCRIPT" list 2>&1)"
RC=$?
set -e
[ "$RC" -eq 0 ] || fail "list (empty): expected rc 0, got $RC"
[ -z "$OUT" ] || fail "list (empty): expected no output, got: $OUT"
echo "PASS: list with empty state dir prints nothing, rc 0"

# --- status <unknown>: non-zero rc, clear message ---
set +e
OUT="$(node "$SCRIPT" status cr-does-not-exist 2>&1)"
RC=$?
set -e
[ "$RC" -ne 0 ] || fail "status <unknown>: expected non-zero rc, got 0"
echo "$OUT" | grep -qi "no such job or thread" || fail "status <unknown>: expected a clear not-found message, got: $OUT"
echo "PASS: status <unknown> is non-zero with a clear message"

# --- worktree common-dir detection via --print-policy (no codex contacted) ---
REPO="$T/repo"
git init -q "$REPO"
git -C "$REPO" config user.email test@example.com
git -C "$REPO" config user.name Test
echo hi > "$REPO/a.txt"
git -C "$REPO" add -A
git -C "$REPO" commit -qm init
git -C "$REPO" worktree add -q "$T/wt" -b wt-branch

POLICY="$(node "$SCRIPT" --print-policy -C "$T/wt" -s workspace-write)"
COMMON_DIR="$(git -C "$REPO" rev-parse --git-common-dir)"
case "$COMMON_DIR" in
  /*) ;;
  *) COMMON_DIR="$REPO/$COMMON_DIR" ;;
esac
# Check membership in the writableRoots *array* specifically (not just
# anywhere in the JSON) — worktreeRoot is reported separately and would
# make this assertion pass vacuously if we only grepped the whole blob.
ROOTS_JOINED="$(echo "$POLICY" | node -e "
  let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
    const p=JSON.parse(d);
    console.log((p.sandboxPolicy.writableRoots||[]).join('\n'));
  });
")"
echo "$ROOTS_JOINED" | grep -qxF "$COMMON_DIR" || fail "print-policy: expected common git dir '$COMMON_DIR' in sandboxPolicy.writableRoots, got roots: [$ROOTS_JOINED]"
echo "$POLICY" | grep -q '"type": "workspaceWrite"' || fail "print-policy: expected workspaceWrite sandbox type"
echo "PASS: worktree common-dir detected and added as a writable root"

# --- print-policy on a non-worktree dir: no worktreeRoot ---
POLICY2="$(node "$SCRIPT" --print-policy -C "$REPO" -s read-only --net)"
echo "$POLICY2" | grep -q '"worktreeRoot": null' || fail "print-policy (non-worktree): expected worktreeRoot null, got: $POLICY2"
echo "$POLICY2" | grep -q '"networkAccess": true' || fail "print-policy (non-worktree): expected networkAccess true under --net"
echo "PASS: non-worktree dir reports no worktree root; --net flips networkAccess"

echo "All codex-run offline tests passed."
