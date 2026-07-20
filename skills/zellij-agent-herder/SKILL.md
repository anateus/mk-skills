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
- Agent panes created by `zellij-peer.sh` or observed by the status hook receive stable breadcrumb identities. Plain panes are unaffected.

## Helpers

`source "<skill-base-dir>/scripts/zj.sh"` (bash/zsh) — gives `_zj`, `_zj_panes`, `zj_resolve_id`, `zj_close_pane`, `zj_pane_exists`, `zj_client_count`, `zj_spawn`, `zj_watch_worktree`, `zj_watch_session`, `zj_review_stream`, `zj_wait_output`, `zj_wait_exit`, `zj_wait_status`. All paths are relative to this skill's base directory (printed on load); never hardcode an install path.

**From fish or another non-POSIX shell** (can't source a bash lib): invoke a helper instead — `bash "<skill-base-dir>/scripts/zj.sh" zj_spawn -n worker -- bash`, `bash "<skill-base-dir>/scripts/zj.sh" zj_wait_output <id> <match> 10`. The peer wrapper and installer are already invocation-based, so they work from any shell.

## Core quick reference

| Do | Command |
|---|---|
| list panes | `_zj_panes` (or `zellij action list-panes -j`) |
| read a pane | `_zj dump-screen -p <id> --full` (plain, never `-a`) |
| spawn | `zj_spawn -d right --cwd DIR -n NAME -- CMD` |
| reopen a stream for completion review | `zj_review_stream <repo_root> <base_sha> [label]` |
| send text | `_zj write-chars -p <id> "text"` |
| send Enter | `_zj write -p <id> 13` (twice for Codex) |
| close | `zj_close_pane <id>` (also removes cached identity) |
| switch tab | `_zj go-to-tab-name <name>` (steals attached view) |
| wait for text | `zj_wait_output <id> <match> <timeout> [--regex]` |
| wait for exit | `zj_wait_exit <id> <timeout>` or `zellij run --block-until-exit-success -- CMD` |
| wait for status | `zj_wait_status <id> working\|idle\|blocked <timeout>` |

## Peer agents

To spawn/drive peer coding agents, use `scripts/zellij-peer.sh {start\|ask\|wait\|read\|list\|close}`. **REQUIRED SUB-SKILL / see** `references/peer-agents.md` for workflows, per-role prompting, and the rule: inspect the peer's actual file changes yourself before reporting success.

## Pane identity breadcrumbs

Peer and lifecycle-observed agent panes render stable lineage, for example `mk-skills (🦀 funky-crab) · working`, then `🦀 f-c > 🌿 schema-review · working`. A root preserves a useful existing pane base as its display label, falling back to the repository/cwd name. Useful native session names are retained as identities. Generic `agent`/`claude`/`codex`/`yolo` labels, spinner-prefixed variants, and cwd/repository identity names receive a persisted adjective-noun fallback with a concrete emoji.

Metadata lives under `${XDG_CACHE_HOME:-$HOME/.cache}/zellij-agent-herder/panes/<session>/<pane>.json`; ancestry is never recovered from title text. `zj_resolve_id` accepts an explicit pane ID, full/rendered base, or stable leaf identity name. The status separator remains exactly ` · `.

## Watching headless worktree agents

Herding isn't only for interactive peer panes. When a controller dispatches **headless** worktree subagents (the `Agent` tool with `isolation: "worktree"`), this skill still applies — to open **one passive, human-facing `hunk diff --watch` pane per worktree** so you can watch each agent's changeset live. The agents stay headless with structured returns; the panes are just for the human. Don't conclude "not a herder task" because the agents aren't interactive — the watching is the herder part.

```
BASE=$(git rev-parse HEAD)                                 # fixed branch point, capture once
zj_watch_worktree <worktree_abs_path> "$BASE" [label]      # one per worktree; echoes the pane id
# ... fan-out runs; controller merges each worktree into the parent tree in order ...
zj_watch_session <parent_repo_root> "$BASE" session <id>... # teardown: swap N panes for 1 aggregate
```

- A review stream is identified by its **Zellij session, originating pane, and git identity** (git common directory plus the worktree root/kind). Hooks persist the top-level agent's origin pane, so work done from another focused pane—or by a subagent whose edit is reported through the parent lifecycle—still belongs to the originating parent stream. Subagents do not create independent origin or status records.
- **During fan-out**, open one `zj_watch_worktree` pane per worktree.
- **At teardown**, once the worktrees are merged and removed, call `zj_watch_session` once with the pane ids the watchers returned: it closes them (their dirs are gone, so their restart loops would otherwise spin) and opens **one aggregate pane** over the parent tree showing the **whole session's work** — parent tree vs the *same* `$BASE`, spanning every merged commit plus anything uncommitted.
- **At explicit completion review**, call `zj_review_stream <repo_root> "$BASE" [label]`. It reuses the live pane or deliberately reopens a manually dismissed unchanged stream; automatic edit hooks respect that dismissal until the diff changes.
- **Leave review notes as work lands.** Each `--watch` pane is a live hunk session, so whenever a significant chunk of work completes (a worktree finishes, or the aggregate lands), use the **`/hunk-review`** skill to walk the hunks and drop inline comments on that diff — drive it through `hunk session *`, never a hand-run `hunk diff`. The notes stay attached to the live session for a reviewer or the human to read.
- **Placement preserves the human's view.** With exactly one attached client, the controller temporarily focuses the recorded origin, opens the review split to its right, then restores the previous focus. With no client, multiple clients, or an unavailable origin, it falls back to a plain tiled pane and verifies the returned pane id.
- **Diff base = the fixed SHA the worktrees branched from**, not `main` (advances when you merge a sibling → phantom "removed" lines) and not `HEAD` (empties on commit — the aggregate pane in particular goes blank the moment merges land).

This is the controller-driven fan-out counterpart to the Hunk hook below. Hooks skip subagent-origin/status records while keeping qualifying parent-lifecycle edits associated with the top-level agent's originating stream.

## Hooks (status + hunk)

Run `bash "<skill-base-dir>/scripts/install-hooks.sh" --all` once to install Claude Code and Codex lifecycle hooks for live pane-title status (`working`/`idle`/`blocked`), origin tracking, and automatic stream review on file changes. Codex requires reviewing the definitions with `/hooks` in the next interactive session. See `references/hooks.md`. Drive a live diff via the `hunk-review` skill.

## Pointers

- `references/command-reference.md` — full herdr→zellij mapping, helper signatures, addressing model.
- `references/pitfalls.md` — sharp edges (silent headless spawn, focus theft, ids, status/hunk troubleshooting).
