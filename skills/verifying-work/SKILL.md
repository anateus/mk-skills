---
name: verifying-work
description: Map completion and readiness claims to fresh direct evidence, run the relevant checks, and report limitations precisely. Use when asked to verify, check, test, confirm, or prove that work is correct, complete, passing, buildable, or ready.
---

# Verifying Work

Map each completion claim to fresh, relevant evidence before stating it as fact.

## Verification gate

1. List the claims the handoff or response will make.
2. Choose evidence that directly proves each claim: the focused behavior test for a fix, the affected suite for regressions, a build for buildability, or inspection for an artifact property.
3. Run the command or inspection now. Read its full result, exit status, failures, warnings, and scope.
4. Compare the observed result with the claim. Do not substitute old output, a peer report, a nearby check, or confidence.
5. State only what the evidence supports, including relevant limitations and unverified areas.

Scale breadth to impact, but never scale away the direct check. If verification cannot run, report the blocker and narrow the claim instead of predicting success.

Evidence expires when code, inputs, configuration, or environment relevant to the claim changes. Re-run the affected check after such changes.
