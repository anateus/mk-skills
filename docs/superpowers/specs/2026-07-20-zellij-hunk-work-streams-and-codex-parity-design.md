# Zellij Hunk Work Streams and Codex Parity

## Purpose

Keep Hunk review panes useful throughout development instead of leaving empty or duplicated panes after commits, merges, and agent delegation. A logical work stream should have roughly one active Hunk pane, placed immediately to the right of the Zellij pane from which the work ultimately originated.

The same operational behavior should work for Claude Code and Codex. Portable personal guidance and Hindsight memory should also be shared between them.

## Scope

This change covers:

- automatic mid-development Hunk watchers;
- explicit end-of-task Hunk review panes;
- headless worktree-agent watchers and their aggregate roll-up;
- origin-pane capture and best-effort right-side placement;
- Claude Code and Codex lifecycle-hook installation;
- shared global agent guidance; and
- Codex Hindsight setup using the existing `claude_code` bank.

It does not introduce a Zellij plugin, redesign Hunk itself, or synchronize every Claude-only preference into Codex.

## Work-Stream Model

A work stream is identified by:

- the Zellij session;
- the top-level origin pane; and
- the git common directory plus the active worktree or aggregate identity.

The origin pane is captured for the top-level agent session and retained across background work and subagents. The human's currently focused pane is never treated as the origin merely because it is focused when a hook fires.

Each active stream owns at most one controller-managed Hunk pane. Its state records:

- stream key and generation;
- owner Zellij session and parent pane ID;
- Hunk pane ID;
- repository or worktree path;
- fixed diff-base SHA;
- diff mode, such as worktree or aggregate; and
- dismissal and last-observed diff identity.

State lives under the existing `~/.cache/zellij-agent-herder/` area and is treated as advisory. Pane and repository state remain authoritative.

## Watcher Controller

All entry points route through one controller rather than independently spawning panes. These entry points include Claude and Codex edit hooks, explicit review helpers, `zj_watch_worktree`, and `zj_watch_session`.

For a watcher request, the controller:

1. Resolves the logical stream and its parent pane.
2. Prunes stale state for missing panes or vanished worktrees.
3. Reuses the current watcher when it still represents the requested diff.
4. Replaces it when the stream generation, target path, diff base, or diff mode changes.
5. Opens the replacement beside the parent when possible.
6. Records state only after confirming that the new pane exists.

Replacement is preferred over in-place retargeting because Hunk sessions can outlive their terminal panes and Zellij does not provide a simple command-level process replacement API. The user-visible invariant matters more than retaining a pane ID: one relevant pane per active stream.

## Diff Stability and Roll-Up

Every watcher uses a fixed branch-point SHA as its base. It must not use moving `main` or current `HEAD`, because sibling merges can create phantom removals and commits can make a `HEAD`-relative watcher empty.

During worktree fan-out, each independently active worktree may have one watcher. When those changes are merged into a parent stream, the roll-up operation:

1. closes only the child watcher panes owned by the controller;
2. marks their stream generations complete;
3. opens or refreshes one aggregate watcher over the parent repository; and
4. retains the original fixed branch-point SHA so merged commits and uncommitted changes remain visible.

Automatic edit-time review and proactive task-completion review use the same stream key and controller. Completion therefore refreshes or reuses the relevant watcher instead of opening a duplicate.

## Manual Dismissal

If a user closes a watcher pane, the controller records that generation as dismissed when it next observes the missing pane. Repeated edits with the same material diff identity do not immediately reopen it.

The material diff identity is a stable hash of the fixed base, target worktree, tracked diff content, and untracked-file paths and content. Timestamp-only changes and hook retries therefore do not create a new generation, while a real source change does.

The stream may open a watcher again when:

- the material diff identity changes;
- the stream rolls up into a new aggregate generation; or
- an explicit review request asks to reopen it.

This keeps automatic review useful without fighting deliberate pane closure.

## Parent-Right Placement

Zellij 0.45 can split the focused pane to the right, but `new-pane` cannot target an arbitrary parent pane ID. `--near-current-pane` is not sufficient: it can silently fail or misplace a pane when a background agent issues the action while another pane is focused.

When the origin pane exists and exactly one client is attached, the controller creates
and verifies a plain tiled pane first. It then uses bounded, geometry-selected
`move-pane -p ID DIRECTION` steps, refreshing `list-panes -j` until the watcher is
observed immediately right of the origin. Because external `focus-pane-id` does not
retarget the attached client in Zellij 0.45, focus restoration uses bounded directional
`move-focus` steps and briefly polls `list-clients` after each one. The client table is
the authoritative restoration signal because pane geometry/focus can update first.
After verified creation and placement, a detached controller invocation guards for
one second against a late switch to that watcher. It restores only from the watcher,
continues observing within the same deadline after success, and exits without action
on any third-pane focus, missing pane, client ambiguity, or controller error.

