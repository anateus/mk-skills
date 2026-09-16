---
name: reviewing-code
description: Review a fixed diff, patch, pull request, commit range, or completed implementation for correctness, risk, requirements, repository standards, and test adequacy.
---

# Reviewing Code

Review a stable change, not a moving target. Establish a fixed comparison point and record diff provenance: repository, base and head revisions or equivalent snapshots, working-tree inclusion, and any generated content excluded from inspection. Accept an optional specification when one exists.

Use Git's changed-file inventory as the coverage baseline, including deletions and renames. Read [diff provenance](references/diff-provenance.md) for coverage bookkeeping and preparing committed, PR, working-tree, or mixed comparisons.

When using a review engine, GitHub diff loader, or live review UI, read [tool-assisted reviews](references/tool-assisted-reviews.md).

## Review axes

Inspect each axis separately so one kind of confidence does not hide another:

1. **Correctness and risk:** trace changed behavior, boundary conditions, failures, security, data integrity, compatibility, and test adequacy.

   When a change alters guards, enablement, or empty/default results, trace the affected state through an existing consumer to its operational consequence, including consumers outside the repository. Check both the whole dataset and individual clients or partitions. Treat new test expectations as claims to validate against that consumer contract. Before recommending that a check be weakened, identify the invariant it protects and where that invariant will be enforced afterward.
2. **Specification compliance:** when a specification exists, map requirements and non-goals to the diff and evidence. Distinguish missing behavior from a flawed implementation.
3. **Repository standards:** apply documented local conventions, architecture, tooling, and maintainability expectations.
4. **Executed behavior:** when the change is runnable, run it: the focused tests and the real code path with realistic input. Results reported by the implementer, a subagent, or a CI comment are claims to check, not evidence.

Read enough surrounding code to validate assumptions. Prefer concrete execution paths and evidence over style speculation. Confirm the comparison point remains fixed before reporting.

After a fix, compare prior findings with the fix diff and check nearby effects. Broaden review when contracts change or evidence exposes a wider problem. Record both the original comparison and fix range; unresolved defects remain open regardless of how many rounds have elapsed. Reopen affected coverage when code or the comparison base changes, and revisit findings that depend on it. A finding disappearing from a later report does not establish a fix.

## Scale the topology

A small, low-risk diff can be reviewed in one pass. Use independent or parallel passes only when diff size or risk makes separation valuable. Peers are optional; partition by axis or non-overlapping area and give each reviewer the same provenance. Peer reports require primary agent verification against the actual diff before becoming findings.

## Report

Lead with actionable findings ordered by severity. Each finding identifies location, observed problem, impact, evidence, and a proportionate remedy. Separate blocking defects from risks and minor improvements. Then summarize reviewed scope, verification performed, residual uncertainty, and explicitly state when no findings were found. Report coverage gaps and failed review work separately from code findings.
