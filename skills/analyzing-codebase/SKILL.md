---
name: analyzing-codebase
description: Build an evidence-backed model of an unfamiliar codebase before consequential work. Use automatically when entering a novel repository or subsystem, when architecture, runtime boundaries, state, or test strategy must be understood, or when the user requests a mode such as for-testing. Do not use for a bounded lookup or routine edit in a familiar area.
---

# Analyzing Codebases

Learn enough of an unfamiliar system to make the next decision safely. Treat names such as `for-testing` as operating modes, not required invocation syntax: infer the mode from the task and activate this skill even when the user does not name one.

## Establish the model

1. Fix the analysis boundary: repository, subsystem, requested outcome, and available external references. Ask only when an unresolved choice would materially change the analysis.
2. Verify behavior from imports, entrypoints, call paths, configuration loading, persistence, and runtime wiring. Treat manifests, READMEs, design docs, issues, and comments as claims until code or runtime evidence supports them.
3. Survey before reading deeply. When the corpus or output is large, use `data-spelunking` to locate candidates, read narrow windows, and preserve the search boundary.
4. Record durable findings under `docs/code-analysis/` by default. Respect another user-selected location. Preserve and extend current artifacts unless the user asks for a fresh pass.
5. Separate observed behavior, claimed intent, hypotheses, and open questions. Include file paths and symbols so another session can verify the model.

## Choose a mode

- For a testing-oriented analysis, including ordinary tests, property-based testing, stateful or generative testing, simulation, Hegel, or Antithesis, read [for testing](references/for-testing.md) and follow its conditional references.
- For architecture orientation without a testing deliverable, use the shared workflow above and the system-model portion of [system discovery](references/system-discovery.md).
- For a requested code graph, first define the question the graph must answer. Prefer built-in text and structural search for bounded questions. A future graph-indexing mode may add tools such as `sqry` or Graphify only after their availability, language coverage, generated-data location, and query value are verified.

## Finish proportionally

Do not turn every first contact with a repository into a full audit. Produce only the artifacts the current task needs, state what remains unexamined, and refresh provenance when the analyzed revision changes.
