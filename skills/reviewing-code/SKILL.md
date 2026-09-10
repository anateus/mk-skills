---
name: reviewing-code
description: Review a fixed diff, patch, pull request, commit range, or completed implementation for correctness, risk, requirements, repository standards, and test adequacy.
---

# Reviewing Code

Review a stable change, not a moving target. Establish a fixed comparison point and record diff provenance: repository, base and head revisions or equivalent snapshots, working-tree inclusion, and any generated content excluded from inspection. Accept an optional specification when one exists.

For a committed range, run `"<skill-base-dir>/scripts/review-package" BASE HEAD`; it writes a complete package under `${TMPDIR:-/tmp}` and prints only its path. The package covers committed `BASE..HEAD` only. Read [diff provenance](references/diff-provenance.md) when the review includes staged, unstaged, untracked, generated, or mixed state.

## Review axes

Inspect each axis separately so one kind of confidence does not hide another:

1. **Correctness and risk:** trace changed behavior, boundary conditions, failures, security, data integrity, compatibility, and test adequacy.
2. **Specification compliance:** when a specification exists, map requirements and non-goals to the diff and evidence. Distinguish missing behavior from a flawed implementation.
3. **Repository standards:** apply documented local conventions, architecture, tooling, and maintainability expectations.
4. **Executed behavior:** when the change is runnable, run it: the focused tests and the real code path with realistic input. Results reported by the implementer, a subagent, or a CI comment are claims to check, not evidence.

Read enough surrounding code to validate assumptions. Prefer concrete execution paths and evidence over style speculation. Confirm the comparison point remains fixed before reporting.

After a fix, compare prior findings with the fix diff and check nearby effects. Broaden review when contracts change or evidence exposes a wider problem. Record both the original comparison and fix range; unresolved defects remain open regardless of how many rounds have elapsed.

## Scale the topology

A small, low-risk diff can be reviewed in one pass. Use independent or parallel passes only when diff size or risk makes separation valuable. Peers are optional; partition by axis or non-overlapping area and give each reviewer the same provenance. Peer reports require primary agent verification against the actual diff before becoming findings.

## Report

Lead with actionable findings ordered by severity. Each finding identifies location, observed problem, impact, evidence, and a proportionate remedy. Separate blocking defects from risks and minor improvements. Then summarize reviewed scope, verification performed, residual uncertainty, and explicitly state when no findings were found.
