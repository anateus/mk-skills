---
name: zellij-agent-herder
description: "Control Zellij panes, sessions, peer agents, waits, and live Hunk review streams using the bundled helpers. Use when running inside Zellij (`ZELLIJ` is set, including `0`) and the task requires pane orchestration, peer coordination, status waiting, or live diff watching. Requires Zellij 0.44 or newer."
---

# zellij-agent-herder

Control Zellij panes and sessions from inside a Zellij pane.

## Guard

If `$ZELLIJ` is unset, stop: this skill does not apply. If it is set to any value, proceed. Zellij stores a client index there, so `ZELLIJ=0` means inside; check presence, not truthiness. Requires Zellij 0.44 or newer.

## Addressing and safety

- The hierarchy is session → tabs → panes. Address a pane by `(session, pane_id)`; pane IDs are not stable global identifiers.
- Target a session with `zellij --session <name> action <command>` or `$ZELLIJ_SESSION_NAME`. Helpers default `ZJ_SESSION` to that name.
- `--name`/`-n` sets a title, not an address. Resolve a name with `zj_resolve_id`.
- Spawn only through `zj_spawn`. It places a pane beside the current pane without stealing focus when one human client is attached, and safely falls back to plain `new-pane` when headless. Direct `--near-current-pane`/`-d` can silently no-op without a client.
- Before fan-out, capture one fixed branch-point `BASE`. Never substitute advancing `main` or current `HEAD`; doing so produces incomplete or misleading aggregate diffs.

## Load helpers

For bash or zsh:

```bash
source "<skill-base-dir>/scripts/zj.sh"
```

This loads `_zj`, `_zj_panes`, resolution, spawn, close, wait, worktree-watch, session-watch, and review helpers. The script resolves its own base directory internally; keep invocation paths skill-base-relative.

From fish or another non-POSIX shell, invoke instead of sourcing, for example:

```bash
bash "<skill-base-dir>/scripts/zj.sh" zj_spawn -n worker -- bash
```

## Quick reference

| Do | Command |
|---|---|
| list panes | `_zj_panes` |
| read pane | `_zj dump-screen -p <id> --full` |
| spawn | `zj_spawn -d right --cwd DIR -n NAME -- CMD` |
| send text / Enter | `_zj write-chars -p <id> "text"`; `_zj write -p <id> 13` |
| close | `zj_close_pane <id>` |
| wait for text | `zj_wait_output <id> <match> <timeout> [--regex]` |
| wait for exit | `zj_wait_exit <id> <timeout>` |
| wait for status | `zj_wait_status <id> working\|idle\|blocked <timeout>` |
| completion review | `zj_review_stream <repo_root> <base_sha> [label]` |

## Conditional references

- **REQUIRED REFERENCE:** Read [peer agents](references/peer-agents.md) when spawning or driving interactive coding-agent panes.
- Read [worktree review streams](references/worktree-review-streams.md) for headless worktree watchers, fixed-base fan-out, aggregation, or live Hunk review. Before annotating a live session, run `hunk skill path` and read the installed `hunk-review` skill completely.
- Read [activation hook](references/activation-hook.md) when Zellij presence is being missed at session start.
- Read [lifecycle hooks](references/lifecycle-hooks.md) for status, identity, origin, and automatic Hunk-diff hook installation or removal.
- Read [shared agent configuration](references/shared-agent-config.md) for shared `AGENTS.md`, Claude guidance, or Hindsight setup.
- Read [command reference](references/command-reference.md) for complete helper signatures and verified native Zellij semantics.
- Read [pitfalls](references/pitfalls.md) when diagnosing focus, addressing, headless spawn, status, or Hunk problems.
