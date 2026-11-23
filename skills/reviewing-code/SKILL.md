---
name: reviewing-code
description: Review code changes (diffs, patches, pull requests, commits, or completed implementations) for correctness, risk, design, maintainability, requirements, repository standards, and test adequacy. Also use for a separate, fresh-context comprehension and implementation-readiness review of consequential specifications or plans.
---

# Reviewing Code

For code reviews, record repository, comparison, revisions/snapshots, working-tree state, and excluded generated content.
For consequential spec/plan critiques, consider [artifact readiness](references/artifact-readiness.md) even without a diff.

Track every changed Git path, including deletions and renames. Read [diff provenance](references/diff-provenance.md) for coverage and committed, PR, working-tree, or mixed comparisons.

For repeatable GitHub capture, read [PR preparation](references/pr-preparation.md).

For a review engine, GitHub diff loader, or live review UI, read [tool-assisted reviews](references/tool-assisted-reviews.md).

## Review axes

Inspect each axis separately so confidence in one never hides another:

1. **Correctness and risk:** trace behavior, boundaries, failures, security, integrity, compatibility, and tests. For nonlocal safety assumptions, use [cross-boundary safety checks](references/cross-boundary-safety.md).

For guards, gates, defaults, triggers, skips, and empty results, exercise the actual consumer decision. Verify that invalid work stays blocked and valid work proceeds. Before weakening a check, identify its invariant and where enforcement moves.
2. **Specification compliance:** map an existing specification's requirements and non-goals to the diff and evidence. Distinguish missing behavior from a flawed implementation.
3. **Repository standards:** find `CODING_STANDARDS.md`, `CONTRIBUTING.md`, and equivalent guidance. Apply relevant conventions, architecture, tooling, and maintainability expectations.
4. **Design and maintainability:** seek behavior-preserving simplification, canonical ownership, useful abstractions, explicit contracts, and sound orchestration. Apply [design checks](references/design-review.md) to changed code, even when tests pass.
5. **Executed behavior:** run a runnable change: the focused tests and the real code path with realistic input. Results an implementer, subagent, or CI comment reports are claims, not evidence.

Read surrounding code to validate assumptions. Prefer executed paths and evidence over style speculation. Confirm the comparison point remains fixed before reporting.

For rollbacks, verify retained behavior, not historical byte equality. After a fix, check the original findings and nearby effects. Record the original comparison and fix range; reopen affected coverage when either revision changes. A finding missing from a later report is not thereby fixed.

## Scale the review

Scale passes to size and risk. One careful pass is enough for a small, local, reversible change. For consequential changes, check what depends on the diff and use a fresh, independent reader when available. Read [scaling a review](references/scaling-review.md) before adding reviewers or review rounds. Verify findings against the code, whoever raised them.

## Report

Lead with findings ordered by severity. Give each finding a location, problem, impact, evidence, and proportionate remedy. State what you reviewed, what you verified, and whether you found nothing. Report coverage gaps and failed review work separately.

Call a defect blocking only when you can show a realistic trigger and a material consequence of this change. Reproduce it or trace the path from input to effect. Keep confirmed lesser defects, problems already in the base, and unverified risks separate. A pre-existing defect can still block if this change newly exposes it.

The caller owns merge policy. Neither an empty report nor a severity count establishes safety for unattended merging. See [merge decisions](references/merge-decisions.md) for consequential assessments.
