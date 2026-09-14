# Property evaluation

Stress-test the property catalog as a portfolio after discovery and topology planning. Discovery is biased toward finding properties; evaluation is biased toward finding problems in the set. Use a fresh pass when practical so prior investment does not turn evaluation into post-hoc justification.

## Prerequisites

- current `system-analysis.md`, `existing-test-hooks.md`, `property-catalog.md`, and `test-topology.md`;
- one evidence file for every cataloged property;
- the current scope and external-reference list.

## Evaluation lenses

### 1. Mechanism fit

Ask whether each candidate mechanism matches the property's state space, workload, oracle, and fault model. A fixed unit test should not consume system-level search budget. A broad generated property should not be reduced to a few examples. A process-failure property is not covered by an in-process generator.

Check the inverse too: a low-priority property may deserve deeper generative or fault-injection testing because timing, sequences, concurrency, or partial failure create a state space deterministic tests cannot cover.

### 2. Coverage balance

Compare the catalog with the system analysis and topology section by section. Look for:

- high-risk areas with no properties;
- over-investment in low-risk or easy paths;
- missing semantic types, boundary tests, lifecycle scenarios, or version combinations;
- component and dependency blind spots;
- cross-cutting interactions that fell between discovery lenses;
- configurable or optional behavior analyzed only at defaults;
- known regression families without a property grounded in the confirmed mechanism.

### 3. Implementability

For each property, determine whether the test can create its preconditions and observe a credible oracle. Check required code changes, internal instrumentation, dependency fidelity, topology, runtime, cost, reproducibility, shrinking or replay, and cleanup. Flag properties whose candidate mechanism cannot actually exercise them.

### 4. Wildcard

Run this after the fixed lenses. Question the framing, find missing perspectives, cross-cut mechanism fit with feasibility, and report concrete concerns that do not fit another lens.

## Operation

When parallel agent work is available and explicitly authorized, assign one lens per agent. Give each the artifact paths, one lens, external references, provenance values, bounded-reading discipline, and a distinct `evaluation/{lens}.md` output. Each agent writes full evidence and returns a compact summary of findings, passes, and uncertainties. Otherwise make fresh sequential passes and write the same evidence files.

## Categorize findings

- **Gap:** a missing risk, property type, execution state, or failure class that targeted discovery can fill.
- **Bias:** a portfolio orientation or priority judgment that requires human input.
- **Refinement:** a specific property has a fixable issue such as an imprecise oracle, unsuitable mechanism, wrong priority, or missing instrumentation note.

Evaluation lenses describe concerns; synthesis assigns categories after reconciling overlapping evidence.

## Address findings

1. Apply refinements to the catalog, evidence files, and relationships.
2. Fill material gaps with targeted discovery, validating external claims and avoiding duplicates.
3. Present biases with evidence and the exact judgment needed.
4. Re-evaluate when gap filling creates a new category or materially changes portfolio balance. A few additions inside an existing category usually need only focused review.

Keep each property's Open Questions list synchronized with its evidence file. Refresh provenance when code or source scope changes.

## Output

Write:

- `docs/code-analysis/evaluation/mechanism-fit.md`
- `docs/code-analysis/evaluation/coverage-balance.md`
- `docs/code-analysis/evaluation/implementability.md`
- `docs/code-analysis/evaluation/wildcard.md`
- `docs/code-analysis/evaluation/synthesis.md`

Update the catalog, evidence files, topology, and relationships when findings require it. Each evaluation artifact uses provenance from [workspace and provenance](workspace.md).
