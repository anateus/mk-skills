---
name: diagnosing-bugs
description: Diagnose unexplained failures, regressions, or flakiness by reproducing, minimizing, and testing competing causes before changing behavior.
---

# Diagnosing Bugs

Build a tight feedback loop that distinguishes causes before editing. The objective is a cause-level fix supported by evidence, not a plausible patch.

## Investigation loop

1. Capture the reported symptom, environment, expected behavior, and smallest known trigger.
2. Reproduce with the narrowest stable command or observation. Reduce inputs and remove unrelated steps while preserving the failure; keep the minimized evidence.
3. Trace the relevant data and control flow across boundaries. Form at least two competing hypotheses when the cause is uncertain.
4. Choose an observation that would discriminate between hypotheses. Instrument, inspect, or vary one factor, then record the discriminating evidence before changing production behavior.
5. Repeat until evidence identifies the causal mechanism. Fix the cause at the narrowest appropriate layer, preserving unrelated public behavior.
6. Demonstrate the original reproduction now passes and add regression protection at a useful behavior seam. Run fresh affected verification.

Keep experiments cheap and reversible. Logs, temporary assertions, history, and dependency inspection are evidence sources; none substitutes for testing a hypothesis.

Capture only evidence needed for the discriminator. Redact sensitive values in commands and artifacts before sharing; this grants no additional data access.

If the investigation is stuck or appears to have converged suspiciously early, optionally use `adversarial-refinement` to pressure-test the diagnosis. Competing hypotheses remain part of this base loop.

## When reproduction is unavailable

Do not invent certainty. Record a documented limitation: what was attempted, available evidence, environmental gaps, and which hypotheses remain. Improve observability or add safe defensive handling only when justified independently. State what would enable a conclusive reproduction and what regression protection could not be added.

## Outcome

Report the cause or leading hypothesis, decisive evidence, fix, and relevant verification. Keep missing discriminators and reproduction limits visible.
