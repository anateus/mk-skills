# Lifecycle hooks

## Scope and trust

The bundled installer adds Claude Code and Codex lifecycle hooks for pane status (`working`, `idle`, `blocked`), stable identity, originating-pane tracking, and automatic live Hunk review after qualifying file changes. Inspect `scripts/install-hooks.sh` and the installed definitions before trusting them. Codex requires review through `/hooks` in the next interactive session.

## Install and remove

```bash
bash "<skill-base-dir>/scripts/install-hooks.sh" --all
bash "<skill-base-dir>/scripts/install-hooks.sh" --uninstall --all
```

Host-specific flags are available in the installer help. Installation is idempotent, backs up changed settings, and preserves unrelated hooks. Installed hook files are symlinks to the skill's scripts so skill updates cannot leave stale controller copies behind. Uninstall is ownership-scoped to entries installed by this skill.

## Behavior

Claude registers status for `UserPromptSubmit`, `Stop`, `Notification`, and `SessionEnd`; origin for `SessionStart`; and asynchronous autodiff for `PostToolUse` matching `Edit|Write|MultiEdit|NotebookEdit`. Codex registers status for `SessionStart`, `UserPromptSubmit`, `PermissionRequest`, `Stop`, and `SessionEnd`; origin for `SessionStart`; and synchronous autodiff for `PostToolUse` matching `apply_patch|Edit|Write`.

| Event | Status effect |
|---|---|
| `SessionStart` (Codex) | clear a stale status suffix |
| `UserPromptSubmit` | `working` |
| `PermissionRequest`, or Claude `Notification` with `notification_type: permission_prompt` | `blocked` |
| `Stop` | `idle` |
| `SessionEnd` | clear only the status suffix |

Other Claude notification types, including idle prompts and agent-completed notices, are ignored rather than mislabeled as blocked. Status and origin hooks also ignore subagent payloads; subagents do not create independent origin or status records.

Origin metadata keeps qualifying top-level edits attached to their originating work stream even if another pane is focused. Automatic review respects a manually dismissed unchanged stream and reopens after the diff changes.

After installation, restart the host, verify pane titles transition during a request, make a harmless file change, and confirm the review stream appears in an origin-named Reviews tab without changing the active tab.
