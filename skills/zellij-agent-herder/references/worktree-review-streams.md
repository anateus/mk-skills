# Worktree and Hunk review streams

## Fixed-base fan-out

Capture the branch point once before dispatch. Never replace it with advancing `main` or current `HEAD`.

```bash
BASE=$(git rev-parse HEAD)
zj_watch_worktree <worktree_abs_path> "$BASE" [label]
# merge completed worktrees into the parent in order
zj_watch_session <parent_repo_root> "$BASE" session <watcher_id>...
```

Open one passive `hunk diff --watch` pane per headless worktree. Keep the agents headless; the panes are human-facing review surfaces. After merges and worktree removal, `zj_watch_session` closes the obsolete watchers and opens one aggregate parent-tree stream against the same `BASE`, covering merged commits and uncommitted changes.

## Identity, placement, and reopening

A stream is keyed by Zellij session, originating pane, and Git identity (common directory plus worktree root/kind). With exactly one attached client, placement briefly focuses the recorded origin, opens to its right, then restores focus. Otherwise it falls back to a tiled pane and verifies the returned ID. Titles preserve compact lineage and append a review leaf.

At completion, run:

```bash
zj_review_stream <repo_root> "$BASE" [label]
```

This reuses the live stream or explicitly reopens an unchanged stream that a human dismissed. Automatic lifecycle hooks keep that dismissal until the diff changes.

## Review handoff

Before annotating, run `hunk skill path` and read the returned `hunk-review` skill completely. Walk and comment through `hunk session *`; do not replace the live session with a hand-run `hunk diff`. Leave notes as significant work lands and inspect the aggregate after all merges.
