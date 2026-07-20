---
name: reviewing-code
description: Use when a bounded change needs evidence-based review before it is accepted, handed off, or released.
---

# Reviewing Code

Review a stable change, not a moving target. Establish a fixed comparison point and record diff provenance: repository, base and head revisions or equivalent snapshots, working-tree inclusion, and any generated content excluded from inspection. Accept an optional specification when one exists.

## Review axes

Inspect each axis separately so one kind of confidence does not hide another:

1. **Correctness and risk:** trace changed behavior, boundary conditions, failures, security, data integrity, compatibility, and test adequacy.
2. **Specification compliance:** when a specification exists, map requirements and non-goals to the diff and evidence. Distinguish missing behavior from a flawed implementation.
3. **Repository standards:** apply documented local conventions, architecture, tooling, and maintainability expectations.

Read enough surrounding code to validate assumptions. Prefer concrete execution paths and evidence over style speculation. Confirm the comparison point remains fixed before reporting.

## Scale the topology

A small, low-risk diff can be reviewed in one pass. Use independent or parallel passes only when diff size or risk makes separation valuable. Peers are optional; partition by axis or non-overlapping area and give each reviewer the same provenance. Peer reports require primary agent verification against the actual diff before becoming findings.

## Report

Lead with actionable findings ordered by severity. Each finding identifies location, observed problem, impact, evidence, and a proportionate remedy. Separate blocking defects from risks and minor improvements. Then summarize reviewed scope, verification performed, residual uncertainty, and explicitly state when no findings were found.

