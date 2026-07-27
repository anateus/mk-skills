# Pitfalls & troubleshooting

Sharp edges of driving zellij headlessly, and how each surfaces.

## Spawning

- **Old Zellij builds lack safe background creation.** This skill requires `new-pane --no-focus` from [zellij-org/zellij#5346](https://github.com/zellij-org/zellij/pull/5346). A binary may still report `0.45.0`, so verify the flag in `zellij action new-pane --help`.
- **Focus theft.** Plain `new-pane`, `zellij run`, `new-tab`, `go-to-tab*`, `focus-*`, and `move-focus` can move an attached human's view. Prefer `zj_spawn`, which always uses `--no-focus`; use `new-tab --no-focus` for automated tab creation.
- **A review's recorded origin can differ from its issuing pane.** `--no-focus` places relative to the issuing pane, not an arbitrary recorded parent. When they match, the controller creates directly to the origin's right. Otherwise it targets the parent's tab, verifies the created pane, and uses bounded `move-pane -p ID DIRECTION` steps with refreshed geometry. Unsafe geometry keeps the verified tiled fallback without changing client focus.
- **Floating panes won't render under `hide_floating_panes = true`.** A `--floating` pane *does* show in `list-panes` but stays invisible under that setting — another reason to use tiled for watcher panes.

## Reading panes

- **`dump-screen` is viewport-only by default.** Use `--full` for text that may have scrolled off (all `zj_wait_*` and `read` do).
- **Never `-a/--ansi` for grep.** ANSI escapes break literal/regex matching. Use plain output.
- **Bare `dump-screen` (no `-p`) follows focus** and returns **empty on a headless session**. Always pass `-p <id>`.
- **Silent bad id.** `dump-screen` on a nonexistent/closed pane returns exit 0 + empty. Verify with `zj_pane_exists` first (the `zj_wait_*` helpers do).

## Sending input

- **Prompt visible but not submitted.** If you `write-chars` and the text sits in the composer unsent, the Enter didn't register — send `write -p <id> 13` again. Codex composers often need it twice (`PEER_DOUBLE_ENTER=1`).

## Naming & ids

- **`--name` is title-only, not addressable.** Resolve name→id with `zj_resolve_id`.
- **Ambiguous names.** If two panes share a base title, `zj_resolve_id` exits 2 (ambiguous). Address by `terminal_N` directly, or give panes unique names. Managed agent identities also allocate around emojis already present in open pane titles so compact titles remain distinguishable.
- **Ids don't survive restart.** They're per-session and reset when the session dies. Never persist a `terminal_N` across sessions.

## Sessions

- **One zellij server, many sessions.** For a fleet, use a **dedicated session per run** with a unique name so tests/automation don't collide with a human's session.
- **Never `pkill zellij`** — it kills every session including the human's. Kill only the specific scratch session you created (`zellij kill-session <name>`).

## Status not updating

- Confirm `install-hooks.sh` ran for the active host. Claude Code definitions live in `~/.claude/settings.json`; Codex definitions live in `~/.codex/hooks.json`.
- Check the host's supported status events. Claude uses `UserPromptSubmit` → `working`, permission-prompt `Notification` → `blocked`, `Stop` → `idle`, and `SessionEnd` → clear. Codex uses `SessionStart` → clear stale status, `UserPromptSubmit` → `working`, `PermissionRequest` → `blocked`, `Stop` → `idle`, and `SessionEnd` → clear.
- For Codex, use `/hooks` in a new interactive session to trust new or changed definitions; valid `~/.codex/hooks.json` entries do not become trusted automatically.
- Status updates only when a supported Claude Code or Codex lifecycle event fires; a plain shell pane never gets a status token.
- Subagents are intentionally skipped (`agent_id` guard) — a subagent won't stamp its parent's pane.

## hunk pane didn't open

Walk the prerequisites: is the edit tool supported for this host? Is `<cwd>` inside a **git repo**? Was a top-level origin captured at `SessionStart`? Is `hunk` on PATH? Inspect stream state under `${XDG_CACHE_HOME:-~/.cache}/zellij-agent-herder/streams/` without editing it while hooks are active.

If a tracked pane was closed and the diff signature did not change, the stream is intentionally treated as manually dismissed and automatic hooks stay quiet. Run `zj_review_stream <repo_root> <fixed_base> [label]` for explicit completion review. If the diff changed, a later qualifying edit should reopen it automatically.

If state points to a pane that no longer exists but behavior does not match the dismissal rules, first confirm the correct Zellij session and origin pane, then inspect `list-panes -j` and the cached stream JSON. Remove a stale stream state file only when no related hook/controller process is running; otherwise use `zj_review_stream`, which reconciles state safely.

**A worktree pane disappeared after roll-up.** This is expected: `zj_watch_session` marks the supplied child streams complete, closes only their panes, and opens one aggregate stream over the parent root against the original fixed base. Do not substitute current `HEAD`, which would hide committed merges.

**Codex Hunk hooks are configured but silent.** Validate `~/.codex/hooks.json`, then use `/hooks` in a new interactive Codex session to trust the definitions. Configuration installation does not grant trust automatically.

## Triggering / the `ZELLIJ` env var

- **`ZELLIJ=0` means inside zellij, not "off".** zellij sets `ZELLIJ` to a **client index** (`0` for the primary/only client; higher values for additional clients attached to the same session). The skill keys on the var being **set to any value** — presence, not truthiness. Any integer (including `0`) means you're inside. Only a genuinely **unset** `ZELLIJ` means "not in zellij." Never write `if [ "$ZELLIJ" = 1 ]` or otherwise treat `0` as false.

## Portability

- **Never `date +%s%3N`** (no millisecond `%N` on macOS/BSD). All timing uses bash `$SECONDS`.
