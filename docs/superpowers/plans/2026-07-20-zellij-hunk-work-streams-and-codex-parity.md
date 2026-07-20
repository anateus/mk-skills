# Zellij Hunk Work Streams and Codex Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep one current Hunk pane per logical work stream, place it to the right of its originating Zellij pane, and provide equivalent hooks, shared guidance, and shared Hindsight memory for Claude Code and Codex.

**Architecture:** A host-neutral Python controller owns watcher state and pane lifecycle; thin Claude/Codex shell hooks normalize lifecycle payloads into controller requests. Existing Zellij shell helpers call the same controller for worktree and aggregate watchers. Idempotent installers merge host-specific hook configuration, while a separate personal-setup script establishes shared guidance and the Hindsight Codex integration.

**Tech Stack:** Python 3 standard library, POSIX shell/Bash, Zellij 0.45 CLI, git, Hunk 0.17+, Claude Code JSON hooks, Codex `hooks.json`, shell-based hermetic tests.

## Global Constraints

- Support Zellij 0.45 and preserve the documented minimum of Zellij 0.44 unless a tested command requires raising it.
- Use a fixed branch-point SHA for every watched diff; never use moving `main` or current `HEAD` as the watcher base.
- Keep no more than one controller-managed Hunk pane per active logical work stream.
- Place a watcher immediately right of its recorded parent pane when an attached client and live parent make that safe; otherwise use a plain tiled fallback.
- Restore the previously focused pane after every focus-based placement attempt.
- Treat state under `~/.cache/zellij-agent-herder/` as advisory and verify panes from `list-panes -j` before reuse or closure.
- Codex hook commands must be synchronous because current Codex parses but skips `async` handlers.
- Preserve unrelated hook/config entries and back up user configuration before mutation.
- Never commit, print, or copy Hindsight credentials into this repository.
- Do not spawn implementation subagents unless the active execution workflow explicitly requires them.

---

## File Map

- Create `skills/zellij-agent-herder/scripts/hunk-stream.py`: stream identity, locking, diff signatures, state persistence, Hunk pane reuse/replacement, dismissal, roll-up, and parent-right placement.
- Create `skills/zellij-agent-herder/scripts/zellij-origin.sh`: top-level session hook that records the stable origin pane for Claude and Codex payloads.
- Modify `skills/zellij-agent-herder/scripts/hunk-autodiff.sh`: reduce it to a payload adapter that calls `hunk-stream.py edit`.
- Modify `skills/zellij-agent-herder/scripts/zellij-agent-status.sh`: normalize Claude and Codex lifecycle events into the shared pane-title states.
- Modify `skills/zellij-agent-herder/scripts/zj.sh`: route worktree/session watcher helpers through the controller and add an explicit-review helper.
- Modify `skills/zellij-agent-herder/scripts/install-hooks.sh`: add `--claude`, `--codex`, and `--all`; install origin, status, and Hunk hooks with ownership-safe JSON merging.
- Create `skills/zellij-agent-herder/scripts/setup-shared-agent-config.sh`: create shared guidance, Claude import, Codex symlink, and configure Hindsight's existing Codex integration.
- Create `skills/zellij-agent-herder/tests/test-hunk-stream.sh`: hermetic controller and payload tests with fake git/Hunk/Zellij processes.
- Create `skills/zellij-agent-herder/tests/test-install-hooks.sh`: hermetic Claude/Codex config merge and uninstall tests.
- Create `skills/zellij-agent-herder/tests/test-shared-agent-config.sh`: hermetic guidance, symlink, and Hindsight-bank tests.
- Modify `skills/zellij-agent-herder/SKILL.md`, `skills/zellij-agent-herder/references/hooks.md`, `skills/zellij-agent-herder/references/pitfalls.md`, and `README.md`: document stream semantics, origin placement, host-specific installation, Hindsight, and recovery.

---

### Task 1: Stream Identity, State, and Diff Signatures

**Files:**
- Create: `skills/zellij-agent-herder/scripts/hunk-stream.py`
- Create: `skills/zellij-agent-herder/tests/test-hunk-stream.sh`

**Interfaces:**
- Produces CLI: `hunk-stream.py signature --root ROOT --base SHA`
- Produces CLI: `hunk-stream.py state-key --session SESSION --parent PANE --root ROOT --kind KIND`
- Produces Python functions: `git_common_dir(root) -> str`, `diff_signature(root, base) -> str`, `stream_key(session, parent, common_dir, identity) -> str`, `locked_state(cache_dir, key)`.
- State JSON fields: `version`, `key`, `generation`, `session`, `parent_pane`, `pane_id`, `root`, `common_dir`, `base`, `kind`, `signature`, `dismissed_signature`.

