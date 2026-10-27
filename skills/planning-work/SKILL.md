---
name: planning-work
description: Plan executable slices from repository evidence. Use for implementation plans or work with multi-step dependencies, owned boundaries, and verification points.
---

# Planning Work

Build a route from current behavior to verified behavior. Link the originating specification when one exists. Inspect before naming exact paths, interfaces, or commands.

## Plan vertical slices

Prefer narrow vertical tracer-bullet slices that deliver an observable thread through the system. Each slice should leave the workspace coherent and make the next uncertainty cheaper.

Specify the next executable slice precisely. For later slices, record outcomes and dependencies, adding exact edits when their interfaces are known:

- the outcome and acceptance criterion it advances;
- owned files or components, based on repository evidence;
- dependencies and ordering constraints;
- expected outputs, including behavior and durable artifacts;
- verification that demonstrates the outcome with a specific command or inspection.

Put discovery or contract-proving slices before work that depends on their result. Call out coordination points, shared files, migrations, rollout concerns, and rollback needs only when applicable. Keep tests beside the behavior they establish rather than in a final testing phase.

Use a small reversible probe for empirical feasibility questions. For broad compatibility changes, consider expand, migrate, then contract stages so consumers can move without a flag day.

When a consequential change establishes new module, type, or ownership boundaries, sketch the caller's real usage before settling those boundaries. Compare at least two genuinely different shapes and their invariants against existing entrypoints and consumers, then choose a shape whose interface keeps policy with its owner. This is a conditional design aid, not a ritual for every plan. Read [architecture sketch](references/architecture-sketch.md) when these boundaries are uncertain.

## Executable topology

Define boundaries a reader can execute from the recorded inputs, outputs, and verification. Plans remain executable inline. Optional peers or Zellij can handle independent slices with distinct ownership when coordination pays off; dispatch still follows user or repository authority and peer results need primary verification.
When the request asks for a reusable pipeline, coordination across workstreams, or possible agent delegation, you MUST read the [pipeline catalog](references/pipeline-catalog.md) before recommending a sequence or dispatch. Select only applicable steps; catalog entries do not make stages mandatory.

Tracker publication, commits, branches, and worktrees belong to repository or user policy, not the core plan format.

When sequencing, dependency, rollout, or rollback assumptions are materially uncertain, use `adversarial-refinement` on the draft plan.

## Plan artifacts are shipped artifacts

Code blocks, queries, and commands embedded in the plan get executed verbatim by whoever runs the slice. Review them as code: check interpolations and correlation scope, and re-derive embedded numbers, queries, and snippets after any design change. Fix the block itself, not only the surrounding prose.

## Final check

Confirm that dependencies form a valid order, every acceptance criterion has coverage, risky assumptions are surfaced early, and completion claims map to fresh evidence. For consequential plans, check likely omitted user inputs and boundary failures, tying material cases to the slices that own them without inventing requirements.
