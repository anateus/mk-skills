---
name: handling-review-feedback
description: Evaluate review comments as technical claims, classify them, and apply accepted changes with verification. Use when review feedback, inline comments, or requested changes need assessment, implementation, or response.
---

# Handling Review Feedback

Technically evaluate feedback as a claim, neither an instruction to accept reflexively nor a position to reject defensively.

## Evaluate each item

1. Restate the claimed problem and requested outcome in technical terms.
2. Inspect the cited code and requirements, then trace affected behavior and constraints. Reproduce or test the concern when practical.
3. Check whether multiple comments share one cause or conflict with one another.
4. Assign exactly one classification:
   - **accepted:** evidence supports the concern and the proposed direction fits the requirements;
   - **rejected with evidence:** the claim is inapplicable or harmful, with concrete code, requirement, or test evidence;
   - **clarification-needed:** intent, scope, evidence, or the desired tradeoff is ambiguous.

Ask a focused question for clarification-needed items before making a consequential interpretation. Explain rejected items directly without performative agreement.

## Apply accepted feedback

Order accepted items by dependency and shared cause. Use `diagnosing-bugs` when a claimed defect's cause is uncertain, `test-driven-development` when accepted feedback changes observable behavior, and `verifying-work` before closing an accepted item. Implement the smallest coherent changes. Verify accepted changes against the original concern and run affected checks; a code edit alone does not close feedback.

Report each item's classification, evidence, action, and verification. Keep unresolved disagreements visible rather than silently dropping them.
