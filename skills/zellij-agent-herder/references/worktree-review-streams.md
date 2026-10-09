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

## Identity, tabs, and reopening

A stream is keyed by Zellij session, originating pane, and Git identity (common directory plus worktree root/kind). Reviews use `<origin tab> -  Reviews #N`, reusing the newest group while it has fewer than four visible panes and opening the next group when full. Native `new-pane --no-focus --tab-id` and `new-tab --no-focus` keep every attached client on its current tab. If the origin tab cannot be determined, the stream falls back to `🔍 <label>`. Pane titles preserve compact lineage and append a review leaf.

At completion, run:

```bash
zj_review_stream <repo_root> "$BASE" [label]
```

This reuses the live stream or explicitly reopens an unchanged stream that a human dismissed. Because the installer no longer registers a review hook, nothing reopens it automatically; run this command (or `zj_watch_worktree`) when you want a review surface.

## Review handoff

Before annotating, run `hunk skill path` and read the returned `hunk-review` skill completely. Walk and comment through `hunk session *`; do not replace the live session with a hand-run `hunk diff`. Leave notes as significant work lands and inspect the aggregate after all merges.

## Managed resource limits

New managed panes run `hunk-watch.py`, which owns one `hunk diff <fixed-base> --watch` child. `ZAH_MAX_ACTIVE_STREAMS` defaults to **4 across Zellij sessions sharing the same cache root**, not four per session. Admission counts live managed panes (including completed streams whose close failed) and locked supervisor leases. Missing inventory or corrupt state blocks new starts. Existing manual Hunk processes are neither adopted nor signalled. Old managed panes count toward admission but gain supervision only when explicitly reopened.

The watcher samples its child's RSS every 15 seconds. Three consecutive samples at or above 512 MiB pause that child with `SIGSTOP`. This is a soft growth guard, not a hard memory limit: sampling can overshoot, pausing retains allocated memory, and descendant processes are not sampled. The warning prints an exact `kill -USR1 <supervisor-pid>` command. Run it from another pane to resume the same child with a five-minute grace period, preserving review state.

Local Hunk 0.19.0 code initializes notes in memory and saves drafts into that in-memory store. Restart durability was not established for installed Hunk 0.22.0. Treat recycling as lossy for drafts, saved inline notes, navigation and extension state. Recycling is **off by default**. For disposable review surfaces, explicitly set `ZAH_HUNK_RECYCLE=1`; pressure then replaces only the owned child in the same pane, with the same working directory and fixed base. It never restarts after an ordinary exit or crash. Closing the pane ends supervision, including a paused child, without reopening the review.

Set these variables before opening a managed stream. Launch carries the settings into the new pane; changing them doesn't reconfigure an existing watcher.

| Variable | Default | Meaning |
| --- | --- | --- |
| `ZAH_MAX_ACTIVE_STREAMS` | `4` | Shared-cache admission cap |
| `ZAH_HUNK_RSS_MIB` | `512` | Child RSS pressure threshold |
| `ZAH_HUNK_SAMPLE_SECONDS` | `15` | Sampling interval |
| `ZAH_HUNK_PRESSURE_SAMPLES` | `3` | Consecutive high samples before action |
| `ZAH_HUNK_RESUME_GRACE_SECONDS` | `300` | Pressure grace after explicit resume |
| `ZAH_HUNK_RECYCLE` | unset | Only `1` permits lossy recycling |
| `ZAH_HUNK_MAX_AGE_SECONDS` | `0` | Age action disabled; positive values pause, or recycle when opted in |
| `ZAH_HUNK_RESTART_DELAY_SECONDS` | `30` | Delay between child generations |
| `ZAH_HUNK_MAX_RESTARTS` | `3` | Lifetime recycle budget; further pressure pauses |
| `ZAH_HUNK_STOP_GRACE_SECONDS` | `3` | TERM grace before KILL on owned-child shutdown |

Unknown pane inventory prevents recycling but doesn't discard an existing child. Confirmed pane closure or supervisor HUP/TERM/INT continues a stopped child, terminates it and waits for exit before releasing its lease. An uncatchable supervisor `SIGKILL` cannot run this cleanup. No process-name sweeps or unrelated-process kills are used.
