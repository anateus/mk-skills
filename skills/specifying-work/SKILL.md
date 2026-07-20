---
name: specifying-work
description: Use when agreed intent needs a concise, reviewable behavior contract before implementation or planning.
---

# Specifying Work

Synthesize established intent and repository evidence into a contract. Do not replay the conversation or restart discovery as an interview.

## Specification shape

Write the smallest useful specification with:

- **Problem:** who or what is affected, and why the current state is insufficient.
- **Behavior:** externally observable outcomes, including important failure behavior.
- **Constraints:** compatibility, security, performance, dependency, and operational boundaries that actually apply.
- **Acceptance criteria:** concrete, independently checkable statements.
- **Seams:** public behavior or integration boundaries where acceptance can be tested and verified.
- **Non-goals:** nearby work deliberately outside scope.

Name assumptions and unresolved choices rather than hiding them in implementation detail. Include an integration map from clarification when it affects the contract; otherwise keep the specification direct.

## Approval threshold

Seek approval when material unresolved choices would change scope, architecture, externally visible behavior, or irreversible work. If prior discussion already resolved those choices, present the synthesis for review and proceed according to the request. Editorial preferences and discoverable implementation facts do not create an approval gate.

## Quality check

The specification is ready when a planner can identify what changes, what stays stable, where behavior can be observed, and how each acceptance criterion will be judged without guessing at user intent.

