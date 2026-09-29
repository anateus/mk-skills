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

Synthesis and subagent handoff must not strengthen evidence. Carry reviewer caveats and open verification gaps forward until a direct check resolves each one. Distinguish a producer emitting success from a consumer accepting it, such as successful checks versus branch protection permitting a merge. A coordinator must not label acceptance as verified or acceptance-aligned from a weaker proxy; retain the narrower result and unresolved consumer check.

## Regression protection

When claiming regression protection, trace the check from its source and generated artifacts through the documented command, test discovery, and CI selection. Run the real entrypoint from committed inputs. A directly executed test doesn't establish that the normal workflow selects it. Required checks should fail visibly when their script, bundle, or prerequisites are missing.

For configuration changes, exercise the committed configuration or its rendered output against the consumer contract. A synthetic fixture establishes only the behavior represented by that fixture. Check relevant environment inputs and workflow path filters so production configuration can't change outside the claimed coverage.

## Sweep integrity

A check that cannot fail is not evidence. Before claiming a custom search found nothing, prove detection with a disposable positive fixture exercising the same search boundary. Never plant data in the real corpus. Check errors and enumerate all occurrences. Run an available end-to-end check instead of deferring it to a manual step.
