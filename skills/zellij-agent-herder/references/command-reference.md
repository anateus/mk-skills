# Command reference — herdr → zellij

Verified against **zellij 0.45.0**. Source `scripts/zj.sh` first; every helper below lives there.

## Addressing model

- A pane is addressed by the tuple **`(session, pane_id)`**. There is no herdr-style global stable id.
- `pane_id` is per-session, monotonic, never reused within a session's life, **never stable across restarts** (a new session starts fresh at `terminal_0`/`plugin_0`).
- `list-panes -j` reports `id` as a **bare int**; `zj.sh` normalizes it to `terminal_<n>` (or `plugin_<n>` for plugin panes — zellij keeps separate id counters per type, so `is_plugin` disambiguates a `terminal_2` from a `plugin_2`) everywhere. `-p terminal_<n>` and `-p <n>` are both accepted by zellij.
- `zj.sh` is sourced into your shell (SKILL.md) under **bash/zsh** — no bash-only array indexing or `trap RETURN`. **From fish (or any non-POSIX shell)** you cannot source it; instead invoke a helper directly via the dispatcher: `bash "<dir>/zj.sh" <helper> <args...>` (e.g. `bash "<dir>/zj.sh" zj_spawn -n worker -- bash`). The dispatcher only fires when the file is executed, never when sourced.
- Session targeting is the **global** flag before the subcommand: `zellij --session <name> action <cmd>`, or the `ZELLIJ_SESSION_NAME` env var. `action` has no independent `--session` flag. `zj.sh` uses `ZJ_SESSION` (defaults to `$ZELLIJ_SESSION_NAME`).
- `--name`/`-n` sets the pane **title only** — it is NOT addressable. Resolve name→id via `zj_resolve_id` (matches the full title or the base before `" · "`).

## `zj.sh` helper signatures

| Helper | Signature → result |
|---|---|
| `_zj` | `_zj <action> [args...]` — run a `zellij action` against `$ZJ_SESSION`. |
| `_zj_panes` | emits each pane object from `list-panes -j` as one JSON line, `id` normalized to `terminal_<n>`/`plugin_<n>` per `is_plugin` (handles both flat-list and dict-by-tab shapes). |
| `zj_resolve_id` | `<name>` → prints `terminal_<n>` (exit 1 not found, 2 ambiguous). |
| `zj_pane_exists` | `<pane_id>` → exit 0 if present, else 1. |
| `zj_client_count` | → number of attached clients (0 == headless). |
| `zj_spawn` | `[new-pane args...]` → spawn a pane, echo its id. **Adaptive** (see below). |
| `zj_wait_output` | `<pane_id> <match> <timeout_s> [interval_s] [--regex]` → 0 match / 1 timeout / 3 missing. `[interval_s]` and `[--regex]` are each independently optional, any order. |
| `zj_wait_exit` | `<pane_id> <timeout_s> [interval_s]` → prints exit_status; 0 exited / 1 timeout / 3 missing. |
| `zj_wait_status` | `<pane_id> <status> <timeout_s> [interval_s]` → 0 when the title's status token equals `<status>` (working\|idle\|blocked); 1 timeout / 3 missing. |

## herdr → zellij action mapping

| Intent | herdr | zellij (`zj.sh`) |
|---|---|---|
| list panes | `pane list` | `_zj_panes` / `zellij action list-panes -j` |
| spawn pane | `pane spawn` | `zj_spawn -d right --cwd DIR -n NAME -- CMD` |
| read pane | `pane read` | `_zj dump-screen -p <id> --full` (plain, never `-a/--ansi`) |
| send text | `pane send` | `_zj write-chars -p <id> "text"` |
| send Enter | — | `_zj write -p <id> 13` (Codex composers may need it twice) |
| rename/title | — | `_zj rename-pane -p <id> "<title>"` |
| close pane | `pane close` | `_zj close-pane -p <id>` |
| switch tab | — | `_zj go-to-tab-name <name>` (⚠ steals an attached client's view) |
| wait for text | `wait output` | `zj_wait_output <id> <match> <timeout>` |
| wait for exit | — | `zj_wait_exit <id> <timeout>` or native `zellij run --block-until-exit-success -- CMD` |
| wait for status | `wait agent-status` | `zj_wait_status <id> <status> <timeout>` (needs the status hook installed) |

## Adaptive spawn (`zj_spawn`)

Placement relative to the focused pane (`--near-current-pane`, `-d/--direction`) **silently no-ops in a headless/no-client session** (zellij exits 0 and prints a fake `terminal_N`, but no pane appears — it needs a connected client for current-pane-relative layout). `zj_spawn` therefore branches on `zj_client_count`:

- **client attached** → `new-pane --near-current-pane <args>` (places beside the current pane, does **not** steal focus).
- **headless** → strips `-d`/`--direction`/`--near-current-pane` and calls plain `new-pane` (zellij picks the biggest free space).

Never call `new-pane --near-current-pane`/`-d` directly — go through `zj_spawn`. Don't trust `new-pane`'s printed `terminal_N` as authoritative (it prints even on the no-op); recover the real id from `list-panes -j`.

## Native blocking waits (zellij ≥ 0.44)

`zellij run`/`new-pane` support `--blocking`, `--block-until-exit`, `--block-until-exit-success`, `--block-until-exit-failure`. These cover **spawning a one-shot command and waiting for it to exit**. They do NOT cover waiting for text to appear in a long-running pane that never exits (a Claude/Codex CLI) — for that, use `zj_wait_output` (a `dump-screen --full` + grep poll loop).

## Capabilities zellij does NOT have natively (filled by this skill)

- **Wait-for-text in a long-running pane** → `zj_wait_output` poll loop.
- **Agent lifecycle status** (working/idle/blocked) → the status hook stamps it into the pane title; read via `zj_wait_status` / `list-panes -j`.
- **Stable global pane ids** → there are none; address by `(session, pane_id)` and resolve names per session.
