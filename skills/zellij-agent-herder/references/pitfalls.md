# Pitfalls & troubleshooting

Sharp edges of driving zellij headlessly, and how each surfaces.

## Spawning

- **Directional/relative spawn silently no-ops headless.** `new-pane --near-current-pane` and `new-pane -d <dir>` exit 0 and print a `terminal_N` string but create **no pane** when no client is attached. Always spawn via `zj_spawn`, which detects this and falls back to plain `new-pane`. Symptom: a later `list-panes` / `zj_resolve_id` can't find the pane you "just spawned."
- **Don't trust `new-pane`'s printed id.** It prints even on the no-op. Recover the real id from `list-panes -j` (or resolve by name).
- **Focus theft.** Plain `new-pane`, `zellij run`, `new-tab`, `go-to-tab*`, `focus-*`, `move-focus` move an attached human's view. Prefer `zj_spawn` (uses `--near-current-pane` when attached) and avoid tab/focus actions when a human may be watching.

## Reading panes

- **`dump-screen` is viewport-only by default.** Use `--full` for text that may have scrolled off (all `zj_wait_*` and `read` do).
- **Never `-a/--ansi` for grep.** ANSI escapes break literal/regex matching. Use plain output.
- **Bare `dump-screen` (no `-p`) follows focus** and returns **empty on a headless session**. Always pass `-p <id>`.
- **Silent bad id.** `dump-screen` on a nonexistent/closed pane returns exit 0 + empty. Verify with `zj_pane_exists` first (the `zj_wait_*` helpers do).

## Sending input

- **Prompt visible but not submitted.** If you `write-chars` and the text sits in the composer unsent, the Enter didn't register — send `write -p <id> 13` again. Codex composers often need it twice (`PEER_DOUBLE_ENTER=1`).

## Naming & ids

- **`--name` is title-only, not addressable.** Resolve name→id with `zj_resolve_id`.
- **Ambiguous names.** If two panes share a base title, `zj_resolve_id` exits 2 (ambiguous). Address by `terminal_N` directly, or give panes unique names.
- **Ids don't survive restart.** They're per-session and reset when the session dies. Never persist a `terminal_N` across sessions.

## Sessions

- **One zellij server, many sessions.** For a fleet, use a **dedicated session per run** with a unique name so tests/automation don't collide with a human's session. `zj_client_count` tells you if anyone's attached.
- **Never `pkill zellij`** — it kills every session including the human's. Kill only the specific scratch session you created (`zellij kill-session <name>`).

## Status not updating

- Confirm `install-hooks.sh` ran and the entries are in `~/.claude/settings.json`.
- Status only updates for a **Claude-family agent** whose lifecycle fires the hooks; a plain shell pane never gets a status token.
- Subagents are intentionally skipped (`agent_id` guard) — a subagent won't stamp its parent's pane.

## hunk pane didn't open

Walk the skip conditions: is `<cwd>` inside a **git repo**? Is the tree **dirty**? Is a **live hunk session already open** for the repo (`hunk session get --repo <root>` exits 0 — including a stray watcher that outlived its pane)? Did the **per-turn dedup marker** already fire (`~/.cache/zellij-agent-herder/turn-*`)? Is `hunk` on PATH? Any one of these is a deliberate no-op.

## Portability

- **Never `date +%s%3N`** (no millisecond `%N` on macOS/BSD). All timing uses bash `$SECONDS`.
