# Subagent artifact discipline implementation plan

> **Feature:** Shared Claude Code and Codex subagent artifact discipline
>
> **Goal:** Preserve each subagent's useful result in a predictable file without changing tool permissions or reading unstable transcript formats.
>
> **Runtime:** Node.js 20+ standard library, Claude Code hooks, and Codex hooks.

## Review outcome

The original plan had sound safety constraints: fail open on hook defects, prevent stop loops, keep artifacts outside the working tree, test malformed events, and validate behavior in real hosts. Its proposed mechanism was too indirect and one capability claim had expired.

The review found six material issues:

1. Claude Code and Codex both support `SubagentStart.additionalContext`. Rewriting a parent dispatch through `PreToolUse` is unnecessary.
2. Both hosts require `permissionDecision: "allow"` when `updatedInput` is returned. The original plan prohibited changing normal permission flow, so its `PreToolUse` design could not meet both requirements.
3. Scanning a transcript for any `Write` or `Edit` call does not prove that findings reached the requested artifact. An implementation agent can edit code and still omit its report.
4. Read-only subagents may not have a file-writing tool. Blocking them for failing an impossible instruction wastes a turn and can still lose the result.
5. A path derived from session ID and prompt hash collides when the same prompt is dispatched twice. `agent_id` already identifies the lifecycle instance.
6. Current Codex has `SubagentStart` and `SubagentStop`. The original Claude-only scope is outdated.

The implementation uses the shared lifecycle surface:

- `SubagentStart` creates a private artifact directory and injects the exact path through `additionalContext`.
- `SubagentStop` checks that exact file. If the agent could not write it, the hook stores `last_assistant_message` as a fallback.
- A first stop with neither an artifact nor a final message is blocked once. A repeated stop always exits and records a diagnostic placeholder when storage is available.

This removes prompt rewriting, permission changes, marker files, transcript parsing, scan budgets, and transcript-flush timing from the correctness path.

## Capability evidence

### Claude Code

Verified on 2026-08-19 with Claude Code 2.1.236 in a scratch directory:

| Capability | Result | Evidence |
|---|---|---|
| `SubagentStart` receives `session_id`, `agent_id`, and `agent_type` | Confirmed | Probe C1 hook input |
| `SubagentStart.additionalContext` reaches the subagent | Confirmed | Probe C1 caused the agent to create the instructed file |
| `SubagentStop` receives `last_assistant_message` and `stop_hook_active` | Confirmed | Probe C1 and C2 hook inputs |
| Blocking `SubagentStop` resumes the subagent once | Confirmed | Probe C2 produced a second event with `stop_hook_active: true` |
| Scratch settings leave `~/.claude/settings.json` unchanged | Confirmed | SHA-256 remained `d1879497240506709b62bbf799d4f610272b469d5f01d09b095454d50d13b628` across the isolated invocation check |

### Codex

