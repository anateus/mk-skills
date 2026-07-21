---
name: implementing-work
description: Route and implement approved or sufficiently clear changes in an existing codebase as coherent, verified slices. Use when the user asks to add, build, change, fix, or implement behavior from a request, specification, plan, or review feedback.
---

# Implementing Work

Route the work through the smallest set of applicable skills, then deliver coherent slices. The request, specification, or plan defines the intended outcome; repository evidence defines how it fits.

## Route and execute

1. Confirm the active scope, acceptance conditions, local guidance, and existing working-tree state. Resolve only ambiguities that materially change the result.
2. Choose the smallest applicable set: `clarifying-work` for consequential unresolved choices; `specifying-work` when agreed behavior needs a reviewable contract; `planning-work` for dependent multi-step work; `adversarial-refinement` when a consequential proposal needs pressure-testing; `test-driven-development` for observable behavior seams; `diagnosing-bugs` while a cause is unknown; `verifying-work` before completion claims; and `reviewing-code` when risk warrants a bounded review. Naming these routes does not require loading all of them.
3. Implement in coherent slices that connect behavior, code, and evidence. Preserve unrelated changes and established interfaces unless the requested outcome changes them.
4. Scale verification to risk. Run focused checks after each slice and broader affected checks before completion; map claims to fresh evidence.
5. Scale review to risk. Small mechanical changes may need only self-review, while broad, security-sensitive, or integration-heavy changes benefit from an independent review when available.

If evidence invalidates the plan, update the route rather than forcing the planned edit. Report material deviations and unresolved limitations.

## Ownership boundary

This skill does not own external lifecycle state. Commits, pull requests, trackers, worktrees, releases, and peer execution follow explicit user or repository policy. Their presence does not replace implementation verification.

## Outcome

Return the slices completed, material decisions or deviations, files affected, and verification evidence. Identify remaining work precisely rather than broadening scope to absorb it.
