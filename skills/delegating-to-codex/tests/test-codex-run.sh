#!/usr/bin/env bash
# Offline tests for codex-run: no real `codex` process is spawned or
# required. Exercises CLI parsing, job-file bookkeeping in an isolated
# state dir, and the sandbox/thread-config policy via --print-policy.
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

# --- -w relative root resolves absolute in BOTH sandboxPolicy.writableRoots
#     and threadConfig — this is the thread-level override that actually
#     gets enforced by the exec tool; sandboxPolicy alone was verified live
#     to be echoed back by thread/start but not honored for writes. ---
CWD_DIR="$T/cwd"
mkdir -p "$CWD_DIR/rel/dir"
EXPECT_ROOT="$CWD_DIR/rel/dir"
POLICY="$(node "$SCRIPT" --print-policy -C "$CWD_DIR" -s workspace-write -w rel/dir)"
CHECK="$(echo "$POLICY" | node -e "
  let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
    const p = JSON.parse(d);
    const roots = p.sandboxPolicy.writableRoots || [];
    const tc = (p.threadConfig || {})['sandbox_workspace_write.writable_roots'] || [];
    const want = '$EXPECT_ROOT';
    console.log(JSON.stringify({ okSandbox: roots.includes(want), okThread: tc.includes(want) }));
  });
")"
echo "$CHECK" | grep -q '\"okSandbox\":true' || fail "-w: expected '$EXPECT_ROOT' in sandboxPolicy.writableRoots, got: $CHECK / policy: $POLICY"
echo "$CHECK" | grep -q '\"okThread\":true' || fail "-w: expected '$EXPECT_ROOT' in threadConfig[sandbox_workspace_write.writable_roots], got: $CHECK / policy: $POLICY"
echo "PASS: -w relative root resolves absolute in sandboxPolicy.writableRoots and threadConfig"

# --- --net sets sandboxPolicy.networkAccess AND the matching threadConfig key ---
POLICY2="$(node "$SCRIPT" --print-policy -C "$CWD_DIR" -s workspace-write --net)"
echo "$POLICY2" | grep -q '"networkAccess": true' || fail "--net: expected sandboxPolicy.networkAccess true, got: $POLICY2"
echo "$POLICY2" | grep -q '"sandbox_workspace_write.network_access": true' || fail "--net: expected threadConfig network_access true, got: $POLICY2"
echo "PASS: --net sets sandboxPolicy.networkAccess and threadConfig network_access"

# --- without -w or --net under workspace-write, threadConfig is null (no
#     override to send — nothing would vacuously pass here without a real
#     assertion, since a bug that always emits {} instead of null would
#     otherwise slip through undetected) ---
POLICY3="$(node "$SCRIPT" --print-policy -C "$CWD_DIR" -s workspace-write)"
echo "$POLICY3" | grep -q '"threadConfig": null' || fail "no -w/--net: expected threadConfig null, got: $POLICY3"
echo "PASS: threadConfig is null without -w or --net"

# --- -s none --print-policy: no sandboxPolicy, no threadConfig (nothing
#     else set), sandbox reported as "none" ---
POLICY_NONE="$(node "$SCRIPT" -s none --print-policy)"
echo "$POLICY_NONE" | grep -q '"sandbox": "none"' || fail "-s none: expected sandbox none, got: $POLICY_NONE"
echo "$POLICY_NONE" | grep -q '"sandboxPolicy": null' || fail "-s none: expected sandboxPolicy null, got: $POLICY_NONE"
echo "$POLICY_NONE" | grep -q '"threadConfig": null' || fail "-s none: expected threadConfig null, got: $POLICY_NONE"
echo "PASS: -s none --print-policy yields null sandboxPolicy and threadConfig"

# --- --preset github-only --print-policy: sandbox none (from $sandbox),
#     null sandboxPolicy, threadConfig carries default_permissions and the
#     domains map, and no $/_ pseudo-key leaked into the merged config ---
PRESET_POLICY="$(node "$SCRIPT" --preset github-only --print-policy)"
CHECK_PRESET="$(echo "$PRESET_POLICY" | node -e "
  let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{
    const p = JSON.parse(d);
    const tc = p.threadConfig || {};
    console.log(JSON.stringify({
      sandbox: p.sandbox,
      sandboxPolicy: p.sandboxPolicy,
      hasDefaultPermissions: tc.default_permissions === 'codex-run',
      hasDomains: !!(tc['permissions.codex-run.network.domains'] && tc['permissions.codex-run.network.domains']['github.com'] === 'allow'),
      noPseudoKeys: Object.keys(tc).every((k) => !k.startsWith('\$') && !k.startsWith('_')),
    }));
  });
")"
echo "$CHECK_PRESET" | grep -q '\"sandbox\":\"none\"' || fail "--preset github-only: expected sandbox none, got: $CHECK_PRESET / policy: $PRESET_POLICY"
echo "$CHECK_PRESET" | grep -q '\"sandboxPolicy\":null' || fail "--preset github-only: expected sandboxPolicy null, got: $CHECK_PRESET / policy: $PRESET_POLICY"
echo "$CHECK_PRESET" | grep -q '\"hasDefaultPermissions\":true' || fail "--preset github-only: expected default_permissions in threadConfig, got: $CHECK_PRESET / policy: $PRESET_POLICY"
echo "$CHECK_PRESET" | grep -q '\"hasDomains\":true' || fail "--preset github-only: expected github.com:allow in domains map, got: $CHECK_PRESET / policy: $PRESET_POLICY"
echo "$CHECK_PRESET" | grep -q '\"noPseudoKeys\":true' || fail "--preset github-only: expected no \$/_ keys in threadConfig, got: $CHECK_PRESET / policy: $PRESET_POLICY"
echo "PASS: --preset github-only --print-policy yields sandbox=none, null sandboxPolicy, merged threadConfig, no pseudo-keys"

# --- -c after --preset overrides a preset key (network.enabled: true in
#     the preset, flipped to false by -c) ---
OVERRIDE_POLICY="$(node "$SCRIPT" --preset github-only -c permissions.codex-run.network.enabled=false --print-policy)"
echo "$OVERRIDE_POLICY" | grep -q '"permissions.codex-run.network.enabled": false' || fail "-c after --preset: expected -c to win, got: $OVERRIDE_POLICY"
echo "PASS: -c override after --preset wins over the preset's value"

# --- --preset does-not-exist: rc 2, clear message ---
set +e
OUT="$(node "$SCRIPT" --preset does-not-exist --print-policy 2>&1)"
RC=$?
set -e
[ "$RC" -eq 2 ] || fail "--preset does-not-exist: expected rc 2, got $RC"
echo "$OUT" | grep -qi "preset not found" || fail "--preset does-not-exist: expected a clear not-found message, got: $OUT"
echo "PASS: --preset does-not-exist is rc 2 with a clear message"

echo "All codex-run offline tests passed."
