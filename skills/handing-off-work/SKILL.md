---
name: handing-off-work
description: Create a concise, redacted, resumable transfer that references durable artifacts and distinguishes verified facts from remaining work. Use when work must move to another session, agent, or collaborator, whether unfinished or complete.
---

# Handing Off Work

Create a temporary summary that lets the next worker resume without reconstructing the session. Treat it as a navigation aid, not a second source of truth.

## Build the handoff

Write to an appropriate temporary location. Include what the next worker needs from:

- **Current state:** scope, branch or workspace identity when relevant, and what has changed.
- **Remaining work:** ordered next actions with dependencies and expected outcomes.
- **Verified facts:** commands or inspections run, results, and when they were observed.
- **Blockers:** missing authority, information, access, failing checks, or unresolved decisions.
- **Suggested skills:** only workflows likely to help with the next actions.

Link to durable specifications, plans, issues, commits, diffs, logs, and source paths. Avoid duplicating their contents. Use stable identifiers and record whether referenced working-tree state is uncommitted or may move.

## Safety and accuracy

Redact secrets, credentials, tokens, personal data, and unnecessary environment details. Do not copy sensitive command output merely for completeness. Distinguish direct observations from inferences and stale results. If peer work contributed, identify its scope and the primary verification performed; peer completion reports are not independent evidence.

Keep the handoff concise and disposable. Durable decisions belong in the project's established artifacts, not only in the temporary file.

For generated deliverables, include the generator and command needed to reproduce them. Other artifacts need a durable, accessible copy and enough context to continue.
