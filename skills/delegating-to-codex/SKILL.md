---
name: delegating-to-codex
description: Hand an implementation or investigation task to Codex from Claude Code or another harness, running it against the real `codex app-server` (not `codex exec`) for per-turn sandbox control, background jobs, and thread resume. Use when asked to delegate work to Codex, run something in Codex, or run a task in the background while continuing other work. Triggers on "hand this to codex", "run this in codex", "delegate to codex", background delegation, or needing a resumable Codex thread.
---

# Delegating to Codex

`codex-run` drives `codex app-server` over JSON-RPC-over-stdio, not `codex exec`: per-turn sandbox (read-only, workspace-write, danger-full-access, none), writable roots, network on/off, permission-profile presets, background jobs, thread resume, a raw event log per run.

## Basic usage

```bash
codex-run -p prompt.md -o last.md
```

Runs one turn, writes agent-message text to `last.md`, prints:

```
exit=<rc> session=<threadId> out=<path> log=<path> job=<jobId> status=<completed|failed|interrupted>
```

`rc`: 0 completed, 1 failed, 130 interrupted, 2 usage error, 3 protocol error.

## Flags

- `-C workdir`: run directory (default `$PWD`).
- `-m model`, `-e effort`: model, reasoning effort, omitted if unset.
- `-s sandbox`: `read-only`, `workspace-write` (default), `danger-full-access`, `none` (no sandbox sent; see Presets).
- `--net`: network under read-only/workspace-write.
- `-w path`: extra writable root under workspace-write; repeatable.
- `-c key=value`: thread-config override (dotted key, JSON value); repeatable, applied after any preset.
- `-r thread_id`: resume a thread (`session=` from a prior one-liner); model, sandbox, cwd can differ.
- `-l log`: log path (default `<out-without-ext>.log`); JSON-RPC in `<out-without-ext>.events.jsonl`.
- `-b`: background: prints `job=<id> session=pending out=... log=...`, exits 0.
- `--timeout secs`: only for `wait`.

## Background jobs

```bash
codex-run -p prompt.md -o out.md -b
codex-run status <job|thread_id>
codex-run wait <job|thread_id> [--timeout secs]
codex-run cancel <job|thread_id>
codex-run list
```

`status`/`wait`/`cancel` take a `job=` id or `session=` thread id. Job files live at `~/.local/state/codex-run/jobs/<jobId>.json` (override with `CODEX_RUN_STATE_DIR`): prompt, sandbox policy, ids, status, rc, for offline lookup.

## Sandbox

Under `workspace-write`, cwd is writable by default; add roots with `-w`, network with `--net`. Both also need thread-level `config`: codex's exec tool enforces only the thread's sandbox, so a turn-only root or `--net` is echoed back but ignored.

Codex denies writes to the checkout's own git directory under `workspace-write`; for a linked worktree that's `.git/worktrees/<name>/`, so `git add`/`git commit` from inside Codex fail with `index.lock: Operation not permitted` (openai/codex #7071, #23661). Leave the tree modified and commit from the controlling agent, or use `-s danger-full-access`.

`--print-policy` prints resolved cwd, sandbox policy, and thread config as JSON, no codex touched, exit 0. Verify `--net` with curl against a live host: fails without it, `200` with it.

## Presets

`--preset <name|path>` resolves `presets/<name>.json` (or a path) and merges into thread config before `-c`, which wins on conflicts. A preset's `$sandbox` key picks the `-s` mode when you didn't set one; codex-run strips `$`/`_` keys before sending config. Default to `--preset github-only` for delegated implementation work: sandbox `none`, a permission profile scoped to GitHub hosts, credential and dotfile denies. With no preset, `-s workspace-write` stays the bare default.

nono/fence wrapping isn't compatible with Codex's sandbox and proxy yet; see [references/live-verification.md](references/live-verification.md) for the evaluation.

## Install

```bash
pnpx skills add anateus/mk-skills
ln -sf "$HOME/.agents/skills/delegating-to-codex/scripts/codex-run.mjs" ~/.local/bin/codex-run
```

In development, point the symlink at the checkout's `scripts/codex-run.mjs`. Back up an older `codex-run` (`codex exec` v1): `cp -n ~/.local/bin/codex-run ~/.local/bin/codex-run-v1`.

## Non-goals

No broker, no MCP, no sandbox wrapper beyond `codex app-server`, no review or transfer commands. A thin single-turn driver; orchestration belongs in the caller.

See [references/live-verification.md](references/live-verification.md) for the scenario checklist and observed one-liners.
