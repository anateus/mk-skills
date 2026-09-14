# System discovery

Build a concrete model of the system under test. This model drives which properties matter, which mechanisms can exercise them, and where defects are likely to hide.

## Start from runtime wiring

- Read process and library entrypoints, server setup, command parsing, exports, and framework registration.
- Trace representative paths from input through validation, control flow, side effects, persistence, and output.
- Identify process and service boundaries, protocols, queues, callbacks, and ownership of retries.
- Map stored and in-memory state, transactions, caches, replication, consistency, and recovery.
- Trace test entrypoints, configuration, fixtures, fakes, helpers, and CI commands to learn what tests actually execute.

Use `data-spelunking` when repository size or generated output makes a whole-corpus read unsafe. Locate first, then read narrow symbol and line windows. A dependency manifest or architecture document is a lead; imports and runtime registration establish current use.

## Independent attention lenses

Make explicit passes through the codebase with these lenses. A lens may yield little; record why rather than inventing findings.

1. **Architecture and data flow:** components, boundaries, protocols, request and event paths.
2. **State and persistence:** durable state, caches, queues, transactions, consistency, recovery.
3. **Concurrency:** threads, async work, shared state, locks, ordering, cancellation, schedulers.
4. **Safety claims:** invariants the system says it never violates.
5. **Liveness claims:** progress and recovery the system says eventually occur.
6. **Bug history:** confirmed mechanisms, regressions, hotspots, and suspiciously untested areas.
7. **Existing test strategy:** unit, integration, end-to-end, property, stateful, simulation, chaos, load, and their real boundaries.
8. **Failure and degradation:** retries, timeouts, fallbacks, partial results, overload, and intermediate failure states.
9. **External dependencies:** behavior delegated to services, storage, clocks, networks, or third-party APIs.
10. **Product context:** critical workflows and user-visible impact.
11. **Unproven assumptions:** swallowed errors, "impossible" branches, undocumented ordering, time, capacity, or availability assumptions.
12. **Wildcard:** surprising or cross-cutting behavior outside the other lenses.

Treat lenses 1 through 11 as fresh examinations. Run wildcard last with awareness of covered territory. When authorized parallel agents are available, lenses may be assigned independently; give each agent the scope, source boundaries, external references, narrow-reading discipline, and a findings-file path. Otherwise run the same lenses sequentially.

## High-value seams

Pay special attention to concurrent state transitions, stale observations, control-plane and data-plane races, recovery from partial work, retries that amplify failure, configuration changes under load, inaccurate health signals, parser or serialization boundaries, and mock wiring that bypasses production behavior.

Timing-sensitive and distributed scenarios deserve explicit treatment, but they are not the only valuable output. For a small library, the strongest properties may instead live in algebraic behavior, parsing, resource ownership, model equivalence, or sequences of public operations.

## External sources

Architecture docs reveal intended design, issues and incidents suggest weaknesses, closed fixes suggest regression families, and limitations sections reveal known risk. Validate a source before stating its claim as current behavior. Represent a claimed guarantee as something to test.

## Output

Write `docs/code-analysis/system-analysis.md` with provenance from [workspace and provenance](workspace.md). Separate observed behavior, claimed intent, hypotheses, assumptions, and open questions.
