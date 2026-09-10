---
name: delegating-to-codex
description: Hand an implementation or investigation task to Codex from Claude Code or another harness, running it against the real `codex app-server` (not `codex exec`) for per-turn sandbox control, background jobs, and thread resume. Use when asked to delegate work to Codex, run something in Codex, or run a task in the background while continuing other work. Triggers on "hand this to codex", "run this in codex", "delegate to codex", background delegation, or needing a resumable Codex thread.
---

# Delegating to Codex

`codex-run` drives `codex app-server` over JSON-RPC-over-stdio instead of shelling out to `codex exec`: per-turn sandbox policy (read-only, workspace-write, danger-full-access; writable roots, network on/off), background jobs, thread resume, a raw event log per run.

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

- `-C workdir`: run directory (default `$PWD`).
- `-m model`, `-e effort`: model, reasoning effort, omitted if unset.
- `-s sandbox`: `read-only`, `workspace-write` (default), `danger-full-access`.
- `--net`: network under read-only/workspace-write.
- `-w path`: extra writable root under workspace-write; repeatable.
- `-r thread_id`: resume a thread (`session=` from a prior one-liner); model, sandbox, cwd can differ.
- `-l log`: log path (default `<out-without-ext>.log`); JSON-RPC in `<out-without-ext>.events.jsonl`.
- `-b`: background: prints `job=<id> session=pending out=... log=...`, exits 0.
- `--timeout secs`: only for `wait`.

## Background jobs

```bash
codex-run -p prompt.md -o out.md -b            # returns immediately, job id
codex-run status <job|thread_id>               # one-liner, rc 3 if running
codex-run wait <job|thread_id> [--timeout secs]   # blocks until terminal
codex-run cancel <job|thread_id>               # SIGTERM, waits up to 15s
codex-run list                                 # newest first
```

`status`/`wait`/`cancel` take either the `job=` id or `session=` thread id. Job files live at `~/.local/state/codex-run/jobs/<jobId>.json` (override with `CODEX_RUN_STATE_DIR`, mainly for tests): prompt, sandbox policy, thread/turn ids, status, rc, enough for a detached worker to run the turn and for later offline lookups.

## Sandbox

Under `workspace-write`, cwd is writable by default; add roots with `-w`, network with `--net`. Both also need thread-level `config` (`thread/start`/`thread/resume`), not just per-turn policy: codex's exec tool enforces the thread's sandbox, so a turn-only root or `--net` is echoed back but ignored.

Codex also denies writes to the checkout's own git directory under `workspace-write`, even inside a writable root. For a linked worktree that's `.git/worktrees/<name>/`, so `git add`/`git commit` from inside Codex fail with `index.lock: Operation not permitted` (openai/codex #7071, #23661). Do not let Codex route around that with `git update-ref` or other plumbing on the shared repo; that defeats the sandbox. Either let Codex leave the tree modified and commit from the controlling agent, or pass `-s danger-full-access` deliberately.

`--print-policy` prints resolved cwd, sandbox policy, and thread config as JSON, no codex touched, exit 0; offline tests check `-w`/`--net` against it. Verify `--net` with curl: `curl -sf --max-time 3 https://example.com` fails to resolve without it, `200` with it.

## Install

```bash
pnpx skills add anateus/mk-skills
ln -sf "$HOME/.agents/skills/delegating-to-codex/scripts/codex-run.mjs" ~/.local/bin/codex-run
```

In development, point the symlink at the checkout's `scripts/codex-run.mjs`. Back up an older `codex-run` (`codex exec` v1): `cp -n ~/.local/bin/codex-run ~/.local/bin/codex-run-v1`.

## Non-goals

No broker, no MCP, no sandbox wrapper beyond `codex app-server`, no review or transfer commands. A thin single-turn driver; orchestration belongs in the caller.

See [references/live-verification.md](references/live-verification.md) for the scenario checklist and observed one-liners.
