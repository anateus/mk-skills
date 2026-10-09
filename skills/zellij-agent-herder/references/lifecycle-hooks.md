# Lifecycle hooks

## Scope and trust

The bundled installer adds Claude Code and Codex lifecycle hooks for pane status (`working`, `idle`, `blocked`), stable identity, and originating-pane tracking. It does not install a review hook: Hunk review streams are opened on demand through the helper API. Inspect `scripts/install-hooks.sh` and the installed definitions before trusting them. Codex requires review through `/hooks` in the next interactive session.

## Install and remove

```bash
bash "<skill-base-dir>/scripts/install-hooks.sh" --all
bash "<skill-base-dir>/scripts/install-hooks.sh" --uninstall --all
```

Host-specific flags are available in the installer help. Installation is idempotent, backs up changed settings, and preserves unrelated hooks. Installed hook files are symlinks to the skill's scripts so skill updates cannot leave stale controller copies behind. Uninstall is ownership-scoped to entries installed by this skill.

## Behavior

Claude registers status for `UserPromptSubmit`, `Stop`, `Notification`, and `SessionEnd`, and origin for `SessionStart`. Codex registers status for `SessionStart`, `UserPromptSubmit`, `PermissionRequest`, `Stop`, and `SessionEnd`, and origin for `SessionStart`. No host registers a `PostToolUse` edit hook; a leftover `hunk-autodiff.sh` entry from an older install is removed the next time the installer runs.

| Event | Status effect |
|---|---|
| `SessionStart` (Codex) | clear a stale status suffix |
| `UserPromptSubmit` | `working` |
| `PermissionRequest`, or Claude `Notification` with `notification_type: permission_prompt` | `blocked` |
| `Stop` | `idle` |
| `SessionEnd` | clear only the status suffix |

Other Claude notification types, including idle prompts and agent-completed notices, are ignored rather than mislabeled as blocked. Status and origin hooks also ignore subagent payloads; subagents do not create independent origin or status records.

Origin metadata keeps qualifying top-level edits attached to their originating work stream even if another pane is focused. Review streams are opened only when requested, and `zj_review_stream` reopens a stream a human dismissed.

After installation, restart the host, verify pane titles transition during a request, and confirm the installed definitions contain no `PostToolUse` entry.
