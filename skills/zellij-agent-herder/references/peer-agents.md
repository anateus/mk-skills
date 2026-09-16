# Peer agents in zellij

Spawn and drive peer coding agents (Claude, Codex, …) in sibling panes. All lifecycle is `scripts/zellij-peer.sh`, which sources `zj.sh`.

## `zellij-peer.sh` subcommands

| Command | Effect |
|---|---|
| `start <name> [--cwd DIR] [--direction right\|down] [--tab\|--pane] -- <agent-cmd...>` | Spawn an identified child pane; prints its real `terminal_N`. The default places it in `<origin tab> - Peers N`, reusing the newest group while it has fewer than four visible panes and creating the next group when full. `--tab` and `ZJ_PEER_PLACEMENT=tab` are aliases for this grouped placement. `--pane` keeps the old beside-the-caller behavior. |
| `ask <name> "<prompt>"` | Native bracketed `paste`, a 250ms render pause, then one Enter (`write 13`). Requires Zellij's `paste` action. Success means input was sent, not that the peer accepted it. |
| `wait <name> [--status idle] [--timeout S]` | Block until the pane's status token equals `--status` (default `idle`, timeout 300s). Requires the status hook installed in the peer's agent. |
| `read <name> [--lines N]` | Dump the pane's full scrollback, last `N` lines (default 200). |
| `list` | One row per pane: `id  base-title  status`. |
| `close <name>` | Close the pane. |

## Identity and coordination

Address peers by explicit pane ID, stable leaf name, or rendered base. `start` persists session-scoped identity and ancestry; `close` removes its record.

Read the peer first and confirm its composer is ready for the prompt. After `ask`, use `read` to verify that the prompt appears in the transcript or the peer visibly starts working, before waiting for idle. Text still in the composer and an idle title are not acknowledgement. Raw `write-chars` followed immediately by Enter can make a paste-aware composer consume Enter as a newline; `ask` uses native bracketed paste to avoid that burst.

If acknowledgement is missing, read again after the editor settles. Send one additional Enter only when the screen clearly shows the intended text still in a ready composer. Never repaste the prompt or blindly repeat Enter when submission is uncertain. `PEER_DOUBLE_ENTER=1` is rejected before input is sent. Startup, reconnect, permission dialogs, and nonempty drafts need inspection rather than automatic retries.

Read [peer identity details](peer-identity.md) when diagnosing names, ancestry, emoji collisions, or choosing a longer-lived coordination pattern.

## Choosing peer panes

Claude Code's built-in Agent-tool subagents are good enough most of the time for dispatch-and-wait delegation. Use peer panes when the new agents are genuine peers of the current one: parallel independent work streams, long-lived agents, or cross-harness coordination. In Codex, the interface for inspecting subagents is still rudimentary, so prefer peer panes by default until its capabilities change.

### Codex peers that share AgentPlan

When AgentPlan is installed, a Codex peer needs its storage directory as a writable sandbox root. Grant `${AGENTPLAN_DIR:-$HOME/.agentplan}`; if `AGENTPLAN_DB` overrides the database path, also grant that file's parent directory. AgentPlan creates storage subdirectories and SQLite uses WAL sidecars and locking, so approving only the executable or database file isn't enough. Grant these directories, not the whole home directory, and repeat the same roots when resuming a peer.

```bash
agentplan_roots=(--add-dir "${AGENTPLAN_DIR:-$HOME/.agentplan}")
if [ -n "${AGENTPLAN_DB:-}" ]; then
  agentplan_roots+=(--add-dir "$(dirname "$AGENTPLAN_DB")")
fi
zellij-peer.sh start worker --cwd "$PWD" -- codex --sandbox workspace-write "${agentplan_roots[@]}"
# Resume the intended peer with its same storage roots, not a fresh default policy.
zellij-peer.sh start worker --cwd "$PWD" -- codex resume --sandbox workspace-write "${agentplan_roots[@]}" "PEER_SESSION_NAME"
```

Have the peer run real `agentplan status <project>` and `agentplan note <project> "Peer storage preflight passed" --ticket <assigned-ticket>` before dispatching business work. A controller-side check or an executable permission alone doesn't prove the peer can update the shared board. If preflight fails, fix the peer's writable roots before continuing; don't bypass the CLI with manual SQLite writes.

## Workflows

### One-shot review
```
zellij-peer.sh start reviewer --cwd "$PWD" -- claude   # prints the pane id; later calls resolve by name
zellij-peer.sh ask reviewer "Review the diff in this repo for correctness bugs. Do NOT edit files. When done, print DONE and stop."
zellij-peer.sh read reviewer --lines 80
# Confirm transcript or working acknowledgement before waiting for completion.
zellij-peer.sh wait reviewer --status idle --timeout 600
zellij-peer.sh read reviewer
zellij-peer.sh close reviewer
```

### Implementation helper (iterative)
Keep the pane open; `ask` a scoped task, `read` for acknowledgement, `wait` for idle, then `read` the result. Give one task at a time.

### Bidirectional messaging
Relay: `read` agent A → `ask` agent B with A's output → verify B's acknowledgement → `wait` B → `read` B → back to A. Keep a turn budget; stop when converged.

## Per-role prompt guidance

- **Reviewers/verifiers:** "**Do not edit files.**" Give an explicit stop condition ("print DONE and stop"). Ask for file:line evidence.
- **Implementers:** one task at a time; name the files in scope; tell them to run the covering test and report results.
- Give an explicit stop condition so `wait --status idle` is meaningful; an agent that keeps asking follow-ups never goes idle.

## Before reporting success

`wait idle` + `read` tells you what the peer *said*, not what it *did*. **Inspect the actual file changes yourself** (`git diff`, run the tests) before you report a peer's work as complete.

## Model tiering and parallel fan-out

- Default peer implementers to a mid-tier model; reserve the strongest model for the hardest tasks and for taking over when a cheaper peer is stuck. Small fast models suit only well-specified mechanical tasks, and their output needs a stronger reviewer plus a controller-level run of the real code.
- For parallel worktree fan-out: check task file overlap before dispatch, give each peer a unique port and resource range for e2e runs, never let a peer kill processes by name (it kills siblings), and let the controller alone rebase, re-run gates, and merge in a fixed order.
