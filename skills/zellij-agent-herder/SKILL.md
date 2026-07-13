---
name: zellij-agent-herder
description: "Use when running inside zellij (the ZELLIJ env var is present — zellij sets it to a client index, so ANY value including \"0\" means inside; it's presence, not truthiness) and you need to control panes/tabs/sessions, spawn or coordinate peer coding agents, wait on their output or status, or watch changes in a live diff. Not for use outside zellij. Requires zellij >= 0.44."
---

# zellij-agent-herder

Control zellij panes/sessions and drive peer coding agents from inside a zellij pane.

## Guard

If `$ZELLIJ` is **unset** you are **not inside zellij** — say so and stop; nothing here applies. If it is **set to any value, proceed** — zellij sets `ZELLIJ` to a client index (`0` for the primary/only client, higher for additional simultaneous clients), so `0` means *inside*, not "off". Check presence, never truthiness.

**Reliable activation (optional).** This skill fires only when Claude notices it's inside zellij. If that gets missed at session start, offer to install a lightweight `SessionStart` hook that surfaces the zellij session into context every session: `bash "<skill-base-dir>/references/hooks/install-hook.sh"` (undo with `uninstall-hook.sh` in the same dir). It's a discovery aid, separate from the operational status/hunk hooks below — see `references/hooks.md`.

## Concepts

- Hierarchy: **session → tabs → panes**. A pane is addressed by `(session, pane_id)`; there are no stable global ids.
- Session targeting is the global flag: `zellij --session <name> action <cmd>`, or `$ZELLIJ_SESSION_NAME`. Helpers default to `ZJ_SESSION=$ZELLIJ_SESSION_NAME`.
- `--name`/`-n` sets the **title only** (not addressable) — resolve name→id with `zj_resolve_id`.
- Spawn only via **`zj_spawn`**: it places beside the current pane (no focus steal) when a human is attached, and falls back to plain `new-pane` when headless — because `--near-current-pane`/`-d` silently no-op with no client.

## Helpers

`source "<skill-base-dir>/scripts/zj.sh"` (bash/zsh) — gives `_zj`, `_zj_panes`, `zj_resolve_id`, `zj_pane_exists`, `zj_client_count`, `zj_spawn`, `zj_wait_output`, `zj_wait_exit`, `zj_wait_status`. All paths are relative to this skill's base directory (printed on load); never hardcode an install path.

**From fish or another non-POSIX shell** (can't source a bash lib): invoke a helper instead — `bash "<skill-base-dir>/scripts/zj.sh" zj_spawn -n worker -- bash`, `bash "<skill-base-dir>/scripts/zj.sh" zj_wait_output <id> <match> 10`. The peer wrapper and installer are already invocation-based, so they work from any shell.

## Core quick reference

| Do | Command |
|---|---|
| list panes | `_zj_panes` (or `zellij action list-panes -j`) |
| read a pane | `_zj dump-screen -p <id> --full` (plain, never `-a`) |
| spawn | `zj_spawn -d right --cwd DIR -n NAME -- CMD` |
| send text | `_zj write-chars -p <id> "text"` |
| send Enter | `_zj write -p <id> 13` (twice for Codex) |
| close | `_zj close-pane -p <id>` |
| switch tab | `_zj go-to-tab-name <name>` (steals attached view) |
| wait for text | `zj_wait_output <id> <match> <timeout> [--regex]` |
| wait for exit | `zj_wait_exit <id> <timeout>` or `zellij run --block-until-exit-success -- CMD` |
| wait for status | `zj_wait_status <id> working\|idle\|blocked <timeout>` |

## Peer agents

To spawn/drive peer coding agents, use `scripts/zellij-peer.sh {start\|ask\|wait\|read\|list\|close}`. **REQUIRED SUB-SKILL / see** `references/peer-agents.md` for workflows, per-role prompting, and the rule: inspect the peer's actual file changes yourself before reporting success.

## Hooks (status + hunk)

Run `bash "<skill-base-dir>/scripts/install-hooks.sh"` once to get live pane-title status (`working`/`idle`/`blocked`) and an automatic `hunk diff --watch` pane on the first file change. See `references/hooks.md`. Drive a live diff via the `hunk-review` skill.

## Pointers

- `references/command-reference.md` — full herdr→zellij mapping, helper signatures, addressing model.
- `references/pitfalls.md` — sharp edges (silent headless spawn, focus theft, ids, status/hunk troubleshooting).
