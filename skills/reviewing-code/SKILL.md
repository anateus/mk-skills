---
name: reviewing-code
description: Review code changes (diffs, patches, pull requests, commits, or completed implementations) for correctness, risk, design, maintainability, requirements, repository standards, and test adequacy. Also use for a separate, fresh-context comprehension and implementation-readiness review of consequential specifications or plans.
---

# Reviewing Code

For code reviews, record repository, comparison, revisions/snapshots, working-tree state, and excluded generated content.
For consequential spec/plan critiques, consider [artifact readiness](references/artifact-readiness.md) even without a diff.

Track every changed Git path, including deletions and renames. Read [diff provenance](references/diff-provenance.md) for coverage and committed, PR, working-tree, or mixed comparisons.

For repeatable GitHub capture, read [PR preparation](references/pr-preparation.md).

When using a review engine, GitHub diff loader, or live review UI, read [tool-assisted reviews](references/tool-assisted-reviews.md).

## Review axes

Inspect each axis separately so one kind of confidence does not hide another:

1. **Correctness and risk:** trace behavior, boundaries, failures, security, integrity, compatibility, and tests. For nonlocal safety assumptions, use [cross-boundary safety checks](references/cross-boundary-safety.md).

   For guards, gates, triggers, skips, or empty/default results, exercise the actual consumer decision: invalid work stays blocked and valid work proceeds, including external consumers. An approved green PR must remain mergeable after a same-SHA body edit; successful check metadata doesn't prove merge eligibility. Check whole datasets and individual clients or partitions. Validate new test expectations against the consumer contract. Before weakening a check, identify its invariant and where enforcement will move.
2. **Specification compliance:** when a specification exists, map requirements and non-goals to the diff and evidence. Distinguish missing behavior from a flawed implementation.
3. **Repository standards:** find `CODING_STANDARDS.md`, `CONTRIBUTING.md`, and equivalent guidance. Apply relevant conventions, architecture, tooling, and maintainability expectations.
4. **Design and maintainability:** seek behavior-preserving simplification, canonical ownership, useful abstractions, explicit contracts, and sound orchestration. For changed code, apply [design checks](references/design-review.md), even when tests pass.
5. **Executed behavior:** when the change is runnable, run it: the focused tests and the real code path with realistic input. Results reported by the implementer, a subagent, or a CI comment are claims to check, not evidence.

Read surrounding code to validate assumptions. Prefer executed paths and evidence over style speculation. Confirm the comparison point remains fixed before reporting.

For rollbacks, verify current retained behavior, not historical byte equality. Trace retained tests and manifest entries through discovery, filtering, scheduling, and enforcement, including later additions. Exercise target-only changes: restored filters can retain mutation entries while skipping their runner.

After a fix, compare prior findings with the fix diff and check nearby effects. Broaden review when contracts change or evidence exposes a wider problem. Record both the original comparison and fix range; unresolved defects remain open regardless of how many rounds have elapsed. Reopen affected coverage when code or the comparison base changes, and revisit findings that depend on it. A finding disappearing from a later report does not establish a fix.

## Scale the topology

Scale passes to size and risk. Optional peers can own axes or non-overlapping areas with shared provenance; verify their findings against the actual diff.

## Report

Lead with actionable findings ordered by severity. Each finding identifies location, observed problem, impact, evidence, and a proportionate remedy. Separate blocking defects from risks and minor improvements. Then summarize reviewed scope, verification performed, residual uncertainty, and explicitly state when no findings were found. Report coverage gaps and failed review work separately from code findings.
