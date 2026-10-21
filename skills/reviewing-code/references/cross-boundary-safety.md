# Cross-boundary safety review

Use for ordinary changed-code review when safety depends on assumptions outside the edited symbol. Cover added, modified, deleted, and renamed paths. Keep [diff provenance](diff-provenance.md), consumer decisions, rollback checks, and fix re-review in force. Scale investigation to the change; do not turn this into a mandatory exhaustive audit.

## Find the safety assumptions

State the specific facts that would make the change safe, including multiple independent invariants where needed. Trace the actual entrypoint through its callers, downstream consumers, data and wire formats, persistence, other languages or services, library behavior at the pinned version, local patches, and teardown or timing. A symbol search alone misses consumers of serialized output, configuration, and removed behavior. Check both the bad case and legitimate case at the actual consumer boundary.

For each material assumption, cite the implementation or contract, then run the cheapest direct check against the real code when feasible. A focused test, executable repro, or actual user path is stronger than a plausible explanation or a test name. Record the input, command, result, and limit of its scope. If access or execution is blocked, mark the assumption unproven and explain the consequence. Do not imply that one passing check establishes every invariant.

## Probe likely cross-boundary failures

- **Feature gates and authorization:** trace all ways the feature becomes visible or callable, including API responses, navigation, background jobs, cached state, and internal-only routes. Check gate-off and gate-on consumers rather than relying on a single UI condition.
- **Local developer workflow:** compare required environment variables, secret locations, ports, networking, startup order, prerequisites, build scripts, and migrations with the documented and actual launch path. Flag a newly required manual step, not merely an optional alternative or an ordinary managed dependency.
- **Breakage and recovery:** check compatibility, deleted behavior, failure between dependent writes, and the actual rollback or migration path. Intended removal is not automatically a defect. Report a high-risk intended change when its downstream effects appear unaccounted for or materially underweighted.

Report demonstrated problems with location, impact, and evidence. Separate checked-and-cleared risks from unproven assumptions. Calibrate severity to likely impact and confidence; do not require a finding quota or promote speculation to a blocker. Review-thread comments can supply leads, but independently verify them against the fixed comparison before adopting them.
