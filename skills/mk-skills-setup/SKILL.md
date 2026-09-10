---
name: mk-skills-setup
description: Install or refresh mk-skills' shared guidance in AGENTS.md or CLAUDE.md. Merges a managed block idempotently, previews by default, and backs up before applying.
---

# mk-skills Setup

Merge `assets/agents-guidance.md` into the host's persistent instructions. Only the marker-delimited managed block changes; surrounding content survives and repeated runs converge. Run the helper from this skill's directory.

## Run it

Preview the unified diff first:

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

Keep local additions outside the managed markers; a later apply overwrites edits inside them. If the block already matches, the helper reports "up to date". Equivalent guidance elsewhere may make installation unnecessary, but the helper compares only its managed block.

## Extending what it ships

Edit `assets/agents-guidance.md` to change the guidance, then re-run against each target to propagate. Keep the asset to genuinely portable, always-on rules that support the skill set; skill-specific detail belongs in that skill's `SKILL.md`/`references/`, not here.
