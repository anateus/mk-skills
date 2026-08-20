---
name: subagent-artifact-discipline
description: Install, remove, configure, or troubleshoot the shared Claude Code and Codex subagent artifact lifecycle hooks. Use when a user asks about subagent artifact paths, hook installation, hook updates, or artifact hook behavior.
---

# Subagent artifact discipline

Use the shared lifecycle runner to preserve detailed subagent findings outside the parent transcript.

## Install

Review `scripts/install-hooks.sh`, `scripts/artifact-discipline.js`, and `config/artifact-discipline.json` before installation. Install only when the user asks for host configuration changes.

If this skill is absent from `~/.agents/skills`, install it explicitly. `skills update` reports newly available skills but does not install them.

```bash
pnpx skills add anateus/mk-skills --skill subagent-artifact-discipline --agent codex claude-code -g -y
```

```bash
bash "<skill-dir>/scripts/install-hooks.sh" --all
```

Use `--claude` or `--codex` to configure one host. The installer preserves unrelated hooks, backs up changed configuration, and links each host to this skill's runner. After global installation, `pnpx skills update -g` updates the linked runner without another hook install.

Review the updated runner and start a new host session after installation or update. In Codex, open `/hooks` to confirm the hook is enabled and trust it when its definition hash changes.

## Uninstall

```bash
bash "<skill-dir>/scripts/install-hooks.sh" --uninstall --all
```

Uninstall removes only entries and links owned by this skill.

## Configuration

Set `MK_SKILLS_ARTIFACT_DIR` to an absolute artifact root. Set `MK_SKILLS_ARTIFACT_DISCIPLINE=off` to disable both lifecycle hooks for one process.

The runner fails open when input, configuration, or storage is unsafe. It does not read subagent transcripts or change tool permissions.
