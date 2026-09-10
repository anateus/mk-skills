# Peer identity details

## Stable identity and lineage

After `start` receives the real pane ID, it persists the child identity and parent ancestry, then renames the pane to a breadcrumb:

```text
mk-skills (🦀 funky-crab) · working
🦀 f-c > 🌿 schema-review · working
🦀 f-c > 🌿 s-r > 🍎 test-runner · idle
```

Useful `<name>` values become the stable leaf name. A root persists a useful existing pane base as its display label, otherwise the repository/cwd name, and wraps its emoji identity in parentheses. Generic names (`agent`, `claude`, `codex`, `yolo` and their prefixed/spinner variants) or identity names equal to the cwd/repository fall back to a stable adjective-noun plus a concrete emoji. Allocation excludes emojis claimed by other open pane identities in the session; a cached identity is reallocated if another open pane claims its emoji, keeping compact titles distinguishable. Derived review breadcrumbs do not claim their parent's emoji. Metadata is session-scoped at `${XDG_CACHE_HOME:-$HOME/.cache}/zellij-agent-herder/panes/<session>/<pane>.json`, so grandchildren inherit ancestry without parsing titles.

Later commands may address the explicit pane ID, current rendered base, or stable leaf name. `close` removes that pane's cache record. Panes created outside the peer wrapper remain unchanged unless the lifecycle status hook observes them.

**`PEER_DOUBLE_ENTER=1`**: some composers (notably Codex) need Enter pressed twice to submit. Export this and `ask` sends a second `write 13`.

## The four-level model (from herdr-peer-agents)

1. **One-shot**: spawn, ask one question, read the answer, close. Reviews, quick lookups.
2. **Iterative**: keep the pane open, `ask`/`wait`/`read` in a loop. Implementation help, debugging.
3. **Bidirectional**: two agents ask each other; you relay. Rare; expensive.
4. **Fleet**: many peers in one session, addressed by name. Parallel independent tasks.

Start at the lowest level that fits. Higher levels cost more tokens and more coordination.
