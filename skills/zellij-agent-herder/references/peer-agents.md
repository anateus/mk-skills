# Peer agents in zellij

Spawn and drive peer coding agents (Claude, Codex, …) in sibling panes. All lifecycle is `scripts/zellij-peer.sh`, which sources `zj.sh`.

## `zellij-peer.sh` subcommands

| Command | Effect |
|---|---|
| `start <name> [--cwd DIR] [--direction right\|down] [--tab\|--pane] -- <agent-cmd...>` | Spawn an identified child pane; prints its real `terminal_N`. The default places it in `<origin tab> - Peers N`, reusing the newest group while it has fewer than four visible panes and creating the next group when full. `--tab` and `ZJ_PEER_PLACEMENT=tab` are aliases for this grouped placement. `--pane` keeps the old beside-the-caller behavior. |
| `ask <name> "<prompt>"` | `write-chars` the prompt into the pane, then Enter (`write 13`). |
| `wait <name> [--status idle] [--timeout S]` | Block until the pane's status token equals `--status` (default `idle`, timeout 300s). Requires the status hook installed in the peer's agent. |
| `read <name> [--lines N]` | Dump the pane's full scrollback, last `N` lines (default 200). |
| `list` | One row per pane: `id  base-title  status`. |
| `close <name>` | Close the pane. |

## Identity and coordination

Address peers by explicit pane ID, stable leaf name, or rendered base. `start` persists session-scoped identity and ancestry; `close` removes its record. Use `PEER_DOUBLE_ENTER=1` when a composer needs two Enter presses. Choose the shortest interaction that fits the task.

Read [peer identity details](peer-identity.md) when diagnosing names, ancestry, emoji collisions, or choosing a longer-lived coordination pattern.

## Choosing peer panes

Claude Code's built-in Agent-tool subagents are good enough most of the time for dispatch-and-wait delegation. Use peer panes when the new agents are genuine peers of the current one: parallel independent work streams, long-lived agents, or cross-harness coordination. In Codex, the interface for inspecting subagents is still rudimentary, so prefer peer panes by default until its capabilities change.

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
- Give an explicit stop condition so `wait --status idle` is meaningful; an agent that keeps asking follow-ups never goes idle.

## Before reporting success

`wait idle` + `read` tells you what the peer *said*, not what it *did*. **Inspect the actual file changes yourself** (`git diff`, run the tests) before you report a peer's work as complete.

## Model tiering and parallel fan-out

- Default peer implementers to a mid-tier model; reserve the strongest model for the hardest tasks and for taking over when a cheaper peer is stuck. Small fast models suit only well-specified mechanical tasks, and their output needs a stronger reviewer plus a controller-level run of the real code.
- For parallel worktree fan-out: check task file overlap before dispatch, give each peer a unique port and resource range for e2e runs, never let a peer kill processes by name (it kills siblings), and let the controller alone rebase, re-run gates, and merge in a fixed order.
