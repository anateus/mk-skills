# Challenge lenses

Use these prompts selectively. Prefer the few lenses most likely to change the decision.

## Universal decision lenses

- Which claim carries the decision, and what evidence could falsify it?
- What constraint is being treated as fixed without proof?
- What is the strongest materially different alternative, and when would it win?
- Can the choice be reversed cheaply? What option value is lost now?

## Product and user behavior

- Which users benefit, which absorb the cost, and whose behavior is assumed?
- What misuse, abandonment, accessibility, or migration path is missing?
- Does the metric reward the intended outcome or a proxy that can be gamed?

## Specifications and interfaces

- Are boundary conditions, errors, compatibility, ordering, and idempotency explicit?
- Can two conforming implementations behave incompatibly?
- Which acceptance criterion cannot be observed at a public seam?

## Architecture, data, security, and operations

- Where are trust boundaries, data ownership, consistency, and failure isolation unclear?
- What happens during partial failure, retry, overload, or dependency degradation?
- What sensitive data, privilege, audit, retention, or recovery obligation is implicit?

## Plans, rollout, and rollback

- Which dependency or sequencing assumption could invalidate later work?
- What proves each slice independently useful and safe to advance?
- Is rollback real after schema, data, protocol, or user-behavior changes?

## Diagnoses and competing hypotheses

- What observation distinguishes the leading hypotheses?
- Which evidence was collected after the suspected cause was proposed?
- What simpler cause or shared upstream factor explains more symptoms?
