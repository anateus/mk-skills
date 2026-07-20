---
name: planning-work
description: Use when a reviewed request or specification needs an executable implementation sequence grounded in an existing codebase.
---

# Planning Work

Build a codebase-grounded route from current behavior to verified behavior. Inspect before naming exact paths, interfaces, or commands.

## Plan vertical slices

Prefer narrow vertical tracer-bullet slices that deliver an observable thread through the system. Each slice should leave the workspace coherent and make the next uncertainty cheaper.

For every slice state:

- the outcome and acceptance criterion it advances;
- owned files or components, based on repository evidence;
- dependencies and ordering constraints;
- expected outputs, including behavior and durable artifacts;
- verification that demonstrates the outcome with a specific command or inspection.

Put discovery or contract-proving slices before work that depends on their result. Call out coordination points, shared files, migrations, rollout concerns, and rollback needs only when applicable. Keep tests beside the behavior they establish rather than in a final testing phase.

## Executable topology

Write boundaries that are peer-ready: a reader can execute a slice from its inputs, expected outputs, and verification without reconstructing hidden context. The same plan must remain executable inline by one agent.

Zellij and peers remain optional execution choices. Suggest peer execution only when slices are independent, ownership is non-overlapping, and coordination cost is justified. Peer-ready wording does not imply dispatch, and peer results still require verification by the responsible agent.

Tracker publication, commits, branches, and worktrees belong to repository or user policy, not the core plan format.

## Final check

Confirm that dependencies form a valid order, every acceptance criterion has coverage, risky assumptions are surfaced early, and completion claims map to fresh evidence.
