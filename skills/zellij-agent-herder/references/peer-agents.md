# Peer agents in zellij

Spawn and drive peer coding agents (Claude, Codex, …) in sibling panes. All lifecycle is `scripts/zellij-peer.sh`, which sources `zj.sh`.

## `zellij-peer.sh` subcommands

| Command | Effect |
|---|---|
| `start <name> [--cwd DIR] [--direction right\|down] -- <agent-cmd...>` | Spawn an identified child pane; prints its real `terminal_N`. Spawn is adaptive (beside the current pane when a human is attached, plain when headless). |
| `ask <name> "<prompt>"` | `write-chars` the prompt into the pane, then Enter (`write 13`). |
| `wait <name> [--status idle] [--timeout S]` | Block until the pane's status token equals `--status` (default `idle`, timeout 300s). Requires the status hook installed in the peer's agent. |
| `read <name> [--lines N]` | Dump the pane's full scrollback, last `N` lines (default 200). |
| `list` | One row per pane: `id  base-title  status`. |
| `close <name>` | Close the pane. |

## Stable identity and lineage

After `start` receives the real pane ID, it persists the child identity and parent ancestry, then renames the pane to a breadcrumb:

```text
mk-skills (🦀 funky-crab) · working
🦀 f-c > 🌿 schema-review · working
🦀 f-c > 🌿 s-r > 🍎 test-runner · idle
```

Useful `<name>` values become the stable leaf name. A root persists a useful existing pane base as its display label, otherwise the repository/cwd name, and wraps its emoji identity in parentheses. Generic names (`agent`, `claude`, `codex`, `yolo` and their prefixed/spinner variants) or identity names equal to the cwd/repository fall back to a stable adjective-noun plus a concrete emoji. Allocation excludes emojis claimed by other open pane identities in the session; a cached identity is reallocated if another open pane claims its emoji, keeping compact titles distinguishable. Derived review breadcrumbs do not claim their parent's emoji. Metadata is session-scoped at `${XDG_CACHE_HOME:-$HOME/.cache}/zellij-agent-herder/panes/<session>/<pane>.json`, so grandchildren inherit ancestry without parsing titles.

Later commands may address the explicit pane ID, current rendered base, or stable leaf name. `close` removes that pane's cache record. Panes created outside the peer wrapper remain unchanged unless the lifecycle status hook observes them.

**`PEER_DOUBLE_ENTER=1`** — some composers (notably Codex) need Enter pressed twice to submit. Export this and `ask` sends a second `write 13`.

## The four-level model (from herdr-peer-agents)

1. **One-shot** — spawn, ask one question, read the answer, close. Reviews, quick lookups.
2. **Iterative** — keep the pane open, `ask`/`wait`/`read` in a loop. Implementation help, debugging.
3. **Bidirectional** — two agents ask each other; you relay. Rare; expensive.
4. **Fleet** — many peers in one session, addressed by name. Parallel independent tasks.

Start at the lowest level that fits. Higher levels cost more tokens and more coordination.

## Workflows

### One-shot review
```
zellij-peer.sh start reviewer --cwd "$PWD" -- claude   # prints the pane id; later calls resolve by name
zellij-peer.sh ask reviewer "Review the diff in this repo for correctness bugs. Do NOT edit files. When done, print DONE and stop."
zellij-peer.sh wait reviewer --status idle --timeout 600
zellij-peer.sh read reviewer
zellij-peer.sh close reviewer
```

### Implementation helper (iterative)
Keep the pane open; `ask` a scoped task, `wait` for idle, `read`, then `ask` the next step. Give one task at a time.

### Bidirectional messaging
Relay: `read` agent A → `ask` agent B with A's output → `wait` B → `read` B → back to A. Keep a turn budget; stop when converged.

## Per-role prompt guidance

- **Reviewers/verifiers:** "**Do not edit files.**" Give an explicit stop condition ("print DONE and stop"). Ask for file:line evidence.
- **Implementers:** one task at a time; name the files in scope; tell them to run the covering test and report results.
- Always give an explicit **stop condition** so `wait --status idle` is meaningful — an agent that keeps asking follow-ups never goes idle.

## Before reporting success

`wait idle` + `read` tells you what the peer *said*, not what it *did*. **Inspect the actual file changes yourself** (`git diff`, run the tests) before you report a peer's work as complete.

## Model tiering and parallel fan-out

- Default peer implementers to a mid-tier model; reserve the strongest model for the hardest tasks and for taking over when a cheaper peer is stuck. Small fast models suit only well-specified mechanical tasks, and their output needs a stronger reviewer plus a controller-level run of the real code.
- For parallel worktree fan-out: check task file overlap before dispatch, give each peer a unique port and resource range for e2e runs, never let a peer kill processes by name (it kills siblings), and let the controller alone rebase, re-run gates, and merge in a fixed order.
