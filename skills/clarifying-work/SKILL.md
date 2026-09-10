---
name: clarifying-work
description: Resolve consequential uncertainty from evidence. Use for ambiguous or integration-heavy work, or tracker tickets whose unresolved choices could cause substantial rework.
---

# Clarifying Work

Reduce consequential uncertainty before choosing a solution. Scale the effort to rework risk: a clear local edit may need no questions, while a cross-system change may need an integration map.

## Clarify from evidence

1. Inspect the repository, documentation, configuration, and established conversation to discover facts locally.
2. Separate known facts, reasonable inferences, and unresolved choices.
3. Rank uncertainties by how much a wrong assumption would change scope, architecture, safety, or acceptance.
4. Use a stated reversible assumption for low-risk gaps. Ask only about material choices evidence cannot resolve. Group independent questions; wait for prerequisites before asking dependent ones.

Do not turn clarification into a generic interview or ask for facts available in the workspace.

For empirical uncertainty, run the smallest reversible feasibility probe within the task's authority. Label temporary artifacts and report what the probe establishes. A feasibility question does not authorize shipping a prototype.

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

Report what the evidence settled and any decision still needed. Preserve the user's scope.

When the request is understood but a proposed direction remains insufficiently challenged, use `adversarial-refinement`; do not keep inventing clarification questions.
