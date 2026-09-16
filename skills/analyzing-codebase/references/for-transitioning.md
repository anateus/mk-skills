# For transitioning

Analyze how a capability can move, change language, or be replaced while preserving its required behavior. Produce a concrete next migration step and the evidence needed to remove the old path. Refactoring inside one repository and retiring a monorepo use the same workflow at different scopes.

Read [for contracts](for-contracts.md) and [workspace and provenance](workspace.md). Reuse the shared inventory when its provenance and extraction configuration are current. The static helper supplies source candidates; the transition artifacts below are evidence-backed agent analysis, not automatic equivalence or retirement decisions.

## Establish the transition

Fix the current capability, intended outcome, repositories, and known constraints. Trace its actual entrypoints, callers, implementations, shared types, state, transactions, jobs, and registrations. Keep observed behavior, intended behavior, and proposed destinations separate.

For monorepo retirement, build a broad baseline across services and shared packages, then deepen one capability at a time. Include provider variants and shared-package dependencies. Kiban and Kanban are candidate destinations where source evidence supports the mapping; allow other destinations, split capabilities, and merged replacements. A similar name or schema does not prove that a new implementation replaces an old one.

## Maintain the transition inventory

Write `transition-inventory.json` and a readable `transition-inventory.md` under the analysis workspace. Include per-root provenance, inventory links, baseline scope, unresolved coverage, and an array of capabilities. For each capability record:

| Field | Required meaning |
|---|---|
| `id`, `name`, `legacyContracts` | Stable capability identity and source contract IDs, including provider variants |
| `disposition` | `move`, `replace`, `retire`, `retain-temporarily`, or `undecided` |
| `replacements` | Proposed or verified contract mappings, destination, and evidence for that status |
| `remainingCallers`, `stateDependencies` | Known consumers, registrations, shared state, and unresolved searches |
| `behavioralGaps` | Validation, serialization, protocol, state, retry, or delivery differences |
| `stage` | `discovered`, `characterizing`, `implementing`, `coexisting`, `cutover`, or `retired`, backed by evidence |
| `nextBlocker`, `nextAction` | What prevents the next step and the smallest action that resolves it |
| `retirementEvidence` | Required checks, evidence already collected, outstanding checks, and conclusion |

Use empty arrays only for examined categories with no findings; record unexamined categories explicitly. Keep proposed mappings distinct from verified correspondences. A correspondence establishes the relationship between implementations; behavioral compatibility still needs its own evidence.

## Analyze the next capability

Write `transition-analysis.md` for the selected migration. Link its contracts and capability ID, then cover:

1. Current and proposed ownership, actual callers and implementations, and the boundary being moved.
2. Required behavior and known mismatches, including validation, serialization, error handling, side effects, state ownership, transaction coupling, retries, and idempotency.
3. Characterization checks and observations that can distinguish the implementations. Use [for testing](for-testing.md) for a deeper test analysis when needed.
4. A migration sequence with dependencies, coexistence, cutover criteria, rollback conditions, and irreversible state changes.
5. Retirement checks and the next executable step, with unresolved evidence called out.

Support TypeScript-to-Python and Python-to-TypeScript moves. Separate structural conversion from required runtime behavior. Matching JSON Schemas cannot establish equivalent custom validation, omission rules, numeric behavior, or side effects. Generated language models and automated conversions are future tooling; the current workflow can specify and compare these requirements from source and tests.

## Establish retirement evidence

A remaining legacy caller blocks retirement. Removing its static reference during a partial scan does not prove that all callers moved. Check consumers across the scanned repositories, external clients, provider and tool registrations, deployed versions, outstanding jobs/messages, shared state, and rollback dependencies.

Record required runtime or deployment evidence as outstanding when unavailable. Stay within existing authorization for obtaining it. Static inventory alone cannot mark a capability safe to delete, even when it reports no references. Keep the stage short of `retired` until the old path's removal and the required checks are evidenced.

Compare rescans against the explicit baseline and scopes: new legacy dependencies, changed contracts, unresolved callers, and retirement blockers. A narrower scan is not migration progress. Treat source moves and renames as candidates for reconciliation before concluding that a capability disappeared.

## Review the result

Follow one proposed boundary back through its source call chain and forward to its replacement or stated gap. Check that a remaining caller blocks removal, an unsupported refinement blocks an equivalence claim, and partial coverage leaves retirement unresolved. Every sequencing recommendation needs a concrete dependency or behavioral reason. Finish with the next action and the evidence that would allow the following step.