- [ ] **Step 1: Write the failing identity and signature tests**

Create the test harness with a temporary `HOME`, repository, initial commit, untracked file, and these assertions:

```bash
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: FAIL because `hunk-stream.py` does not exist.

- [ ] **Step 3: Implement the minimal controller foundation**

Implement an `argparse` CLI, canonical paths, `git rev-parse --git-common-dir`, and a SHA-256 signature over:

```python
payload = {
    "base": base,
    "tracked": run_git(root, ["diff", "--binary", "--no-ext-diff", base, "--"]),
    "untracked": [
        {"path": path, "sha256": sha256_file(os.path.join(root, path))}
        for path in sorted(nul_git_paths(root, ["ls-files", "--others", "--exclude-standard", "-z"]))
    ],
}
```

Derive the stream key from canonical JSON containing session, normalized parent ID, canonical common directory, root identity, and kind. Store state beneath `${XDG_CACHE_HOME:-~/.cache}/zellij-agent-herder/streams/`. Use `fcntl.flock` on `<key>.lock`, write JSON to a same-directory temporary file, `fsync`, then `os.replace`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: `identity/signature: PASS`.

- [ ] **Step 5: Commit**

```bash
git add skills/zellij-agent-herder/scripts/hunk-stream.py skills/zellij-agent-herder/tests/test-hunk-stream.sh
git commit -m "feat(zah): add hunk work-stream state foundation"
```

---

### Task 2: Pane Reconciliation and Parent-Right Placement

**Files:**
- Modify: `skills/zellij-agent-herder/scripts/hunk-stream.py`
- Modify: `skills/zellij-agent-herder/tests/test-hunk-stream.sh`

**Interfaces:**
- Consumes state and signature interfaces from Task 1.
- Produces CLI: `hunk-stream.py ensure --session SESSION --parent PANE --root ROOT --base SHA --kind worktree|aggregate [--label LABEL] [--explicit]` and prints the verified pane ID.
- Produces CLI: `hunk-stream.py rollup --session SESSION --parent PANE --root ROOT --base SHA --label LABEL --child-pane ID...` and prints the aggregate pane ID.

- [ ] **Step 1: Add failing fake-Zellij lifecycle tests**

Extend the test harness with a fake `zellij` executable that logs actions and maintains JSON panes/clients. Assert:

```bash
P1="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
P2="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
[ "$P1" = "$P2" ]
[ "$(grep -c 'new-pane' "$ZELLIJ_LOG")" = 1 ]
grep -q 'focus-pane-id terminal_1' "$ZELLIJ_LOG"
grep -q 'new-pane --direction right' "$ZELLIJ_LOG"
grep -q 'focus-pane-id terminal_9' "$ZELLIJ_LOG"
```

Delete the fake watcher pane without changing the diff and call `ensure` without `--explicit`; assert no second `new-pane`. Change `a.txt`; assert it reopens. Call `ensure --explicit`; assert it reopens even when the signature is unchanged. Create two child panes, call `rollup`, and assert both recorded children close and exactly one aggregate pane opens with the original base.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: FAIL because `ensure` and `rollup` are not defined.

- [ ] **Step 3: Implement reconciliation and spawning**

Implement these rules under the per-stream lock:

```python
if state_pane_exists(state) and same_request(state, request):
    return state["pane_id"]
if state and not state_pane_exists(state):
    if state.get("signature") == signature and not explicit:
        state["dismissed_signature"] = signature
        save_state(state)
        return ""
if state.get("dismissed_signature") == signature and not explicit:
    return ""
