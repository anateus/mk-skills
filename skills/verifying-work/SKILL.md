---
name: verifying-work
description: Map completion and readiness claims to fresh direct evidence, run the relevant checks, and report limitations precisely. Use when asked to verify, check, test, confirm, or prove that work is correct, complete, passing, buildable, or ready. Triggers on "did it work", "make sure it passes", "double-check", "is this done", "confirm the fix", and before any claim that work is verified, passing, or clean.
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

## Sweep integrity

A check that cannot fail is not evidence. A sweep that reports nothing counts only after it detects a planted known positive; typos, unsupported flags, and swallowed errors all read as clean. Enumerate every occurrence rather than judging the first match. When the real end-to-end command is runnable now, run it instead of declaring a later manual step.
