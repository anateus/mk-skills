# Property discovery

Discover testable properties through independent attention lenses after the system model and existing-hook scan are current. Use the format in [property catalog](property-catalog.md).

## Attention lenses

1. **Data integrity:** ordering, transaction boundaries, constraints, corruption, loss, and round trips.
2. **Concurrency:** races, atomicity, cancellation, ordering, shared state, and time-of-check/time-of-use gaps.
3. **Failure recovery:** partial operations, restart behavior, retries, idempotency, and recovery subphases.
4. **Protocol contracts:** schemas, error semantics, compatibility, message ordering, and wire rendering.
5. **Resource boundaries:** exhaustion, leaks, backpressure, queue depth, and capacity limits.
6. **Security boundaries:** authorization, privilege transitions, input validation, and confused-deputy paths.
7. **Distributed coordination:** consensus, leadership, partitions, replication, and stale commands. This may yield nothing for a single-process library.
8. **Lifecycle transitions:** startup, shutdown, migration, upgrade, initialization, and cleanup.
9. **Idempotency and replay:** duplicates, at-least-once work, deduplication, and repeated side effects.
10. **Version compatibility:** serialization, defaults, negotiation, and mixed-version behavior.
11. **Wildcard:** non-obvious properties and interactions the fixed lenses miss.

For each candidate, record code evidence, confidence, the exact property, workload, oracle, useful fault model, existing test hooks, and open questions. If a lens yields no relevant property, say why.

The wildcard lens runs after the fixed lenses. Look for cross-cutting behavior, missing concepts, surprising interactions, and assumptions so obvious that nobody wrote them down.

## Parallel and sequential operation

When parallel agent work is available and explicitly authorized, assign one lens per agent. Give each agent:

- the current `system-analysis.md` and `existing-test-hooks.md` paths;
- one full lens description;
- the property-catalog format;
- the scope and external-reference list;
- the instruction to validate external claims;
- bounded-reading discipline from `data-spelunking` and a distinct evidence output path.

Each agent writes detailed evidence to disk and returns a compact summary. Otherwise work through the lenses sequentially, treating each fixed lens as a fresh pass.

## Synthesis

- Merge duplicates; independent discovery increases confidence but does not prove a property.
- Preserve unique finds unless evidence invalidates them.
- Resolve disagreements about semantics, priority, oracle, or mechanism by checking code.
- Keep property semantics separate from tool-specific implementation.
- Assign one canonical slug and merge duplicate evidence into one file.
- Record which lenses surfaced each property.
- Write relationship clusters only when properties share evidence, paths, mechanisms, or causal dependencies.

Do not reread every unique evidence file during synthesis when a compact summary is enough. Use `data-spelunking` if intermediate agent or search output is large.

## Investigate open questions

For each open question, examine the evidence file and trace the narrow code or documentation path that can decide it. Do not fabricate answers. Use `(partial: ...)` for incomplete findings and `(needs human input)` only after exhausting available evidence. Append an investigation log, then synchronize the catalog entry. Update, split, or invalidate the property when the answer changes its premise.

## Output

Write or update:

- `docs/code-analysis/property-catalog.md`
- `docs/code-analysis/properties/{slug}.md`
- `docs/code-analysis/property-relationships.md`

Apply provenance from [workspace and provenance](workspace.md) to both top-level files.
