# Property catalog

The catalog is a revision-scoped summary of what should be tested. Begin it with the provenance defined in [workspace and provenance](workspace.md).

## Property types

- **Safety:** a bad state never occurs.
- **Liveness:** required progress eventually occurs under stated conditions.
- **Reachability:** a meaningful path or result is reached or remains unreachable.
- **Equivalence:** behavior agrees with a model or independent implementation.
- **Metamorphic:** a controlled input transformation has a specified relationship to the output.

## Make every property checkable

Replace "test failover" with a condition such as "an acknowledged write remains readable after leader failover." Ask what input or workload creates the state, what exact observation decides the outcome, and what oracle makes that decision credible. If those cannot be answered, keep the candidate in open questions rather than presenting it as implementable.

## Catalog format

Each property has a descriptive kebab-case slug used in its heading, evidence filename, and relationship references.

```markdown
### acked-writes-survive - Acknowledged writes survive

| | |
|---|---|
| **Type** | Safety / Liveness / Reachability / Equivalence / Metamorphic |
| **Property** | One sentence stating the condition to verify |
| **Oracle** | What is checked, from which observation point, and why it decides the result |
| **Workload** | Inputs or operation sequence needed to exercise it |
| **Fault model** | Relevant failures or perturbations, or None |
| **Candidate mechanisms** | Ordinary test / property-based / stateful model / simulation / Hegel / Antithesis / other, with rationale |
| **Priority** | High / Medium / Low, with reason |
| **Why it matters** | Impact and validated regression evidence, if any |

**Open Questions:**

- Unresolved question, or None.
```

Keep semantic properties independent of framework syntax. A property may have several candidate mechanisms or a cheap deterministic layer plus a deeper generative layer. Name a specific primitive only after selecting the framework and confirming its current API.

## Honest summaries

The prose fields and Open Questions list form one claim. Do not write a firm field that its questions contradict. Write fields at the level of generality supported by evidence; put the unresolved detail in the list.

Open-question tags describe investigation state:

- no tag: not investigated;
- `(partial: <finding>)`: useful evidence exists but the question remains;
- `(needs human input)`: code and available docs were exhausted and a human decision or fact is missing.

Remove resolved questions and update any affected fields. Priority is independent of uncertainty. Put catalog-wide questions in the file-level `Open Questions` section.

## Evidence files

Every cataloged property gets `docs/code-analysis/properties/{slug}.md`. Preserve the evidence trail, relevant paths and symbols, failure scenario, observation points, existing versus missing test hooks, and anything expensive to rediscover.

When investigating a question, append an `### Investigation Log` entry that says what was examined, what was found, what remained absent, and the conclusion. Keep resolved entries as audit history. Every `(partial: ...)` or `(needs human input)` tag must have a corresponding log entry.

## Select candidate mechanisms

- Use an ordinary unit or integration test for a small, reproducible state space with a direct oracle.
- Use property-based generation for broad input spaces and shrinkable counterexamples.
- Use a stateful command model when correctness depends on operation sequences and model state.
- Use simulation or a deterministic scheduler for timing and concurrency when the program can run inside that harness.
- Use system-level generative or fault-injection tools when meaningful behavior spans processes, storage, networks, restarts, or large interleaving spaces.
- Layer mechanisms when one cheaply guards the core property and another searches hard-to-reach states.

Do not force a property into a powerful framework merely because the framework is available. Record tool-specific assertion types, scheduler needs, instrumentation, or deployment constraints only in the mechanism plan.

## Quantity and organization

Scale the catalog to the system and request. A nontrivial distributed system may justify 15 or more properties; a small library or targeted slice may justify only a few. Group by architectural risk, not by an arbitrary count.

Write `property-catalog.md`, `properties/{slug}.md`, and `property-relationships.md` under `docs/code-analysis/`.