close_owned_pane_if_present(state)
pane_id = spawn_hunk(request)
verify_pane(pane_id)
save_state(new_state)
return pane_id
```

For placement, parse `list-clients` into `(client_id, focused_pane)` rows. With exactly one attached client and a live parent: focus the parent, call `new-pane --direction right --cwd ROOT --name NAME -- hunk diff BASE --watch`, and restore the old focus in `finally`. Otherwise omit direction/focus arguments and use plain tiled `new-pane`. Verify the returned ID in `list-panes -j`; if verification fails, recover by unique generated pane title. Quote command arguments as an argv list, never interpolated shell.

For `rollup`, close only child IDs that exist in controller state or are explicitly supplied by the existing helper contract, mark child state complete, and call `ensure(kind="aggregate", explicit=True)` with the same base.

- [ ] **Step 4: Run controller tests**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: all identity, dedup, dismissal, focus restoration, fallback, and roll-up assertions print `PASS`.

- [ ] **Step 5: Run a real scratch-session placement check**

Run the test's documented `LIVE_ZELLIJ=1` branch, which creates a uniquely named scratch session, two sleeping panes, calls `ensure`, inspects `list-panes -j` geometry, and kills only that scratch session.

Expected: watcher geometry begins at the parent's right edge and the originally focused pane remains focused.

- [ ] **Step 6: Commit**

```bash
git add skills/zellij-agent-herder/scripts/hunk-stream.py skills/zellij-agent-herder/tests/test-hunk-stream.sh
git commit -m "feat(zah): reconcile and place hunk stream panes"
```

---

### Task 3: Origin Capture and Hook Adapters

**Files:**
- Create: `skills/zellij-agent-herder/scripts/zellij-origin.sh`
- Modify: `skills/zellij-agent-herder/scripts/hunk-autodiff.sh`
- Modify: `skills/zellij-agent-herder/scripts/zellij-agent-status.sh`
- Modify: `skills/zellij-agent-herder/tests/test-hunk-stream.sh`

**Interfaces:**
- Produces origin file: `${XDG_CACHE_HOME:-~/.cache}/zellij-agent-herder/origins/<host>-<session_id>.json` with `host`, `session_id`, `zellij_session`, and normalized `parent_pane`.
- `hunk-autodiff.sh` consumes Claude or Codex JSON on stdin and invokes `hunk-stream.py ensure`.

- [ ] **Step 1: Add failing Claude/Codex payload tests**

Add fixtures for Claude `SessionStart`/`PostToolUse` and Codex `SessionStart`/`PostToolUse`. Use `ZELLIJ_PANE_ID=terminal_1`, then change the environment to `terminal_7` before the edit hook and assert the controller request still uses `terminal_1`. Assert payloads with Claude `agent_id` or Codex subagent context do not overwrite the top-level origin. Assert `apply_patch`, `Edit`, and `Write` trigger while irrelevant read tools do not.

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: FAIL because no origin adapter exists and autodiff still skips/opens directly.

- [ ] **Step 3: Implement origin capture**

`zellij-origin.sh` reads stdin once, detects the host from Codex-only `model`/`turn_id` fields or an explicit `ZAH_HOST`, ignores subagent start payloads, normalizes numeric IDs to `terminal_N`, and atomically writes the origin JSON keyed by host and lifecycle `session_id`. It exits successfully outside Zellij or for malformed payloads.

- [ ] **Step 4: Replace autodiff spawning with controller invocation**

Keep repository/root discovery in one place by passing the payload to a new controller `edit` subcommand. `edit` extracts `tool_input.file_path` for Claude and Codex, resolves the origin record, chooses a fixed base once per stream with `git merge-base HEAD @{upstream}` when available and otherwise the stream's initial `HEAD`, then delegates to `ensure`. Do not pass `async` assumptions into the script.

- [ ] **Step 5: Normalize status events for both hosts**

Preserve Claude's existing mapping. Add Codex mappings: `UserPromptSubmit` sets `working`, `PermissionRequest` sets `blocked`, and `Stop` sets `idle`. Codex currently has no `SessionEnd` hook, so a later `SessionStart` first strips a stale status suffix before origin capture. Continue ignoring subagent payloads so they cannot stamp the parent independently.

- [ ] **Step 6: Run payload and controller tests**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: all payloads use the captured parent; subagents do not replace it; edit matchers behave as asserted.

- [ ] **Step 7: Commit**

```bash
git add skills/zellij-agent-herder/scripts/zellij-origin.sh skills/zellij-agent-herder/scripts/hunk-autodiff.sh skills/zellij-agent-herder/scripts/zellij-agent-status.sh skills/zellij-agent-herder/scripts/hunk-stream.py skills/zellij-agent-herder/tests/test-hunk-stream.sh
git commit -m "feat(zah): preserve origin panes across agent hooks"
```

---

### Task 4: Route Worktree, Roll-Up, and Explicit Review Helpers

**Files:**
- Modify: `skills/zellij-agent-herder/scripts/zj.sh`
- Modify: `skills/zellij-agent-herder/tests/test-hunk-stream.sh`

**Interfaces:**
- Preserves: `zj_watch_worktree ROOT BASE [LABEL] -> pane_id`.
- Preserves: `zj_watch_session ROOT BASE LABEL [child_pane_id...] -> pane_id`.
- Produces: `zj_review_stream ROOT BASE [LABEL] -> pane_id`, setting explicit reopen behavior.

- [ ] **Step 1: Add failing shell-helper tests**

Source `zj.sh` against the fake Zellij environment. Assert `zj_watch_worktree` invokes controller `ensure`, `zj_watch_session` invokes `rollup`, and `zj_review_stream` invokes `ensure --explicit`. Assert repeated helper use does not duplicate panes and roll-up closes child panes.

- [ ] **Step 2: Run tests to verify failure**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: FAIL because helpers still spawn directly and `zj_review_stream` is undefined.

- [ ] **Step 3: Implement thin helper wrappers**

Resolve `hunk-stream.py` relative to `zj.sh`. Pass `ZJ_SESSION`, the captured origin pane when present, canonical roots, bases, labels, and child IDs as separate arguments. Preserve existing return codes: missing Hunk returns `2`, failed/absent spawn returns `1`, success prints only the pane ID.

- [ ] **Step 4: Run tests**

Run: `bash skills/zellij-agent-herder/tests/test-hunk-stream.sh`

Expected: helper assertions pass with one pane per stream.

- [ ] **Step 5: Commit**

```bash
git add skills/zellij-agent-herder/scripts/zj.sh skills/zellij-agent-herder/tests/test-hunk-stream.sh
git commit -m "refactor(zah): unify worktree and review watchers"
```

---

### Task 5: Dual-Host Hook Installer

**Files:**
- Modify: `skills/zellij-agent-herder/scripts/install-hooks.sh`
- Create: `skills/zellij-agent-herder/tests/test-install-hooks.sh`

**Interfaces:**
- Produces: `install-hooks.sh --claude|--codex|--all` (default `--all`).
- Produces: `install-hooks.sh --uninstall --claude|--codex|--all`.
- Claude destination: `${CLAUDE_CONFIG_DIR:-~/.claude}/hooks/` and `settings.json`.
- Codex destination: `${CODEX_CONFIG_DIR:-~/.codex}/hooks/` and `hooks.json`.

- [ ] **Step 1: Write failing idempotent merge tests**

Create temporary Claude/Codex config roots containing unrelated hook entries. Run `--all` twice and assert:

```bash
python3 - "$CLAUDE/settings.json" "$CODEX/hooks.json" <<'PY'
import json, sys
c, x = map(lambda p: json.load(open(p)), sys.argv[1:])
assert sum("zellij-origin.sh" in h.get("command", "") for g in c["hooks"]["SessionStart"] for h in g["hooks"]) == 1
assert sum("hunk-autodiff.sh" in h.get("command", "") for g in x["hooks"]["PostToolUse"] for h in g["hooks"]) == 1
assert all("async" not in h for g in x["hooks"]["PostToolUse"] for h in g["hooks"])
assert any("unrelated" in h.get("command", "") for g in x["hooks"]["Stop"] for h in g["hooks"])
PY
```

Run uninstall and assert only owned entries/files disappear. Assert backups exist before every changed configuration. Assert Codex matchers cover `apply_patch|Edit|Write`.

- [ ] **Step 2: Run tests to verify failure**

Run: `bash skills/zellij-agent-herder/tests/test-install-hooks.sh`

Expected: FAIL because the installer has no host flags or Codex support.

- [ ] **Step 3: Implement host-specific merge/unmerge operations**

Keep shell responsible for argument parsing, copying executable scripts, and backups. Use embedded Python for structural JSON merging. Identify owned hook handlers by exact installed script basename and destination prefix. Claude installs its existing `UserPromptSubmit`, `Stop`, `Notification`, and `SessionEnd` status events plus `SessionStart` origin and edit autodiff with `async: true`. Codex installs `UserPromptSubmit`, `PermissionRequest`, and `Stop` status events, `SessionStart` origin/reset, and synchronous `PostToolUse` autodiff. Print a final Codex note: `Run /hooks and trust the new or changed zellij-agent-herder definitions.`

- [ ] **Step 4: Run installer tests**

Run: `bash skills/zellij-agent-herder/tests/test-install-hooks.sh`

Expected: `Claude install: PASS`, `Codex install: PASS`, `uninstall preservation: PASS`.

- [ ] **Step 5: Commit**

```bash
git add skills/zellij-agent-herder/scripts/install-hooks.sh skills/zellij-agent-herder/tests/test-install-hooks.sh
git commit -m "feat(zah): install native Claude and Codex hooks"
```

---

### Task 6: Shared Guidance and Hindsight Setup

**Files:**
- Create: `skills/zellij-agent-herder/scripts/setup-shared-agent-config.sh`
- Create: `skills/zellij-agent-herder/tests/test-shared-agent-config.sh`

**Interfaces:**
- Produces: `setup-shared-agent-config.sh [--agents-dir DIR] [--claude-dir DIR] [--codex-dir DIR] [--hindsight-dir DIR]`.
- Canonical guidance: `~/.agents/AGENTS.md`.
- Codex link: `~/.codex/AGENTS.md -> ~/.agents/AGENTS.md`.
- Claude overlay: `~/.claude/CLAUDE.md` imports the canonical file and retains Claude-only instructions.
- Hindsight override: `~/.hindsight/codex.json` with `bankId: "claude_code"` and `dynamicBankId: false`.

- [ ] **Step 1: Write failing personal-setup tests**

Use four temporary config roots. Seed a Claude file containing the four current `<important if>` blocks and a fake Hindsight Codex integration source. Assert the setup:

- creates canonical guidance with verification, shared Hindsight, and work-stream Hunk-review rules;
- leaves model delegation only in Claude's overlay;
- inserts exactly one Claude import line for the canonical file;
- creates the Codex symlink without replacing an unrelated real file unless it first backs it up;
- installs/merges Hindsight's `SessionStart`, `UserPromptSubmit`, and `Stop` hooks without removing Zellij or unrelated hooks;
- writes `bankId: "claude_code"` and `dynamicBankId: false`; and
- never writes a fixture token into repository files or stdout.

- [ ] **Step 2: Run tests to verify failure**

Run: `bash skills/zellij-agent-herder/tests/test-shared-agent-config.sh`

Expected: FAIL because the setup script does not exist.

- [ ] **Step 3: Implement shared guidance setup**

Write the three portable `<important if>` blocks to `AGENTS.md` in host-neutral language. Use Claude Code's supported `@/absolute/path/to/AGENTS.md` import syntax at the top of `CLAUDE.md`; preserve the Claude-only model-delegation block below it. Back up any changed real file with a timestamp suffix. Create the Codex symlink only after validating its target.

- [ ] **Step 4: Implement Hindsight Codex setup**

Prefer an already installed official Hindsight Codex integration under `~/.hindsight/codex/`. If missing, invoke the official installer in an explicit `--install-hindsight` path rather than silently downloading during ordinary setup. Merge its hook definitions structurally into Codex `hooks.json`, then merge only `bankId` and `dynamicBankId` into `~/.hindsight/codex.json`. Reuse existing endpoint/token fields in place and redact token values from diagnostics.

- [ ] **Step 5: Run setup tests**

Run: `bash skills/zellij-agent-herder/tests/test-shared-agent-config.sh`

Expected: `shared guidance: PASS`, `Claude overlay: PASS`, `Codex symlink: PASS`, `shared Hindsight bank: PASS`.

- [ ] **Step 6: Commit**

```bash
git add skills/zellij-agent-herder/scripts/setup-shared-agent-config.sh skills/zellij-agent-herder/tests/test-shared-agent-config.sh
git commit -m "feat(zah): share agent guidance and Hindsight memory"
```

---

### Task 7: Documentation and Installed-Configuration Migration

**Files:**
- Modify: `skills/zellij-agent-herder/SKILL.md`
- Modify: `skills/zellij-agent-herder/references/hooks.md`
- Modify: `skills/zellij-agent-herder/references/pitfalls.md`
- Modify: `README.md`
- Runtime changes: `~/.agents/AGENTS.md`, `~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.codex/hooks.json`, `~/.hindsight/codex.json`, and installed hook scripts.

**Interfaces:**
- Documents the exact Task 4–6 commands and recovery behavior.
- Applies the tested installers to the user's real configuration without committing personal files.

- [ ] **Step 1: Update skill and reference documentation**

Document:

- the `(session, origin pane, git identity)` stream model;
- fixed bases and worktree-to-aggregate roll-up;
- `zj_review_stream` for explicit completion review;
- focus/split-right/restore behavior and headless fallback;
- `install-hooks.sh --all` and ownership-scoped uninstall;
- Codex hook trust via `/hooks`;
- shared guidance and Hindsight setup; and
- stale state/manual dismissal troubleshooting.

Remove statements that automatic Hunk panes are always plain tiled or that subagents can never contribute to a parent stream.

- [ ] **Step 2: Run all automated tests**

Run:

```bash
bash skills/zellij-agent-herder/tests/test-hunk-stream.sh
bash skills/zellij-agent-herder/tests/test-install-hooks.sh
bash skills/zellij-agent-herder/tests/test-shared-agent-config.sh
git diff --check
```

Expected: all test suites print `PASS`; `git diff --check` is silent.

- [ ] **Step 3: Install hooks into the real Claude and Codex configuration**

Run:

```bash
bash skills/zellij-agent-herder/scripts/install-hooks.sh --all
```

Expected: both configurations are backed up and updated; the script asks for Codex hook trust review without exposing secrets.

- [ ] **Step 4: Apply shared guidance and Hindsight configuration**

Run:

```bash
bash skills/zellij-agent-herder/scripts/setup-shared-agent-config.sh
```

If the official Codex Hindsight scripts are not already installed, run the script's explicit `--install-hindsight` flow, inspect the downloaded installer source or checksum prompt it presents, and rerun ordinary setup.

Expected: `readlink ~/.codex/AGENTS.md` resolves to `~/.agents/AGENTS.md`; Claude imports the same file; `~/.hindsight/codex.json` selects `claude_code`; existing credentials remain redacted and unchanged.

- [ ] **Step 5: Verify active host configuration**

Run:

```bash
python3 -m json.tool ~/.claude/settings.json >/dev/null
python3 -m json.tool ~/.codex/hooks.json >/dev/null
python3 -m json.tool ~/.hindsight/codex.json >/dev/null
test "$(python3 -c 'import json,os; print(json.load(open(os.path.expanduser("~/.hindsight/codex.json")))["bankId"])')" = claude_code
```

Expected: all commands exit `0`. In the next Codex interactive session, use `/hooks` to trust the new definitions and confirm Hindsight recall plus Zellij origin hooks are listed.

- [ ] **Step 6: Commit documentation**

```bash
git add README.md skills/zellij-agent-herder/SKILL.md skills/zellij-agent-herder/references/hooks.md skills/zellij-agent-herder/references/pitfalls.md
git commit -m "docs(zah): document work streams and Codex parity"
```

---

### Task 8: End-to-End Verification

**Files:**
- Modify only if verification exposes a defect: files and tests from Tasks 1–7.

**Interfaces:**
- Verifies the complete behavior; introduces no new interface.

- [ ] **Step 1: Run the complete automated suite from a clean shell**

```bash
env -u ZELLIJ bash skills/zellij-agent-herder/tests/test-hunk-stream.sh
bash skills/zellij-agent-herder/tests/test-install-hooks.sh
bash skills/zellij-agent-herder/tests/test-shared-agent-config.sh
git diff --check
```

Expected: every suite passes and no whitespace errors are reported.

- [ ] **Step 2: Verify a live mid-development stream**

In a uniquely named scratch Zellij session, start an agent-like sleeping parent pane, record it with `zellij-origin.sh`, edit a scratch repository, and feed a representative Codex `PostToolUse` payload to `hunk-autodiff.sh`.

Expected: exactly one Hunk pane appears immediately right of the parent; the previously focused pane is restored; a second identical hook does not open another pane.

- [ ] **Step 3: Verify commit and roll-up behavior**

Commit the scratch change, create two scratch worktrees from one fixed SHA, call `zj_watch_worktree` for each, merge both into the parent, then call `zj_watch_session` with the child pane IDs.

Expected: the child panes close, one aggregate pane remains, and its Hunk diff shows both merged changes relative to the original fixed SHA.

- [ ] **Step 4: Verify dismissal and explicit reopen**

Close the aggregate pane, repeat the unchanged automatic request, then call `zj_review_stream` explicitly.

Expected: automatic request respects dismissal; explicit review opens one replacement beside the parent.

- [ ] **Step 5: Inspect repository and personal-config diffs**

Run `git status --short`, `git log --oneline --decorate -10`, and redacted structural summaries of the three JSON configs. Confirm no personal config, credential, cache state, or scratch artifact is tracked.

- [ ] **Step 6: Commit any verification-only fixes**

If verification required code changes, rerun the failing test first, implement the minimal correction, rerun the full suite, and commit only the affected repository files with `fix(zah): <specific verified defect>`. If no defect was found, do not create an empty commit.
