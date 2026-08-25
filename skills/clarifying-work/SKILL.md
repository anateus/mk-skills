---
name: clarifying-work
description: Reduce consequential uncertainty by inspecting facts, separating assumptions from decisions, and mapping integration risks. Use when a request is ambiguous, integration-heavy, cross-boundary, or likely to hide decisions that could cause substantial rework. Consider whenever drafting or filing a tracker ticket (e.g. Linear), so the ticket records decisions rather than assumptions.
---

# Clarifying Work

Reduce consequential uncertainty before choosing a solution. Scale the effort to rework risk: a clear local edit may need no questions, while a cross-system change may need an integration map.

## Clarify from evidence

1. Inspect the repository, documentation, configuration, and established conversation to discover facts locally.
2. Separate known facts, reasonable inferences, and unresolved choices.
3. Rank uncertainties by how much a wrong assumption would change scope, architecture, safety, or acceptance.
4. Continue with a stated reversible assumption when risk is low. When an answer materially changes the result, ask one material question at a time and explain the decision it unlocks.

Do not turn clarification into a generic interview or ask for facts available in the workspace.

## Integration scan

Check only the dimensions relevant to the request:

- integration consumers and downstream callers;
- failure modes, recovery, and partial success;
- schema propagation, compatibility, and migrations;
- lifecycle, ownership, cleanup, and concurrency;
- authorization, trust boundaries, and sensitive data;
- dependency scope, versioning, and availability;
- configuration, defaults, overrides, and environments;
- edge cases, limits, and unsupported states.

For changes spanning boundaries, produce a compact integration map: affected producers and consumers, contracts that change, state or control flow between them, and open risks. The map is an aid when warranted, not a required artifact.

## Outcome

Return the clarified objective, discovered constraints, material assumptions, and any remaining decision. Preserve the user's intent; clarification narrows uncertainty rather than inventing scope.

When the request is understood but a proposed direction remains insufficiently challenged, use `adversarial-refinement`; do not keep inventing clarification questions.
