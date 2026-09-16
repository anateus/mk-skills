# For testing

Analyze a target system and produce code-analysis artifacts that can drive an appropriate testing approach. The consumer may be an ordinary unit or integration suite, a property-based framework such as fast-check, a stateful or generative system such as Hegel, a simulator, or Antithesis. Choose the mechanism after discovering the properties and execution needs.

## Success criteria

- `docs/code-analysis/system-analysis.md` captures architecture, state, concurrency, existing test strategy, and failure-prone areas.
- `docs/code-analysis/existing-test-hooks.md` records existing assertions, properties, generators, models, fault seams, and observability hooks relevant to testing.
- `docs/code-analysis/property-catalog.md` lists concrete, checkable properties with priorities and candidate test mechanisms.
- `docs/code-analysis/test-topology.md` describes the smallest useful execution shape, from one in-process test to a multi-service fault-injection environment.
- `docs/code-analysis/properties/{slug}.md` preserves each property's evidence trail.
- `docs/code-analysis/property-relationships.md` maps suspected clusters and dependencies.
- `docs/code-analysis/evaluation/synthesis.md` records categorized evaluation findings and actions taken.

Produce only the subset needed for a targeted request, and record omitted work explicitly.

## Scope the run

At the start of a full testing analysis, ask whether docs, design notes, related repositories, issue trackers, incidents, or other references outside the directory tree should be consulted. "Just this directory" is a complete answer. Record each reference as a path or URL plus a short reason.

Beyond that question, ask only for blockers or scoping decisions that cannot be inferred safely:

- the codebase location, if unclear;
- the subsystem that matters, if the request is narrower than the repository;
- known incidents, fixed bugs, or failure modes worth targeting;
- hard constraints on the eventual test environment or framework.

Treat existing artifacts as inputs and extend them unless the user requests a fresh pass. Read [workspace and provenance](workspace.md) before writing any artifact. External sources are leads, not facts; read [validating claims](validating-claims.md).

## Concepts

- **System under test:** the code and runtime behavior inside the analysis boundary.
- **Workload:** operations used to exercise the system, from a direct function call to concurrent clients.
- **Safety property:** a bad state never occurs.
- **Liveness property:** required progress eventually occurs under stated conditions.
- **Reachability property:** a meaningful path or outcome is reached or remains unreachable.
- **Oracle:** the rule, model, independent implementation, or observation used to decide whether behavior is correct.
- **Fault model:** the failures or perturbations a test mechanism can create.

Do not commit to framework primitives during discovery. First express the semantic property, observation point, workload, and fault model. Then map it to a conventional assertion, model comparison, fast-check property or command model, Hegel mechanism, Antithesis assertion, or another suitable test.

## References

| Reference | Read when |
|---|---|
| [workspace and provenance](workspace.md) | Always before writing artifacts |
| [system discovery](system-discovery.md) | Building or refreshing the system model |
| [for contracts](for-contracts.md) | Testing schemas, serialization, APIs, or boundaries across languages and repositories |
| [property discovery](property-discovery.md) | Finding testable properties through independent lenses |
| [property catalog](property-catalog.md) | Recording, prioritizing, and implementing properties |
| [validating claims](validating-claims.md) | Using docs, issues, incidents, or other external claims |
| [fault models](fault-models.md) | Matching failures and perturbations to a test mechanism |
| [test topology](test-topology.md) | Choosing the smallest execution environment |
| [property evaluation](property-evaluation.md) | Stress-testing the catalog as a portfolio |

## Full analysis

1. Initialize or inspect `docs/code-analysis/` using [workspace and provenance](workspace.md).
2. Read [system discovery](system-discovery.md), then analyze architecture, state, concurrency, test strategy, runtime boundaries, and failure-prone paths.
   When properties depend on schemas or boundaries, reuse or refresh the shared [contract inventory](for-contracts.md). Link contract IDs and coverage gaps to the affected properties. Distinguish declared shapes, client expectations, validation, and serialization; generated schemas alone do not establish runtime behavior.
3. Scan for existing test hooks. Search framework configuration and imports, assertion and property definitions, generators or arbitraries, state-machine models, test helpers, fault injectors, deterministic schedulers, fakes, observability events, and internal consistency checks. Record paths, symbols, roles, and whether each hook is active. If none exist, state the search boundary and that no hooks were found.
4. Read [property discovery](property-discovery.md) and [property catalog](property-catalog.md). Discover properties using independent attention lenses, then synthesize and investigate open questions.
5. Read [fault models](fault-models.md) and [test topology](test-topology.md). For each property, choose the least expensive mechanism that can create the required states and observe the result. Write the minimal useful topology.
6. Read [property evaluation](property-evaluation.md). Evaluate the catalog for test-mechanism fit, coverage balance, implementability, and blind spots. Apply refinements, fill material gaps, and surface judgment calls.
7. Update all affected artifacts and their provenance.

## Targeted property research

1. Refresh the system model only if it is missing or stale.
2. Discover properties in the requested area and turn claimed guarantees into explicit properties. Confirm a reported defect before using it as a property premise.
3. Update the catalog, one evidence file per new property, and the relationship map.
4. Select candidate test mechanisms without forcing every property into the same framework.
5. Evaluate the changed slice. A small addition in an existing category does not require a full portfolio evaluation.

## General guidance

- Prefer a condition that can fail over goals such as "test failover."
- A documented guarantee becomes a property to verify, not a statement that the guarantee holds.
- A bug report becomes a lead. Confirm the mechanism from primary evidence before building on it.
- Distinguish existing, partial, and missing instrumentation. Never recommend adding a hook already present.
- Identify surgical system-side observation points for rare, dangerous, timing-sensitive, or externally invisible states.
- Focus on boundaries as well as algorithms: parsing, rendering, adapters, mocks, persistence, clocks, retries, recovery, and lifecycle transitions.
- For language or implementation transitions, test conditional validation, omitted/null values, serialization, and retries at the same observation point. Compatible-looking schemas do not discharge native behavior gaps. Keep inventory coverage limits visible in the property evidence.
- Keep execution topology minimal. Every process, dependency, container, and generated input adds cost or state space.
- Write assumptions and open questions into artifacts rather than keeping them in conversation state.

## Self-review

Before completion, check the requested artifact set against actual files and content. Confirm that:

- the system analysis covers architecture, state, concurrency, test strategy, and failure-prone areas at the requested scope;
- the existing-hook scan states its corpus and distinguishes existing, partial, and missing mechanisms;
- every catalog item is concrete, checkable, prioritized, and linked to a matching evidence file;
- property semantics are separate from framework-specific implementation;
- each candidate mechanism can create the required state and observe the result;
- unresolved questions are visible in the catalog and backed by investigation notes when marked partial or human-dependent;
- relationships reference real property slugs;
- evaluation findings were applied or explicitly left for human judgment;
- provenance matches the analyzed revision and external-reference scope;
- all unexamined areas and incomplete artifacts are named.
