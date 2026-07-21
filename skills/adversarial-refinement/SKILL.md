---
name: adversarial-refinement
description: Stress-test and improve proposals, decisions, specifications, plans, architectures, and diagnoses using adversarial questions, counterexamples, alternative approaches, and tradeoff analysis. Use when the user asks to grill, challenge, red-team, stress-test, or poke holes in an idea, or when another workflow explicitly requests a pressure test before commitment.
---

# Adversarial Refinement

## Purpose and boundary

Constructively oppose a coherent artifact or decision so its strongest version survives. This skill is optional and risk-scaled: it does not replace discovery, specification, planning, diagnosis, implementation, code review, or user authority. It does not own implementation or external lifecycle actions.

## Choose a mode

- **Interactive grill:** when the user asks to be grilled or challenged. Ask one material question at a time, give a recommended answer and rationale, then wait. Let the user stop or set a challenge budget.
- **Artifact critique:** when another workflow requests a pressure test. Resolve discoverable facts autonomously and return a compact critique; do not manufacture user questions when evidence can settle the issue.

## Refinement loop

1. Establish the artifact and decision under review. Inspect local and other discoverable facts before asking the user.
2. Steelman the current proposal: state its strongest rationale, constraints, and intended benefit before criticism.
3. Prioritize by decision impact. Test assumptions, counterexamples, failure modes, downstream effects, reversibility, opportunity cost, and the strongest materially different alternative.
4. For interactive mode, ask one material question at a time with a recommended answer and rationale. Track what survived, changed, or remains open.
5. For artifact critique, report evidence-backed findings and proposed refinements. Ask only about material choices the environment cannot resolve.
6. Stop when remaining uncertainty is acceptable for the risk, the challenge budget is spent, or the user asks to stop. Do not exhaustively walk every branch.

## Exit and return

Return the refined position, important changes, rejected alternatives, unresolved decisions, and residual risks. Do not require a design document, approval after every section, implementation, commits, or any other external ceremony merely because refinement finished.

## Conditional reference

Read [challenge lenses](references/challenge-lenses.md) only when the artifact is consequential or a generic challenge has not exposed enough risk.
