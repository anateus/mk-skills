---
name: delegating-to-codex
description: Hand an implementation or investigation task to Codex from Claude Code or another harness, running it against the real `codex app-server` (not `codex exec`) for per-turn sandbox control, background jobs, and thread resume. Use when asked to delegate work to Codex, run something in Codex, or run a task in the background while continuing other work. Triggers on "hand this to codex", "run this in codex", "delegate to codex", background delegation, or needing a resumable Codex thread.
---

# Delegating to Codex

`codex-run` drives `codex app-server` over JSON-RPC-over-stdio instead of shelling out to `codex exec`: per-turn sandbox policy (read-only, workspace-write, or danger-full-access, with writable roots and network on/off), background jobs, thread resume, a raw event log per run.

## Basic usage

```bash
codex-run -p prompt.md -o last.md
```

Reads `prompt.md`, runs one turn, writes agent-message text to `last.md`, prints one line:

```
exit=<rc> session=<threadId> out=<path> log=<path> job=<jobId> status=<completed|failed|interrupted>
```

`rc`: 0 completed, 1 failed, 130 interrupted, 2 usage error, 3 protocol error. Script against this line, not the log.

## Flags

- `-C workdir` — directory to run in (default `$PWD`).
- `-m model`, `-e effort` — model and reasoning effort (omitted if unset).
- `-s sandbox` — `read-only`, `workspace-write` (default), or `danger-full-access`.
- `--net` — network access under read-only/workspace-write (ignored otherwise).
- `-w path` — extra writable root under workspace-write; repeatable.
- `-r thread_id` — resume a thread (the `session=` value from a prior one-liner); model, sandbox, cwd can differ from the original run.
- `-l log` — log path (default `<out-without-ext>.log`); raw JSON-RPC goes to `<out-without-ext>.events.jsonl` — inspect with `jq`, not `cat`.
- `-b` — background: prints `job=<id> session=pending out=... log=...` immediately, exits 0.
- `--timeout secs` — only meaningful with `wait`.

## Background jobs

```bash
codex-run -p prompt.md -o out.md -b            # returns immediately with a job id
codex-run status <job|thread_id>               # prints the one-liner, rc 3 if still running
codex-run wait <job|thread_id> [--timeout secs]   # blocks, polling every 1s, until terminal
codex-run cancel <job|thread_id>               # SIGTERM, worker sends turn/interrupt, waits up to 15s
codex-run list                                 # newest first: jobId status threadId cwd startedAt
```

`status`/`wait`/`cancel` take either the `job=` id or the `session=` thread id. Job files live at `~/.local/state/codex-run/jobs/<jobId>.json` (override with `CODEX_RUN_STATE_DIR`, mainly for tests): prompt text, sandbox policy, thread/turn ids, status, rc — enough for a detached worker to run the turn and for later lookups offline.

## Sandbox and worktree roots

Under `workspace-write`, cwd is writable by default; add more with `-w`. If `-C` is a linked git worktree (`.git` is a file, not a directory), codex-run resolves the common git dir via `git rev-parse --git-common-dir` and adds it as a writable root automatically — git needs that dir writable to commit from the worktree. Codex's sandbox can still block specific git lock files (`index.lock`, `COMMIT_EDITMSG`) even so; route around with plumbing commands rather than `danger-full-access`.

`--print-policy` does the same resolution but skips codex — prints resolved cwd, sandbox policy, worktree root as JSON, exit 0. This is how the offline tests check worktree detection without a real codex run.

## Install

```bash
pnpx skills add anateus/mk-skills
ln -sf "$HOME/.agents/skills/delegating-to-codex/scripts/codex-run.mjs" ~/.local/bin/codex-run
```

In development, point the symlink at the checkout's `scripts/codex-run.mjs` instead. Back up an older `codex-run` (the `codex exec` v1) first: `cp -n ~/.local/bin/codex-run ~/.local/bin/codex-run-v1`.

## Non-goals

No broker, no MCP, no sandbox wrapper beyond `codex app-server`, no review or transfer commands. A thin single-turn driver; orchestration belongs in the caller.

See [references/live-verification.md](references/live-verification.md) for the seven-scenario checklist and observed one-liners.