If no client is attached, the origin pane is gone, or focus cannot be resolved safely, the controller falls back to a plain tiled pane. It retains the origin identity so a later replacement can be placed correctly. With multiple attached clients, placement is best-effort and must not intentionally move every client's focus.

## Claude Code and Codex Hooks

The installation scripts gain explicit support for both hosts while preserving unrelated configuration.

Claude Code continues to use `~/.claude/settings.json` and installed scripts under `~/.claude/hooks/`.

Codex uses `~/.codex/hooks.json` and scripts installed under a Codex-owned hook directory. Its configuration uses the current Codex hook schema and synchronous command handlers; Codex parses but skips `async` handlers. Relevant tool matchers include `apply_patch`, `Edit`, and `Write`, with shell-edit detection added only if needed for parity and reliably identifiable from the hook payload.

Both integrations normalize their different hook payloads into the controller's host-neutral request format. Top-level session hooks capture the origin pane. Subagent hooks inherit the top-level origin and do not independently create a new work stream unless an explicit worktree-watcher request defines one.

Install and uninstall operations are idempotent. They merge or remove only entries owned by this skill, preserve unrelated hooks, back up modified configuration, and report any hook-trust step Codex requires after definitions change.

## Shared Global Guidance

Create `~/.agents/AGENTS.md` as the canonical personal guidance file and create `~/.codex/AGENTS.md` as a symlink to it. Update `~/.claude/CLAUDE.md` to import or explicitly reference the canonical file using Claude Code's supported instruction-file syntax, while retaining only Claude-specific overlay guidance locally.

Portable guidance copied from `~/.claude/CLAUDE.md` includes:

- verify architectural and stack claims against live code rather than relying on manifests or aspirational documentation;
- use Hindsight as the primary cross-session memory system when available; and
- proactively route completed coding changes through the work-stream-aware Hunk review flow when running inside Zellij.

Claude-specific model delegation remains only in `~/.claude/CLAUDE.md`. Guidance that names Claude-only tools is rewritten in host-neutral terms in the shared file. Changes to the canonical file therefore reach both hosts without manual duplication. Existing personal files are backed up before replacement, reference insertion, or symlink creation.

## Shared Hindsight Memory

Use Hindsight's existing Codex integration rather than inventing a second MCP wrapper. Install or copy its Codex lifecycle scripts into the normal user location, merge its `SessionStart`, `UserPromptSubmit`, and `Stop` handlers into `~/.codex/hooks.json`, and set `bankId` to `claude_code` with dynamic bank IDs disabled.

Reuse the same Hindsight endpoint and authentication source already configured for Claude. Secrets must not be copied into this repository, printed during installation, or embedded in the shared guidance file. A failed or unavailable Hindsight service must not prevent normal Codex turns or Hunk watcher behavior.

## Failure Handling

- Missing panes and vanished worktrees are pruned without closing unrelated panes.
- Failed Hunk or Zellij launches do not create durable success markers that block retries.
- Pane ownership is verified by recorded ID and stream metadata before closure.
- Focus restoration runs after every attempted parent-relative spawn.
- Missing Hunk, Zellij, git, Python, or unsupported host versions produce a concise diagnostic and leave the agent workflow usable.
- Concurrent hook invocations serialize updates per stream so they cannot create duplicate panes or corrupt state.
- Malformed hook payloads no-op safely and can emit debug diagnostics when explicitly enabled.

## Testing

Hermetic tests use temporary git repositories, cache/config homes, and scratch Zellij sessions. They cover:

- one watcher for repeated edits in one stream;
- separate watchers for independently active worktree streams;
- child watcher closure and single aggregate watcher creation on roll-up;
- fixed-base visibility after commits and merges;
- explicit review reusing or intentionally reopening the stream watcher;
- manual dismissal surviving an unchanged diff and reopening after a material change;
- stale pane and vanished-worktree recovery;
- parent-right placement and restoration of the previously focused pane;
- headless and missing-parent tiled fallback;
- concurrent requests for the same stream;
- Claude and Codex payload normalization;
- Codex's synchronous hook configuration and relevant edit matchers;
- idempotent hook installation and ownership-scoped uninstall;
- preservation of unrelated Claude and Codex hooks;
- creation and backup behavior for the shared guidance symlink;
- Claude's global instruction file importing the shared guidance while retaining its host-specific overlay; and
- Hindsight configuration using the shared `claude_code` bank without exposing credentials.

Live verification in a scratch Zellij session confirms the final pane geometry and restored client focus, since command exit status alone is not reliable evidence that a move occurred.

## Success Criteria

- At steady state, each active logical work stream has no more than one controller-managed Hunk pane.
- Committing, merging, or rolling up work does not leave an empty watcher as the only review surface.
- A watcher is split immediately right of its recorded parent pane whenever Zellij permits it, with a safe tiled fallback otherwise.
- Background agents retain the top-level origin pane instead of following incidental client focus.
- Claude Code and Codex receive equivalent watcher behavior through their native hook formats.
- Codex reads the shared global guidance and uses the same Hindsight `claude_code` bank as Claude.
