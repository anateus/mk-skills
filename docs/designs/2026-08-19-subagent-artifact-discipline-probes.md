# Subagent artifact discipline probes

## Purpose

These probes tested the lifecycle facts used by `hooks/artifact-discipline.js`. Each host ran from a scratch directory with an explicit scratch hook declaration. The probes did not edit live hook settings.

The initial runs still loaded installed plugins. Their parent `Stop` events triggered Superwhisper popups. The artifact hooks did not invoke Superwhisper, and the installed Superwhisper declarations do not register `SubagentStart` or `SubagentStop`. Future probe commands must set these process-local overrides:

```bash
CLAUDE_HOOK=/usr/bin/true claude ...
SUPERWHISPER_CODEX_HOOK=/usr/bin/true codex ...
```

This suppresses Superwhisper only inside the probe process. It does not create disabled markers or change the user's saved integration state.

## Claude Code 2.1.236

### C1: start context and stop fields

The scratch declaration registered `SubagentStart` and `SubagentStop` for `general-purpose`. The start hook returned:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Before finishing, write exactly \"context arrived\" to <scratch>/artifact.md. Then return a one-line summary."
  }
}
```

Observed start input, with volatile paths shortened:

```json
{
  "session_id": "1b8d5ed4-5134-4642-8437-133018b75f1e",
  "transcript_path": "<claude-project>/1b8d5ed4-5134-4642-8437-133018b75f1e.jsonl",
  "cwd": "<scratch>",
  "prompt_id": "56436811-00f9-479a-b272-30c5b060b01b",
  "agent_id": "af5f954c01338c8c9",
  "agent_type": "general-purpose",
  "hook_event_name": "SubagentStart"
}
```

The subagent created the requested 16-byte file containing `context arrived`. Its stop event included `agent_transcript_path`, `last_assistant_message`, and `stop_hook_active: false`.

Decision: use `SubagentStart.additionalContext` for the artifact instruction. No parent tool-input rewrite is needed.

### C2: one continuation

The stop hook returned `decision: "block"` when the first stop had no artifact. Its reason asked the agent to create `<scratch>/artifact.md`.

The hook then received two stop events for the same agent:

```json
{"hook_event_name":"SubagentStop","agent_id":"a5876c0dba051b71a","agent_type":"general-purpose","stop_hook_active":false,"last_assistant_message":"6"}
{"hook_event_name":"SubagentStop","agent_id":"a5876c0dba051b71a","agent_type":"general-purpose","stop_hook_active":true,"last_assistant_message":"Done. Written \"block resumed\" to <scratch>/artifact.md."}
```

The second turn created the requested file. The subagent then stopped.

Decision: a block resumes the subagent. The production hook must check `stop_hook_active` and must never block the second stop.

### Settings isolation

The probes used `--setting-sources '' --settings <scratch-settings>`. An isolated invocation left `~/.claude/settings.json` at SHA-256 `d1879497240506709b62bbf799d4f610272b469d5f01d09b095454d50d13b628` before and after the check.

### C3: production runner

The final Claude probe registered the repository's `hooks/artifact-discipline.js`, set `CLAUDE_HOOK=/usr/bin/true`, and asked one subagent to calculate `11+12`. The parent returned `23`. The shared runner wrote the same two bytes to:

```text
<scratch>/shared-artifacts/be51277e-9653-4a4b-926a-716a28352cb3/ad5aa5614f662864e/findings.md
```

The process-local override replaced the installed Superwhisper app hook binary with `/usr/bin/true` during this probe.

## Codex CLI 0.148.0

### X1: shared lifecycle runner

The probe used a project-local scratch `.codex/hooks.json` and `--dangerously-bypass-hook-trust` for that vetted invocation. It did not modify `~/.codex/hooks.json` or `~/.codex/config.toml`.

Observed start input, with volatile paths shortened:

```json
{
  "session_id": "01a01c65-40b6-7321-bf1d-80f4fba1b77b",
  "turn_id": "01a01c65-5a4b-7721-b28e-d7cfe32d9aa4",
  "transcript_path": "<codex-session>/subagent.jsonl",
  "cwd": "<scratch>",
  "hook_event_name": "SubagentStart",
  "model": "gpt-5.6-luna",
  "permission_mode": "bypassPermissions",
  "agent_id": "01a01c65-5a27-7463-98d6-8b9f5e8f4186",
  "agent_type": "default"
}
```

Observed stop input:

```json
{
  "session_id": "01a01c65-40b6-7321-bf1d-80f4fba1b77b",
  "turn_id": "01a01c65-5a4b-7721-b28e-d7cfe32d9aa4",
  "cwd": "<scratch>",
  "hook_event_name": "SubagentStop",
  "model": "gpt-5.6-luna",
  "permission_mode": "bypassPermissions",
  "stop_hook_active": false,
  "agent_id": "01a01c65-5a27-7463-98d6-8b9f5e8f4186",
  "agent_type": "default",
  "last_assistant_message": "17"
}
```

The shared runner wrote `17` to:

```text
<scratch>/artifacts/<session_id>/<agent_id>/findings.md
```

Decision: Codex and Claude Code can share the same event parser, output envelopes, path derivation, fallback storage, and single-continuation guard. Host declarations differ only in their plugin-root environment variable.

## Rejected design

The original design rewrote the parent `Agent` input and scanned the subagent transcript for write-tool markers. Both hosts now expose direct start context and final-message fields. The transcript scan also answered the wrong question: any code edit could satisfy it without producing a findings artifact. The implementation checks the exact artifact and uses the documented final response as its fallback.
