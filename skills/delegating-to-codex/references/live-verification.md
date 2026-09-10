# Live verification checklist

Ten scenarios run against a real `codex app-server` (codex-cli 0.154.0, model
`gpt-5.6-luna`, logged in) to confirm codex-run actually drives the protocol
correctly, not just that it parses flags. Each scenario was also run alone
(not only as part of a batch), since job files and thread state persist
between runs. Re-run this checklist after any change to `scripts/codex-run.mjs`
that touches turn handling, sandbox policy, or job bookkeeping.

Setup:

```bash
git init /tmp/cr-test && cd /tmp/cr-test
echo hi > a.txt && git add -A && git commit -qm init
```

## 1. Foreground read-only

```bash
codex-run -C /tmp/cr-test -s read-only -p p1.md -o out1.md   # p1.md: "Reply with exactly the word PONG and nothing else."
```

Observed: `exit=0 session=01a08d1b-9f32-7c93-a617-31be283e11bd out=out1.md log=out1.log job=cr-20260910-2615df status=completed`. `out1.md` contained `PONG`. Pass.

## 2. Foreground workspace-write

```bash
codex-run -C /tmp/cr-test -s workspace-write -p p2.md -o out2.md   # p2.md: "Append the line 'from codex' to a.txt, then reply DONE."
```

Observed: `exit=0 session=01a08d1b-bf1f-76e1-ba6a-3f0a16ba4fa6 out=out2.md log=out2.log job=cr-20260910-c003e5 status=completed`. `a.txt` gained the new line; `out2.md` ended in `DONE`. Pass.

## 3. Background + wait

```bash
codex-run -C /tmp/cr-test -s read-only -p p1.md -o out3.md -b   # prints job=... session=pending immediately
codex-run wait cr-20260910-e8fd5e
```

Observed final: `exit=0 session=01a08d1c-0780-7070-b48f-8bb34b2c2a5e out=out3.md log=out3.log job=cr-20260910-e8fd5e status=completed`, same shape as scenario 1. Pass.

## 4. Cancel

```bash
codex-run -C /tmp/cr-test -s workspace-write -p p4.md -o out4.md -b   # p4.md: "Count from 1 to 200, one number per line, running `sleep 1` between each via the shell."
sleep 5
codex-run cancel cr-20260910-38e90c
```

Observed: `exit=130 session=01a08d1c-2bd8-75b2-8123-af9e0c066cb7 out=out4.md log=out4.log job=cr-20260910-38e90c status=interrupted`. Log shows `SIGTERM received, sending turn/interrupt` followed by `turn/completed status=interrupted` within the 15s window. Worker process confirmed gone via `ps` afterward. Pass.

Clean rerun (under `$HOME`, post thread-config fix): `job=cr-20260910-5232ed`, `exit=130`, `status=interrupted`. Same log sequence, `SIGTERM received, sending turn/interrupt` then `turn/completed status=interrupted`; worker process gone afterward. Cancel behavior is unaffected by the sandbox-config change. Pass.

## 5. Resume

```bash
codex-run -C /tmp/cr-test -s read-only -r 01a08d1b-9f32-7c93-a617-31be283e11bd -p p5.md -o out5.md   # p5.md: "What single word did you reply last time? Answer with just that word."
```

Observed: `exit=0 session=01a08d1b-9f32-7c93-a617-31be283e11bd out=out5.md log=out5.log job=cr-20260910-e3d008 status=completed`, same thread id as scenario 1, confirming resume reused the thread rather than starting a new one. `out5.md` contained `PONG`. Pass.

## 6. Worktree git-dir denial (DOM-7702 case)

```bash
git -C /tmp/cr-test worktree add ../cr-wt -b wt
codex-run -C /tmp/cr-wt -s workspace-write -w /tmp/cr-test/.git -p p6.md -o out6.md   # p6.md: "Create b.txt containing 'wt', run `git add b.txt && git commit -m wt`, reply with the new commit hash."
```

Expected: codex denies the `git commit` write to the worktree's private git metadata (`.git/worktrees/wt/index.lock: Operation not permitted`) regardless of the `-w` root, because that protection covers the checkout's own git dir and cannot be granted away. `out6.md` reports the fatal error; the turn itself still finishes normally (`status=completed`, `exit=0`); no new commit lands on `wt`.

Observed (clean rerun under `$HOME`, not `/tmp`, after the thread-level config fix): `exit=0 session=01a08d2e-2774-71f1-8287-57e459cd8c9b out=/Users/mike/.cache/cr6b-geiN/wt/out.md log=/Users/mike/.cache/cr6b-geiN/wt/out.log job=cr-20260910-1300aa status=completed`. The `thread/start` response echoed `writableRoots: ["/Users/mike/.cache/cr6b-geiN/repo/.git"]`, confirming the root now actually reaches the thread, and the commit still failed with `fatal: Unable to create '.../repo/.git/worktrees/wt/index.lock': Operation not permitted`, reported by the agent in `out.md`. No commit was made. Pass, in the sense that codex-run now reports the real, honest failure instead of hanging or silently succeeding.

An earlier run of this scenario looked like a pass only because the agent, once denied the lock file, used `git update-ref` directly against the shared repo's refs to route around the sandbox instead of reporting the failure. That is not behavior codex-run should encourage, and the worktree auto-root feature that made it easy to reach has been removed. This is an upstream codex limitation (openai/codex #7071, #23661), not something fixable from this client; see "Sandbox" in `SKILL.md` for the recommended pattern (let Codex leave the tree modified and commit from the controlling agent, or pass `-s danger-full-access` deliberately).

## 7. Usage and list

```bash
codex-run -o out.md        # no -p
```

