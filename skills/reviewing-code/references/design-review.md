# Design and maintainability review

Apply this axis to meaningful implementation changes, even when tests pass and the repository has no written design standard. Correct behavior does not excuse a substantial structural regression. Look beyond local cleanup for a feasible reorganization that removes concepts, branches, state, or indirection while preserving the contract.

## Trace the design before judging it

Follow the changed entrypoints through their callers, contracts, state transitions, and side effects. Locate the existing owner of each policy and any canonical helper. Compare the old and new organization: which responsibilities, dependencies, or cases must a maintainer now understand or change together? Inspect the surrounding implementation before recommending a replacement.

A maintainability finding need not demonstrate a runtime bug. Ground it in a concrete burden introduced, worsened, or unnecessarily retained in the changed implementation, such as scattered policy edits, invalid state combinations, hidden invariants, unnecessary coordination, or indirection that obscures ownership. Show a feasible simpler direction and explain what complexity it removes. Do not invent a future requirement or open unrelated pre-existing debt to justify a preferred design.

## Structural checks

### Remove complexity, not just move it

Look for repeated conditionals, one-off flags, special modes, and exceptions inserted into otherwise unrelated paths. Ask whether a clearer state model, ownership boundary, default flow, or existing abstraction could eliminate whole branches or layers. Centralizing the same tangled conditions in another file is not necessarily a simplification.

Prefer a concrete reframing over rename-only feedback when the problem is structural. A small pure function or explicit dispatcher can help, but do not prescribe another abstraction unless it reduces the concepts, coupling, or change surface a reader must handle.

### Make abstractions earn their cost

Inspect pass-through wrappers, identity adapters, generic registries, and configurable mechanisms hiding a simple fixed shape. What invariant, policy, substitution boundary, or isolation do they provide? Flag indirection that adds a concept without a useful contract, especially when callers still need to know its implementation.

Keep wrappers that enforce a real boundary, compatibility contract, ownership rule, or test seam. Do not equate fewer lines or fewer functions with better design.

### Keep policy in its canonical owner

Check for feature checks scattered through shared infrastructure, implementation details leaking through public APIs, and near-duplicates of existing helpers. Trace the layer that already owns the concept. Explain why the new location forces unrelated consumers to change or lets equivalent flows drift.

Before recommending reuse, verify the existing helper's callers, contract, mutation and error behavior, ordering, and dependencies. Moving every special case into a shared utility can increase coupling rather than fix it.

### Expose contracts and invariants

Question casts, permissive object shapes, unnecessary optionality, and silent defaults that conceal what must be true. Follow where values originate, are validated, and become trusted. A validated boundary or explicit model should simplify downstream decisions rather than merely add type annotations.

Untrusted input legitimately starts as unknown, optional fields can be part of the contract, and deliberate fallback behavior can be correct. Identify the particular invariant being hidden or bypassed, not the presence of a language construct.

### Preserve cohesion as code grows

Look for a formerly cohesive module acquiring unrelated responsibilities, shared mutable state, or dependencies that make a local change require reading several distant flows. Consider decomposition around stable ownership or independently testable behavior.

File size and branch counts are investigation cues, not universal rejection thresholds. A large generated file or cohesive table is not a design defect merely because it crosses a line count. Explain the responsibility or coupling problem that decomposition would solve.

### Make orchestration and failure boundaries deliberate

Trace data dependencies, observable ordering, shared resources, rate limits, cancellation, and failure handling. Independent work may benefit from parallel execution when that also simplifies the flow; work with ordering or resource constraints may need to stay sequential. Do not recommend parallelism from adjacent awaits alone.

For related state changes, inspect what remains after failure between steps. Prefer the owning transaction, atomic operation, or an explicit recovery strategy when the contract requires consistency. Running writes concurrently does not make them atomic. Separate business decisions from orchestration when it makes those dependencies and recovery rules easier to verify.

## Turn the diagnosis into useful feedback

Identify the changed location, the concrete maintenance burden, and a credible simpler direction. State the existing consumers, error behavior, ordering, mutation, and side effects the alternative must preserve. A verified burden does not require implementing a complete redesign before reporting it. If the proposed replacement's feasibility or equivalence is unverified, say so rather than presenting a sketch as proof.

Substantial structural regressions or a clearly demonstrated, materially simpler alternative can warrant blocking feedback despite passing tests. Keep optional improvements distinct from blockers, rank by impact, and avoid burying structural issues under cosmetic nits. A review request does not authorize an implementation rewrite, unrelated cleanup, or a broader redesign.
