---
name: verifying-work
description: Tie completion and readiness claims to direct evidence. Use when asked to verify, test, confirm, or double-check, and before claiming work is correct, complete, passing, or clean.
---

# Verifying Work

Map each completion claim to fresh, relevant evidence before stating it as fact.

## Verification gate

1. List the claims the handoff or response will make.
2. Choose evidence that directly proves each claim: the focused behavior test for a fix, the affected suite for regressions, a build for buildability, or inspection for an artifact property.
3. Run the command or inspection and read its full result, exit status, failures, warnings, and scope. Reuse your directly inspected evidence from this work when relevant code, inputs, configuration, and environment are unchanged, unless current instructions require a new run.
4. Compare the observed result with the claim. A peer report, stale output, nearby check, or confidence cannot substitute for your direct check.
5. State only what the evidence supports, including relevant limitations and unverified areas.

Scale breadth to impact, but never scale away the direct check. If verification cannot run, report the blocker and narrow the claim instead of predicting success.

Evidence expires when code, inputs, configuration, or environment relevant to the claim changes. Re-run the affected check after such changes.

## Sweep integrity

A check that cannot fail is not evidence. Before claiming a custom search found nothing, prove detection with a disposable positive fixture exercising the same search boundary. Never plant data in the real corpus. Check errors and enumerate all occurrences. Run an available end-to-end check instead of deferring it to a manual step.
