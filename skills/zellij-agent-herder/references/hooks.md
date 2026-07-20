# Hooks

Two independent hook regimes, installed by separate scripts — install either, both, or neither:

- **Activation hook** (`references/hooks/install-hook.sh`) — a *discovery* aid: a `SessionStart` hook that tells Claude it's inside zellij so this skill triggers reliably. See "Activation hook" below.
- **Status + hunk-autodiff hooks** (`scripts/install-hooks.sh`) — *operational* aids: live pane-title status and an auto diff pane on file changes. See "Status + hunk-autodiff" below.

---

## Activation hook (`references/hooks/install-hook.sh`)

A `SessionStart` hook (`zellij-activation.sh`) that, when a session starts **inside** zellij, prints the session/pane into Claude's context (for `SessionStart`, plain stdout is added as context — no jq/python needed). That makes the `zellij-agent-herder` skill's trigger match reliably instead of depending on Claude happening to check `$ZELLIJ`.

```
bash "<skill-base-dir>/references/hooks/install-hook.sh"     # install (idempotent)
bash "<skill-base-dir>/references/hooks/uninstall-hook.sh"   # remove
```

Install: copies `zellij-activation.sh` into `~/.claude/hooks/`, backs up `~/.claude/settings.json`, and **appends** a `SessionStart` entry without clobbering existing ones (e.g. herdr's). Re-running is a no-op. Take effect on the **next** session.

The hook no-ops silently outside zellij (`$ZELLIJ` unset) — presence, not truthiness, so `0` still counts as inside. Uninstall removes only this hook's entry and file; other `SessionStart` hooks are left intact.

---

## Status + hunk-autodiff (`scripts/install-hooks.sh`)

Shared Claude Code and Codex lifecycle hooks installed by one script. They give a top-level agent running in a zellij pane a live status in its pane title, remember its originating pane, and associate edits with a persistent Hunk review stream.

## Install

```
bash "<skill-base-dir>/scripts/install-hooks.sh" --all
```

`--all` is the default; use `--claude` or `--codex` to target one host. The idempotent installer copies `zellij-agent-status.sh`, `pane-identity.py`, `zellij-origin.sh`, and `hunk-autodiff.sh` into each host's `hooks/` directory, backs up a changed `~/.claude/settings.json` or `~/.codex/hooks.json` as `.bak.<timestamp>.<pid>`, and replaces only entries owned by these installed script paths. Existing hook groups and commands are preserved.

Claude registers status on `UserPromptSubmit`, `Stop`, `Notification`, and `SessionEnd`; origin on `SessionStart`; and async autodiff on `PostToolUse` matching `Edit|Write|MultiEdit|NotebookEdit`. Codex registers status on `SessionStart`, `UserPromptSubmit`, `PermissionRequest`, and `Stop`; origin on `SessionStart`; and synchronous autodiff on `PostToolUse` matching `apply_patch|Edit|Write`.

After installing Codex hooks, open `/hooks` in the **next Codex interactive session** and trust the new or changed definitions. Do not assume a hook is trusted merely because it is present in `hooks.json`.

## Status hook (`zellij-agent-status.sh`)

Assigns a stable identity on first observation, then stamps `"<breadcrumb> · <status>"` into the current pane's title. Roots render as `"<display-label> (<emoji> <full-name>) · <status>"`, preferring a useful existing pane base and otherwise the repository/cwd name. A useful native session name is preferred for identity; generic `agent`/`claude`/`codex`/`yolo`, spinner-prefixed, cwd, and repository identity names receive a persisted curated emoji plus adjective-noun fallback. Parent ancestry previously assigned by the peer wrapper remains intact.

Identity metadata is the source of truth at `${XDG_CACHE_HOME:-$HOME/.cache}/zellij-agent-herder/panes/<session>/<pane>.json`. The hook never reconstructs lineage from a rendered title. Plain panes not observed by this hook and not created through `zellij-peer.sh` remain unaffected.

| Event | Status |
|---|---|
| `UserPromptSubmit` | `working` |
| `Notification` (`notification_type: permission_prompt` only) | `blocked` |
| `Stop` | `idle` |
| `SessionEnd` | *(cleared — title reverts to just `<base>`, no suffix)* |

`Notification` fires for several distinct subtypes — `permission_prompt`, `idle_prompt` (a "you've been idle" nudge, not actually blocked), `agent_completed`, etc. Only `permission_prompt` maps to `blocked`; other `Notification` subtypes are ignored so an agent that's simply idle doesn't get mislabeled as blocked.

`SessionEnd` fires whenever the Claude Code process actually exits (`/exit`, Ctrl+D, `/clear`, logout, etc.) — without it, the last stamped status (e.g. `blocked`) stays stuck in the pane title forever after the agent is gone, since none of the other three events fire on exit. The hook strips only the `" · <status>"` suffix and retains the cached breadcrumb.

No-ops when: run outside zellij (`ZELLIJ_PANE_ID` unset), `zellij`/`python3` absent, the hook JSON carries an `agent_id` (a **subagent** — never stamp its parent's pane), the event is `SubagentStop` (never revive idle), or a `Notification` whose `notification_type` isn't `permission_prompt`. The separator is exactly `" · "` (space, U+00B7, space), byte-identical to what `zj_resolve_id`/`zj_wait_status` split on. `zj_wait_status` reads it back.

## Origin and hunk-autodiff hooks

`zellij-origin.sh` records the first top-level `SessionStart` origin as `(host session id, Zellij session, origin pane)`. `hunk-autodiff.sh` normalizes the host's `PostToolUse` payload and routes qualifying edits into a stream identified by **(Zellij session, origin pane, git common directory, worktree root/kind)**. A subagent does not overwrite the origin or stamp parent status, but edits surfaced through the parent lifecycle can contribute to that parent stream.

The first stream request chooses a fixed base (upstream merge-base when available, otherwise `HEAD`) and retains it as the stream changes. `zj_watch_worktree` accepts an explicit fixed branch point; `zj_watch_session` rolls completed worktree panes into one parent-tree aggregate against that same base. Automatic requests reuse a live matching pane. If the human closes a pane while its signature is unchanged, automatic requests record and respect that dismissal; `zj_review_stream` explicitly reopens it for completion review.

With exactly one attached client and a valid origin pane, the controller briefly focuses the origin, opens the Hunk pane split-right, and restores the client's former focus. Headless, multi-client, or missing-origin cases use a plain tiled pane. Every spawn is reconciled against `list-panes` rather than trusting `new-pane` output alone.

## Driving a live session

Once a `hunk diff --watch` pane is open, run `hunk skill path` and read the returned **`hunk-review`** skill completely before inspecting or annotating the session. This keeps the workflow aligned with the installed Hunk version; it currently uses commands such as `hunk session review --repo <root> --json` and `hunk session comment ...`.

Review pane titles inherit the originating pane's emoji lineage and append `🔍`, using ` ▸ ` as the compact descent marker (for example, `🦀 ▸ 🌿 ▸ 🔍`). If the parent has no cached identity, the title is simply `🔍`.

## Uninstall

Use the ownership-scoped uninstaller rather than deleting hook groups by hand:

```
bash "<skill-base-dir>/scripts/install-hooks.sh" --uninstall --all
```

Use `--claude` or `--codex` for one host. It backs up changed configuration, removes the three installed scripts, and removes only hook entries whose command resolves to those scripts in that host's hooks directory; unrelated entries, empty groups, and other hooks remain intact.

## Shared guidance and Hindsight

`bash "<skill-base-dir>/scripts/setup-shared-agent-config.sh"` creates canonical shared guidance at `~/.agents/AGENTS.md`, imports it from `~/.claude/CLAUDE.md`, symlinks `~/.codex/AGENTS.md` to it, merges already-installed official Hindsight Codex hooks into `~/.codex/hooks.json`, and sets `~/.hindsight/codex.json` to `{"bankId":"claude_code","dynamicBankId":false}` while preserving other fields such as credentials. Changed files are backed up.

Ordinary setup never downloads Hindsight. If `~/.hindsight/codex/hooks.json` is absent but an official integration is already available in a trusted local checkout, use:

```
bash "<skill-base-dir>/scripts/setup-shared-agent-config.sh" --hindsight-source <official-codex-integration-dir>
```

The local source must be a regular, non-symlink directory containing regular `hooks/hooks.json`, `settings.json`, and `scripts/` content with `SessionStart`, `UserPromptSubmit`, and `Stop` hook groups. The installer rejects symlinks and malformed JSON/structure before mutation, copies scripts and settings through a temporary directory without downloading, substitutes `__SCRIPTS_DIR__` with the final installed path, and atomically replaces changed `~/.hindsight/codex` content after backing up an existing installation.

Alternatively, use the explicit `--install-hindsight` flow only when the `hindsight codex install --directory` interface is available and verified, then rerun ordinary setup. Review and trust the merged Codex definitions with `/hooks` in the next interactive session.
