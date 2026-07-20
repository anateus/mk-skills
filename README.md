# mk-skills

Agent skills for [Claude Code](https://claude.com/claude-code), installable with the [`skills`](https://github.com/vercel-labs/skills) CLI.

## Install

```bash
# all skills, into the current project (./.claude/skills/)
npx skills add anateus/mk-skills

# global (~/.claude/skills/)
npx skills add anateus/mk-skills -g

# a single skill
npx skills add anateus/mk-skills --skill zellij-agent-herder
```

## Skills

| Skill | What it does | Requires |
|---|---|---|
| **zellij-agent-herder** | Control zellij panes/tabs/sessions and drive peer coding agents from inside a zellij pane — spawn/read/send/close, wait on output or status, and keep Claude/Codex edits in origin-aware Hunk review streams with worktree roll-up. | `zellij` ≥ 0.44 (developed against 0.45); `hunk` 0.17+ for the diff feature. Helpers source under bash/zsh; from fish, invoke via `bash <dir>/scripts/zj.sh <helper> …`. |

### Setup — zellij-agent-herder hooks

The pane-title status, origin tracking, and stream-aware Hunk review features use Claude Code and Codex lifecycle hooks. Install both host configurations once:

```bash
bash "<skill-base-dir>/scripts/install-hooks.sh" --all
```

The installer is idempotent, backs up changed `~/.claude/settings.json` and `~/.codex/hooks.json`, and preserves unrelated hooks. Use `--uninstall --all` for ownership-scoped removal. In the next Codex interactive session, use `/hooks` to trust the installed definitions.

To share host-neutral guidance and the `claude_code` Hindsight bank across Claude and Codex after the official Hindsight Codex integration is already installed:

```bash
bash "<skill-base-dir>/scripts/setup-shared-agent-config.sh"
```

This backs up changed personal configuration, keeps credentials intact, imports `~/.agents/AGENTS.md` into Claude, and symlinks Codex to the same guidance. It does not download missing Hindsight hooks during ordinary setup. See `references/hooks.md` for the explicit installation prerequisite, verification, recovery, and uninstall behavior.
