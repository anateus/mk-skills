---
name: mk-skills-setup
description: Bootstrap mk-skills' cross-cutting agent guidance into a host's always-on instructions by merging a shipped, marker-delimited block into AGENTS.md or CLAUDE.md — idempotently, dry-run by default, with a backup on apply. Use once after installing mk-skills to seed guidance (e.g. the read-discipline that pairs with data-spelunking) that individual skills assume but that only lives in a per-skill file otherwise; re-run any time to update the managed block in place.
---

# mk-skills Setup

Some guidance needs to be *always on*, not loaded per-skill — e.g. the subagent read-discipline that keeps delegated spelunking from thrashing. A `SKILL.md` only loads when its trigger fires, so cross-cutting rules like that belong in the host's persistent instructions (`AGENTS.md` for Codex/shared agents, `CLAUDE.md` for Claude Code). This skill merges the shipped block into one of those files safely.

It ships the guidance in `assets/agents-guidance.md` and writes it into the target inside a marker-delimited **managed block**. Only that block is touched; everything else in the file is preserved. Re-running converges the block to whatever the skill currently ships — it never duplicates.

## Run it

Dry-run first (default — shows a unified diff, writes nothing):

```
scripts/merge-guidance.py --into agents-global
```

Apply once it looks right (saves a `<target>.bak` backup, then writes):

```
scripts/merge-guidance.py --into agents-global --apply
```

Target selection:

| flag | file |
|------|------|
| `--into agents-global` | `~/.agents/AGENTS.md` |
| `--into claude-global` | `~/.claude/CLAUDE.md` |
| `--into agents-project` | `./AGENTS.md` |
| `--into claude-project` | `./CLAUDE.md` |
| `--target PATH` | any explicit file |

Run with no target to list detected candidates and whether each already holds the managed block. A missing target file is only created with `--create`, and only when its parent directory already exists (it will not mkdir a surprising tree).

## Safety / idempotency

- **Dry-run by default.** Nothing is written without `--apply`.
- **Backup on apply.** The prior file is copied to `<target>.bak` before writing.
- **Managed block only.** Content is bounded by `<!-- BEGIN mk-skills:agent-guidance … -->` / `<!-- END mk-skills:agent-guidance -->`. Re-running replaces just that region; if the block already matches, it reports "up to date" and exits 0. Hand-edits *inside* the markers are overwritten on re-run — put local additions outside them.

## When you don't need it

If the host's `AGENTS.md`/`CLAUDE.md` already carries equivalent guidance (e.g. you wrote the read-discipline block by hand), skip it — a dry-run will show no change and re-applying is a no-op.

## Extending what it ships

Edit `assets/agents-guidance.md` to change the guidance, then re-run against each target to propagate. Keep the asset to genuinely portable, always-on rules that support the skill set; skill-specific detail belongs in that skill's `SKILL.md`/`references/`, not here.
