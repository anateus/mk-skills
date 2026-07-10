# Hook regime — status + hunk-autodiff

Two Claude Code lifecycle hooks, both installed by one script. They give an agent running in a zellij pane a live status in its pane title and an automatic diff pane when it starts changing files.

## Install

```
bash "<skill-base-dir>/scripts/install-hooks.sh"
```

Idempotent and safe to re-run. It:
1. Copies `zellij-agent-status.sh` and `hunk-autodiff.sh` into `~/.claude/hooks/` (chmod +x).
2. Backs up `~/.claude/settings.json` (`.bak.<timestamp>`).
3. Registers, without clobbering existing hooks (e.g. herdr's `SessionStart`):
   - `UserPromptSubmit`, `Stop`, `Notification` → `zellij-agent-status.sh`
   - `PostToolUse` (matcher `Edit|Write|MultiEdit|NotebookEdit`, `"async": true`) → `hunk-autodiff.sh`

## Status hook (`zellij-agent-status.sh`)

Stamps `"<base> · <status>"` into the current pane's title:

| Event | Status |
|---|---|
| `UserPromptSubmit` | `working` |
| `Notification` | `blocked` |
| `Stop` | `idle` |

No-ops when: run outside zellij (`ZELLIJ_PANE_ID` unset), `zellij`/`python3` absent, the hook JSON carries an `agent_id` (a **subagent** — never stamp its parent's pane), or the event is `SubagentStop` (never revive idle). The separator is `" · "` (space, U+00B7, space), byte-identical to what `zj_resolve_id`/`zj_wait_status` split on. `zj_wait_status` reads it back.

## hunk-autodiff hook (`hunk-autodiff.sh`)

On the agent's **first file change in a worktree this turn**, opens `hunk diff --watch` beside the agent pane (adaptive spawn — beside when attached, plain when headless).

Skips when: outside zellij; subagent (`agent_id`); not a git repo; clean tree; a live hunk session already tracks the repo (`hunk session get --repo <root>` exits 0); or a per-`(root, prompt_id)` dedup marker under `~/.cache/zellij-agent-herder/` already fired this turn (written **before** opening, so a retry within the turn won't double-open).

**Known limitation:** `hunk diff --watch` runs under a local daemon whose session can **outlive its zellij pane**. If a human closes the diff pane, `hunk session get` may still report the session live, so the hook won't reopen the diff on the next change that turn. Kill the stray watcher (or start a fresh turn) to reset.

## Toggles

- **When it fires.** Default is first-change (`PostToolUse`). To fire at turn-end instead, move the `hunk-autodiff.sh` registration from `PostToolUse` to `Stop` in `~/.claude/settings.json` (and drop the matcher).
- **Dedup strategy.** This port dedups per `(root, prompt_id)` (one open attempt per turn per repo). The original `hunk.autodiff` plugin instead tracked a diff signature to "stay closed" once dismissed — swap that in if you prefer dismissal to survive across turns.

## Driving a live session

Once a `hunk diff --watch` pane is open, an agent can inspect/annotate it via the **`hunk-review`** skill (`hunk session review --repo <root> --json`, `hunk session comment ...`).

## Uninstall

Remove the two files `~/.claude/hooks/zellij-agent-status.sh` and `~/.claude/hooks/hunk-autodiff.sh`, and delete their entries from `~/.claude/settings.json` (the `UserPromptSubmit`/`Stop`/`Notification` status entries and the `PostToolUse` hunk entry). A settings backup from install time sits alongside as `settings.json.bak.<timestamp>`.
