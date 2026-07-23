# Parallel investigations

Use parallel agents only for independent evidence surfaces or competing hypotheses. Parallelism should reduce wall time, not multiply speculative narratives.

## Coordinator contract

Before dispatching:

1. Write the incident contract and current hypothesis matrix.
2. Fetch or snapshot shared source once when possible.
3. Assign non-overlapping boundaries and one discriminator per agent.
4. Keep production work read-only unless the user separately authorized a mutation.
5. Limit the first wave to the smallest useful set, usually two or three probes.
6. Reconcile results into the ledger before starting another wave.

Stop dispatching when agents repeat the same evidence, lack access to a discriminator, or return only plausible stories.

## Reusable investigator prompt

```markdown
Investigate <incident> read-only.

Hypothesis or surface: <one bounded mechanism or evidence source>
Discriminator: <the observation that would differ between live alternatives>
Scope: <repos, services, time window, cohort, environment>
Allowed sources/actions: <explicit list>
Do not: mutate production, update tickets, expose secrets, or infer live wiring from docs alone.

Return:
1. Verdict: supported, refuted, or inconclusive.
2. Decisive evidence table with exact source/artifact/query, window, denominator, identifiers, and actor/clock/leg.
3. Strongest disconfirming evidence.
4. Null coverage, instrumentation boundaries, and assumptions.
5. Smallest next discriminator if inconclusive.
6. Claims from the brief that the evidence corrects.
```

## Useful non-overlapping probes

- Runtime tracer: prove the current entrypoint, call graph, config, and deployment path.
- Data discriminator: compare affected/unaffected cohorts and quantify onset, occupancy, latency, and null coverage.
- Raw-boundary investigator: inspect provider bodies, packet/audio traces, or external service responses and identify the emitting actor.
- Adversarial verifier: after synthesis, challenge the proposed causal chain using only the ledger and raw artifacts.

Do not ask every agent to “find the root cause.” Ask each to settle one boundary or hypothesis, then synthesize centrally.
