# Fresh-context specification or plan review

Use this optional mode when a consequential specification or plan is critiqued for comprehension or implementation readiness and an independent review would reduce risk. It can be prompted by the user or selected from the artifact's stakes; do not make it routine for low-risk or editorial critique.

Start a fresh reviewer context with the artifact under review and its linked source artifacts. Do not supply the author's conversation, private rationale, or an answer-key rubric. Ask the reviewer to explain the intended outcome and boundaries in its own words, identify material ambiguities, omissions, contradictions, and risks, and assess whether the available evidence supports implementation readiness.

Reconcile every proposed finding with the linked sources and current code where applicable. Separate:

- behavior that exists now, supported by code or executed evidence;
- behavior that is planned or specified but not yet implemented;
- historical behavior, tied to a revision or dated source;
- unknown or unverified claims and what evidence is missing.

A plan's planned paths, tests, or future-state descriptions are not proof of present behavior. Do not mark a specification incorrect merely because its requested change is absent from current code. Report actionable findings with artifact/source locations, evidence, impact, and a proportionate remedy; keep disagreements or missing evidence explicit. Do not edit the artifact, implement the plan, or present private author intent as something a reader could infer from the artifact.

Keep findings tied to stated requirements and material implementation dependencies. Label unstated dependencies as questions; do not turn optional safeguards or illustrative test cases into acceptance criteria.