Codex CLI 0.148.0 is installed locally. Current [official Codex hook documentation](https://learn.chatgpt.com/docs/hooks) specifies the same fields and output shapes for `SubagentStart` and `SubagentStop`, including `agent_id`, `additionalContext`, `last_assistant_message`, `stop_hook_active`, and `decision: "block"` continuation. Probe X1 confirmed the local wire format and fallback artifact path.

Raw redacted inputs and commands belong in `docs/designs/2026-08-19-subagent-artifact-discipline-probes.md`.

Installed plugins remain active even when the target hook declaration comes from scratch settings. Probe commands must set `CLAUDE_HOOK=/usr/bin/true` and `SUPERWHISPER_CODEX_HOOK=/usr/bin/true` so the installed Superwhisper parent `Stop` hooks cannot open voice UI. These overrides apply only to the probe process and do not change the user's saved Superwhisper state.

## Behavior contract

### Artifact path

Default path:

```text
${TMPDIR}/mk-skills/agent-artifacts/<session_id>/<agent_id>/findings.md
```

`MK_SKILLS_ARTIFACT_DIR` replaces the root and must be absolute. `session_id` and `agent_id` must match a conservative identifier grammar before either enters a path. Invalid input fails open without touching the file system.

The hook creates only the parent directory at `SubagentStart`, with private permissions where supported. Different agents in one session always receive different paths.

### Start behavior

For a valid `SubagentStart` event, the shared runner returns `hookSpecificOutput.hookEventName: "SubagentStart"` and `additionalContext` that:

- names the exact artifact path;
- asks for detailed findings there when the agent has a writing tool;
- asks for full findings in the final response when it cannot write;
- asks for a short final summary that names the artifact path.

No tool permission is granted, denied, or changed.

### Stop behavior

Checks run in this order:

1. If `MK_SKILLS_ARTIFACT_DISCIPLINE=off`, allow without file-system access.
2. Validate the event and derive the path from lifecycle identifiers, never `agent_transcript_path`.
3. If the path is a non-empty regular file, allow.
4. If `last_assistant_message` is non-empty, atomically persist it to the artifact path and allow.
5. If this is the first stop, return `decision: "block"` with a short reason asking for findings in the file or final response.
6. If `stop_hook_active` is true, never block again. Write a diagnostic placeholder when possible, then allow.

Storage failures, malformed JSON, invalid identifiers, invalid roots, unsupported events, and unexpected file types fail open with a concise diagnostic. The runner never reads a transcript or a path supplied through `agent_transcript_path`.

### Limits and opt-out

Fallback content has a configured UTF-8 byte limit and carries a truncation marker when needed. Hook stdin also has a fixed byte ceiling. Exceeding either limit cannot block shutdown.

`MK_SKILLS_ARTIFACT_DISCIPLINE=off` disables both lifecycle halves in both hosts.

Artifacts are session scratch data. The plugin does not delete them automatically. Users who need cross-session retention can set `MK_SKILLS_ARTIFACT_DIR` to a managed absolute directory.

## File map

### Create

| Path | Purpose |
|---|---|
| `hooks/artifact-discipline.js` | Plugin entrypoint for the shared runtime. |
| `skills/subagent-artifact-discipline/scripts/artifact-discipline.js` | Bounded stdin reader and shared event router. |
| `skills/subagent-artifact-discipline/lib/artifact-discipline.js` | Path derivation, context rendering, artifact inspection, and atomic fallback writes. |
| `skills/subagent-artifact-discipline/config/artifact-discipline.json` | Root subdirectory, filename, byte ceilings, and prompt text. |
| `skills/subagent-artifact-discipline/scripts/install-hooks.sh` | One-time Claude Code and Codex hook installer. |
| `skills/subagent-artifact-discipline/tests/test-install-hooks.sh` | Installer ownership, idempotence, and preservation checks. |
| `tests/hooks/artifact-discipline.test.js` | Public hook behavior and direct storage checks for both host envelopes. |
| `docs/designs/2026-08-19-subagent-artifact-discipline-probes.md` | Durable Claude and Codex probe evidence. |

### Modify

| Path | Change |
|---|---|
| `hooks/hooks.json` | Register Codex `SubagentStart` and `SubagentStop` through `${PLUGIN_ROOT}`. |
| `adapters/claude/hooks.json` | Register Claude `SubagentStart` and `SubagentStop` through `${CLAUDE_PLUGIN_ROOT}`. |
| `README.md` | Document shared behavior, installation, updates, opt-out, root override, fallback, retention, and review-before-trust. |
| `tests/hooks/claude-adapter.test.js` | Pin both declarations and shared lifecycle parity. |
| `scripts/validate.js` | Run the standalone hook installer test. |

### Leave unchanged

- `hooks/run-hook.js`, `lib/mode-policy.js`, and their existing tests
- Existing mode-selection code and tests

## Test-first slices

### Slice 1: path and start context

Tests must prove:

- stable path for one session and agent;
- distinct paths for two agents in one session;
- absolute override handling;
- rejection of relative roots and unsafe identifiers;
- context contains the derived path and both write-capable and read-only instructions;
- opt-out and malformed events produce no injection;
- only the artifact parent directory is created;
- Claude and Codex receive the same output envelope.

### Slice 2: stop persistence

Tests must prove:

- an existing non-empty regular artifact passes unchanged;
- a missing or empty artifact receives `last_assistant_message` atomically;
- fallback limits truncate on a UTF-8 boundary and mark truncation;
- an empty first response blocks once with the exact path;
- `stop_hook_active: true` never blocks and records a placeholder when possible;
- malformed input, invalid paths, and storage failures allow the stop;
- `agent_transcript_path` is never opened;
- opt-out performs no file-system writes.

### Slice 3: host integration and documentation

- Register both events in both declarations.
- Record Claude Probes C1 and C2 and a Codex scratch probe.
- Update `README.md`. Scope the old statement to mode selection: it does not inspect transcripts, and artifact discipline does not need to.
- Pin declaration parity in tests.

### Slice 4: skills CLI installation and updates

- Package the runner, library, and configuration in an installable skill.
- Add an idempotent installer that owns only its two lifecycle entries and host links.
- Point each host at a stable path under the installed skill so `pnpx skills update -g` replaces runtime code without rewriting host configuration.
- Preserve unrelated hook entries and back up configuration only when content changes.
- Require a new host session after updates and a Codex `/hooks` review when the hook hash changes.

## Verification

- Run the new test file alone after each slice.
- Mutate the single-block guard and confirm its test fails.
- Mutate path separation so two agents collide and confirm its test fails.
- Mutate fallback handling so an empty file counts as complete and confirm its test fails.
- Run scratch end-to-end probes in Claude Code and Codex without modifying live host settings. Override installed Superwhisper hook commands with `/usr/bin/true` for the probe processes.
- Run `node scripts/validate.js` after all changes.
- Compare the Node hook and skill test count with the pre-change baseline of 55.
- Re-read modified documents and scan them for em and en dashes.
- Run `git diff --check` and inspect the complete final diff.

## Residual risks

1. A read-only agent's fallback contains only its final response. The injected context asks for full findings there, but no hook can recover content the agent omitted.
2. A storage failure degrades to the normal host result path. Fail-open behavior prevents a hook defect from trapping an agent.
3. Temp artifacts need external cleanup. Automatic deletion would conflict with the parent's need to read them after completion.
4. Host hook schemas can change. Tests pin the shared envelope, while the probe document records versions that established runtime behavior.

## Implementation record

- The public runner tests started red because `hooks/artifact-discipline.js` was absent, then passed after the shared implementation.
- Removing the single-continuation guard failed the active-stop test.
- Collapsing agent paths failed the distinct-agent test.
- Treating an empty artifact as complete failed the fallback test.
- `node scripts/validate.js` passed all repository-owned checks.
- The Node hook and skill suite increased from 55 passing tests before implementation to 69 passing tests after implementation.
- The optional plugin schema validator was unavailable because the local Python environment lacks PyYAML. JSON parsing and declaration behavior tests passed.
- Scratch end-to-end runs of the production runner persisted `23` for Claude Code 2.1.236 and `17` for Codex CLI 0.148.0.
- The final Claude probe used `CLAUDE_HOOK=/usr/bin/true`, which isolated Superwhisper without changing its saved enabled state.
- The standalone installer test passed for Claude Code and Codex, including idempotent reinstall and ownership-scoped uninstall.
- A global skills installation needs one installer run. Later `pnpx skills update -g` refreshes the linked runtime for both hosts.
- Existing installations must add the new skill once because `skills update` does not install newly discovered skills.
- Plugin and standalone hook wiring are alternatives. Enabling both duplicates lifecycle invocations.