Observed: usage text on stderr, `rc=2`. `codex-run list` (no arguments) printed all known jobs, newest first, one line per job (`jobId status threadId cwd startedAt`), including all of the above. Pass.

## 8. Network access (`--net`)

```bash
codex-run -C /tmp/cr-test -s workspace-write -p p8.md -o out8.md         # p8.md: "Run `curl -sf --max-time 3 -o /dev/null -w '%{http_code}' https://example.com` and reply with its output."
codex-run -C /tmp/cr-test -s workspace-write --net -p p8.md -o out8b.md
```

Observed: without `--net`, curl could not resolve the host (`curl: (6) Could not resolve host: example.com`), `job=cr-20260910-a943e3`. With `--net`, the same command returned `200`, `job=cr-20260910-34e606`. Confirms `--net` reaches the thread-level `sandbox_workspace_write.network_access` override, not just the per-turn policy. Pass.

## 9. Permission profile via preset

```bash
codex-run -C /tmp/cr-test --preset github-only -p p9.md -o out9.md   # p9.md: "Run curl against https://example.com, https://api.github.com and https://gitlab.com and report each response code, then try `ls ~/.ssh` and `touch ~/Desktop/perm-probe` and report each result."
```

Observed: `curl -sf --max-time 3 -o /dev/null -w '%{http_code}' https://example.com` returned `curl: (56) CONNECT tunnel failed, response 403` (the managed proxy's domain allowlist denied it); the same command against `https://api.github.com` returned `200`; against `https://gitlab.com` the CONNECT was denied the same way as `example.com`. `ls ~/.ssh` failed with `ls: /Users/mike/.ssh: Operation not permitted`, and the same for `~/.aws`, `~/.zshrc`, `~/.codex`, `~/.claude`, `~/.config/gh`, and `~/Library/Keychains`. `touch ~/Desktop/perm-probe` failed with `touch: /Users/mike/Desktop/perm-probe: Operation not permitted`. A write inside cwd succeeded normally throughout. Codex's own process (the app-server codex-run talks to) kept running the whole time; it is not the sandboxed process, only the commands it runs are. Pass.

Public vs. private git over https under this profile: `git ls-remote https://github.com/openai/codex` and `git clone --depth 1 https://github.com/fencesandbox/fence` both succeed, since public reads need no credentials. Fetching a private repo instead fails with `fatal: could not read Username for 'https://github.com': Device not configured`, because no credential helper is reachable inside the sandbox. That split is expected and by design: public read access over https works from inside Codex under this preset; private fetch/push and any `gh` command are the controlling agent's job, run outside the sandbox, not something to route through it.

## 10. Direct-bypass attempts

```bash
codex-run -C /tmp/cr-test --preset github-only -p p10.md -o out10.md   # p10.md: "Try each of: curl --noproxy '*' https://example.com; env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY curl https://example.com; nc -z example.com 443; ssh -T git@github.com. Report exactly what happens for each."
```

Observed: all four fail to reach the network. `curl --noproxy '*' https://example.com` fails the same way as through the proxy, since Seatbelt only allows the loopback proxy address and bypassing the proxy client-side does not restore DNS. Unsetting `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` before curl produces the same failure, because the proxy is injected at the sandbox level rather than only via env vars a command could unset. `nc -z example.com 443` and `ssh -T git@github.com` both fail with no DNS resolution at all. None of the four reach any network path the domain allowlist did not already grant. Pass: the profile is not bypassable from inside the sandboxed command by any of the obvious tricks.

## nono evaluated, not used

nono was considered as a wrapper around codex-run for the same restriction this preset now gives natively, and is not used today:

- Codex's model client ignores `HTTPS_PROXY` (openai/codex #4242, open), so nono's proxy mode breaks the model call itself, not just the commands it runs.
- Even in nono's filesystem-only mode, Codex's own per-command Seatbelt cannot apply inside nono's Seatbelt: `sandbox-exec: sandbox_apply: Operation not permitted`.
- Under nono, Codex's TLS verifier needs `SSL_CERT_FILE=/etc/ssl/cert.pem` set explicitly, or every HTTPS call fails with `invalid peer certificate: UnknownIssuer`.

nono's filesystem isolation on its own works fine with `-s danger-full-access` (`~/.ssh`, `~/.aws`, `~/.zshrc`, Desktop all denied), but that combination also throws away Codex's own command sandbox and network proxy, which is the whole point of a permission-profile preset. Revisit nono once Codex ships `respect_system_proxy` (listed as under development in `codex features list`).

One nono run is worth flagging on its own, since it shaped how scenario 9 and 10 were written: a model asked to check `example.com` and `github.com` answered `example=200 github=200` with no `commandExecution` item anywhere in that run's `events.jsonl`; it had answered from a `webSearch` item instead of ever running curl. That is why a verification prompt has to demand literal shell output, not just a report of response codes, and why this checklist's pass/fail reads `events.jsonl` item types rather than trusting `out.md` alone.

## Protocol notes confirmed from the wire

Field names relied on in `runTurn()` were checked directly against `events.jsonl` from run 1, not just against the JSON schema:

- `AgentMessageThreadItem`: `.text` holds the reply text directly (no nested `content` array).
- `CommandExecutionThreadItem`: `.command` and `.exitCode` (camelCase), plus `.status`.
- `FileChangeThreadItem`: `.changes[]`, each with `.path`, `.diff`, `.kind`; the item itself has `.status`.
- `Turn`: `.id` and `.status`.
- The wire omits `"jsonrpc":"2.0"` entirely on every frame, despite the protocol otherwise following JSON-RPC 2.0 request/response/notification shape.

No discrepancy between the schema and the live wire was found; nothing in `codex-run.mjs` had to change as a result of this check.
