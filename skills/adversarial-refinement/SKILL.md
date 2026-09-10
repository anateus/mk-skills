---
name: adversarial-refinement
description: Stress-test a proposal, decision, plan, architecture, or diagnosis with counterexamples and alternatives. Use when asked to grill, challenge, red-team, or pressure-test an idea.
---

# Adversarial Refinement

## Purpose and boundary

Challenge a coherent proposal in proportion to its risk. Refinement does not authorize implementation or external actions.

## Choose a mode

- **Interactive grill:** when the user asks to be grilled or challenged. Give a recommendation and rationale with each question, then wait. Follow the user's pacing; otherwise group independent choices and sequence dependent ones. Let the user stop or set a challenge budget.
- **Artifact critique:** when another workflow requests a pressure test. Resolve discoverable facts autonomously and return a compact critique; do not manufacture user questions when evidence can settle the issue.

## Refinement loop

1. Establish the artifact and decision under review. Inspect local and other discoverable facts before asking the user.
2. Check the proposal's stated benefit and constraints against the available evidence.
3. Prioritize by decision impact. Test assumptions, counterexamples, failure modes, downstream effects, reversibility, opportunity cost, and the strongest materially different alternative.
4. Track what survived, changed, or remains open. Use a small reversible probe when an empirical uncertainty can be settled within the task's authority.
5. For artifact critique, report evidence-backed findings and proposed refinements. Ask only about material choices the environment cannot resolve.
6. Stop when remaining uncertainty is acceptable for the risk, the challenge budget is spent, or the user asks to stop. Do not exhaustively walk every branch.

## Exit and return

Return the refined position and material changes, alternatives, open decisions, or risks. Scale detail to what the next decision needs.

## Conditional reference

Read [challenge lenses](references/challenge-lenses.md) only when the artifact is consequential or a generic challenge has not exposed enough risk.
