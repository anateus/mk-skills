# mk-skills

A portable, curated software-development skill set for Codex and Claude Code. Selective invocation is the default: load a skill when its trigger clearly matches, and scale ceremony to the task's risk. Strict mode adds explicit sequencing and verification without changing the skills or requiring external workflow.

## Curated skills

The core set covers `clarifying-work`, `adversarial-refinement`, `specifying-work`, `planning-work`, `test-driven-development`, `diagnosing-bugs`, `investigating-incidents`, `implementing-work`, `reviewing-code`, `handling-review-feedback`, `verifying-work`, `handing-off-work`, `strict-mode`, and `curating-skills`.

`zellij-agent-herder` is also included for optional pane orchestration. It and the curated workflow are bidirectionally independent: every curated skill works without zellij, and the herder works without strict mode or the curated skills. When independent tasks benefit from peers, the peer-ready plans make pairing low effort; sequential execution remains fully supported.

## Codex plugin

Install or link this repository through the Codex plugin workflow so `.codex-plugin/plugin.json`, `skills/`, `hooks/`, `lib/`, and `config/` remain together. Before trusting the plugin, review [`hooks/hooks.json`](hooks/hooks.json) and [`hooks/run-hook.js`](hooks/run-hook.js): the synchronous `SessionStart` hook reads the documented event fields, loads the shared local policy, and writes context JSON.

Choose a profile with an environment override:

```bash
MK_SKILLS_MODE=strict|selective|off
```

Use one concrete value, for example `MK_SKILLS_MODE=strict codex`. Until reasoning effort becomes a stable hook field, pair a low-reasoning Codex profile with `strict` explicitly; the hook deliberately does not inspect transcripts. `off` disables policy injection but leaves skills available for explicit use.

Without an override, conservative small-model markers (`mini`, `nano`, and `haiku`) and legacy GPT-3.x/Claude 2–3 families select strict mode automatically. Other and unknown model identifiers remain selective; adjust `config/mode-policy.json` when a host introduces a new stable model family.

## Claude Code adapter

Claude support is a required deliverable, not a separate skill fork. Package or link the repository as a Claude plugin and expose [`adapters/claude/hooks.json`](adapters/claude/hooks.json) as its hook declaration. It invokes the same runner and `config/mode-policy.json` through `CLAUDE_PLUGIN_ROOT`, so both hosts select identical text. Review the hook command before enabling the plugin. Startup, resume, clear, and compact use the shared selector where Claude supports those `SessionStart` sources.

For skills-only installation, the existing CLI remains available:

```bash
npx skills add anateus/mk-skills
npx skills add anateus/mk-skills -g
```

Ordinary execution skills are self-contained and work offline after installation. Network access is used only for deliberate upstream curation; [`curating-skills`](skills/curating-skills/SKILL.md) additionally requires an mk-skills source checkout, reviews pinned sources, and produces a manual merge report without overwriting local skills.

## Validate

Run all repository-owned hook, skill, curation, and bundled Zellij Python/shell suites, optional plugin-schema validation, and the diff check with:

```bash
node scripts/validate.js
```

Set `PLUGIN_VALIDATOR=/path/to/validate_plugin.py` to select a validator. The plugin-schema check reports whether it skipped because the validator file is absent or because PyYAML is unavailable; PyYAML is not required by installed skills. Repository-owned checks continue.

Static tests do not substitute for clean-session activation evidence. Before release, follow the [skill activation forward-test guide](docs/validation/skill-activation-forward-tests.md) using the checked-in fixtures.

For Zellij pane-title status and auto-diff setup, read [`lifecycle-hooks.md`](skills/zellij-agent-herder/references/lifecycle-hooks.md). Those hooks are optional and independent of both host adapters above.

### Optional zellij-agent-herder setup

The herder keeps Claude/Codex edits in origin-aware Hunk review streams with worktree roll-up. It requires zellij 0.44 or newer and Hunk 0.17 or newer for live diffs.

The pane-title status, origin tracking, and stream-aware Hunk review features use Claude Code and Codex lifecycle hooks. Install both host configurations once:

```bash
bash "<skill-base-dir>/scripts/install-hooks.sh" --all
```

The installer is idempotent, backs up changed `~/.claude/settings.json` and `~/.codex/hooks.json`, and preserves unrelated hooks. Use `--uninstall --all` for ownership-scoped removal. In the next Codex interactive session, use `/hooks` to trust the installed definitions.

To share host-neutral guidance and the `claude_code` Hindsight bank across Claude and Codex after the official Hindsight Codex integration is already installed:

```bash
bash "<skill-base-dir>/scripts/setup-shared-agent-config.sh"
```

This backs up changed personal configuration, keeps credentials intact, imports `~/.agents/AGENTS.md` into Claude, and symlinks Codex to the same guidance. It does not download missing Hindsight hooks during ordinary setup. Read [`shared-agent-config.md`](skills/zellij-agent-herder/references/shared-agent-config.md) for prerequisites and verification behavior; hook uninstall applies only to the Zellij-owned entries described above. Read [`worktree-review-streams.md`](skills/zellij-agent-herder/references/worktree-review-streams.md) for fixed-base worktree and live Hunk operation.

If an official Codex integration already exists in a trusted local checkout, install it without downloading:

```bash
bash "<skill-base-dir>/scripts/setup-shared-agent-config.sh" --hindsight-source <official-codex-integration-dir>
```

The source must contain regular `hooks/hooks.json`, `settings.json`, and `scripts/` content with the required lifecycle hook groups. The installer rejects symlinks and malformed structure, stages a local copy under `~/.hindsight/codex`, substitutes its installed scripts path, and then applies the shared configuration.
