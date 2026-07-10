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
| **zellij-agent-herder** | Control zellij panes/tabs/sessions and drive peer coding agents from inside a zellij pane — spawn/read/send/close, wait on output or status, live pane-title status, and an auto `hunk diff --watch` pane on first file change. | `zellij` ≥ 0.44 (developed against 0.45); `hunk` 0.17+ for the diff feature. Helpers source under bash/zsh; from fish, invoke via `bash <dir>/scripts/zj.sh <helper> …`. |

### Setup — zellij-agent-herder hooks

The pane-title status and auto-diff features ride Claude Code lifecycle hooks. Install them once:

```bash
bash "<skill-base-dir>/scripts/install-hooks.sh"
```

(idempotent; backs up `~/.claude/settings.json`, preserves existing hooks). See the skill's `references/hooks.md` for what it writes and how to uninstall.
