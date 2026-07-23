# Evidence ledger

Use one durable Markdown document per incident. Append changes; do not rewrite history.

## Incident contract

```markdown
# Incident: <name>

- Symptom:
- Impact:
- Expected baseline:
- Last known good / first known bad:
- Timezone and comparison window:
- Affected and unaffected cohorts:
- Environment:
- Allowed actions:
- Current runtime path:
```

## Evidence table

```markdown
| ID | Kind | Observation or claim | Source and query/artifact | Window / scope | Layer / actor / identifier | Supports | Refutes | Confidence |
|---|---|---|---|---|---|---|---|---|
| E1 | observation | ... | ... | ... | ... | H1 | H2 | direct |
```

Use these kinds:

- `observation`: directly visible in a raw artifact or reproducible query.
- `inference`: follows from named observations; state the reasoning.
- `hypothesis`: a mechanism that predicts different observations.
- `limitation`: missing access, coverage, clock alignment, or ambiguous semantics.
- `decision`: an operational choice and its authority.

## Hypothesis matrix

```markdown
| ID | Mechanism | Predicted observation | Cheapest discriminator | Result | Status |
|---|---|---|---|---|---|
| H1 | ... | ... | ... | E1 | active / refuted / supported |
```

Keep “supported” distinct from “confirmed.” A correlation or matching timestamp supports a hypothesis; a discriminator that separates strong alternatives can confirm it.

## Correction log

```markdown
| Time | Superseded claim | Corrected claim | Evidence forcing change | Downstream artifacts to revise |
|---|---|---|---|---|
```

Corrections are first-class evidence. Update incident posts, tickets, diagrams, memories, and proposed fixes when their premise changes.

## Checkpoint

Before each new investigation wave, write:

1. What is directly known?
2. Which hypotheses remain live?
3. What single observation would most change the decision?
4. Which existing work would the proposed probe duplicate?
5. Is the incident asking for diagnosis, mitigation, or both?
