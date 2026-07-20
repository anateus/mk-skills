# Curated Agent Skills Design

Date: 2026-07-20

## Goal

Turn `mk-skills` into a self-contained, selectively invoked software-development skill set that preserves the strongest ideas from Superpowers, Matt Pocock's skills, Spec Kitty, and Mike's existing `mk-*` skills without inheriting their full workflow machinery.

The initial release targets Codex. Claude Code compatibility is a required fast-follow built on the same policy and skill content.

## Design Principles

- Trust capable models with judgment; add ceremony only where risk warrants it.
- Automatically invoke skills only for clear triggers.
- Keep normal skill bodies concise and independently useful offline.
- Provide strict guidance for smaller models and low-reasoning configurations without duplicating the skill set.
- Separate general engineering practice from repository-specific PR, tracker, and worktree policy.
- Adapt upstream ideas deliberately; never overwrite local skills automatically.
- Preserve fresh verification as the basis for completion claims.

## Upstream Assessment

### Superpowers

Superpowers provides strong practices for clarification, planning, TDD, debugging, review, and verification. Its current distribution is intentionally a complete development methodology. The global `using-superpowers` bootstrap treats even a small chance of relevance as mandatory invocation, while several skills require fixed sequences, multiple approval gates, committed artifacts, worktrees, subagents, and exact completion procedures.

Those controls can improve adherence in weaker models, but they create excessive ceremony and context load for stronger models. `mk-skills` will retain the underlying engineering principles while moving strict sequencing into an optional policy layer.

### Matt Pocock's skills

Matt's repository offers a more compositional model: concise skills, explicit versus model invocation, progressive disclosure, tracer-bullet ticketing, behavior-oriented TDD, tight debugging feedback loops, and review along separate standards and specification axes.

The strongest transferable idea is that each skill should have one clear leading concept and should earn every instruction it includes. Some upstream choices remain too opinionated for the core set, such as mandatory user confirmation of every test seam, always committing after implementation, or requiring parallel subagents for every code review.

### Spec Kitty

Spec Kitty cleanly separates research, specification, planning, task decomposition, implementation/review, acceptance, and merge. Its current skills are compact because much of their behavior belongs to its runtime and command system.

`mk-skills` will reuse the lifecycle boundaries and reviewability principles, not the mission runtime, commands, state transitions, or merge machinery.

### Existing `mk-*` skills

`mk-clarify` contributes a valuable integration taxonomy: downstream consumers, failure modes, schema propagation, service lifecycle, authorization, dependency scope, configuration, and edge cases. This will be retained but scaled to task risk.

`mk-write-plan` contributes integration-aware exploration, explicit architecture decisions, and TDD-sized task slices. Its backlog-specific commands will not enter the portable core.

`mk-pr` demonstrates robust resumability and safe state detection, but its PR and backlog state machine is deliberately excluded. The replacement implementation skill will not own PR lifecycle, CI polling, tracker states, worktrees, or merge operations.

## Operating Profiles

The same skills support three profiles:

- `selective`: default. Skills trigger only on clear descriptions, and each workflow scales its depth to uncertainty and risk.
- `strict`: injects compact sequencing, checkpoint, and verification rules for smaller models or constrained reasoning effort.
- `off`: disables automatic policy injection while leaving skills available for explicit invocation.

Strict mode strengthens how the shared skills are applied. It does not require PR creation, commits, worktrees, subagents, external tracker changes, or destructive actions.

## Hook and Policy Architecture

`mk-skills` will be packaged as a Codex plugin containing portable skills and a thin `SessionStart` hook. The hook will also run after compaction so strict guidance remains present when context is rebuilt.

The hook receives the documented Codex model slug and selects a profile in this order:

1. Explicit environment or local configuration override: `strict`, `selective`, or `off`.
2. Model-family rules in a harness-neutral policy file.
3. The `selective` default.

Codex does not currently expose reasoning effort as a documented hook input. The first release will therefore provide a Codex profile or environment override that pairs low reasoning effort with strict mode. It will not parse the unstable session transcript. Direct effort detection can replace the override when a stable hook field becomes available.

The hook will fail open. Unknown models, missing policy, or malformed overrides select `selective` and return a concise diagnostic. Injected strict guidance should remain roughly 150-250 words.

Claude Code compatibility will reuse the selector, policy schema, and injected text. Only its hook adapter and packaging differ. Shared fixtures must prove both adapters make equivalent decisions.

## Curated Skill Set

### `clarifying-work`

Use for ambiguous, integration-heavy, or cross-boundary changes. Inspect discoverable facts before questioning the user. Apply the `mk-clarify` integration taxonomy proportionally, prioritize questions by rework risk and uncertainty, and ask only questions whose answers materially change the result.

### `specifying-work`

Turn intent into a concise specification covering the problem, desired behavior, constraints, acceptance criteria, testing seams, and non-goals. Synthesize established conversation rather than repeating an interview. Require approval only when unresolved decisions materially affect scope or architecture.

### `planning-work`

Ground implementation plans in the existing codebase. Prefer vertical tracer-bullet slices with explicit dependencies and verification. Use exact paths only after inspecting the repository. Keep tracker publication optional and outside the core plan format.

### `test-driven-development`

Combine behavior-first tests at public seams with observable red-green evidence and narrow vertical cycles. Apply TDD where behavior can be expressed through a useful seam; allow proportional alternatives for mechanical, generated, configuration-only, or otherwise low-value cases.

### `diagnosing-bugs`

Build a tight feedback loop, reproduce and minimize the failure, form competing hypotheses, instrument discriminating evidence, fix the cause, and add an appropriate regression test. Record limitations when a reliable reproduction or seam cannot be built.

### `implementing-work`

Act as a lightweight router for work based on an approved spec, plan, or ticket. Implement in coherent slices, use applicable testing guidance, verify the result, and request review when risk warrants it. Do not own PR or tracker state.

### `reviewing-code`

Review a fixed diff along distinct axes: correctness and risk, specification compliance when a spec exists, and documented repository standards. Use independent or parallel passes when the change is large enough to benefit; do not mandate subagents for small reviews. Report actionable findings by severity before summaries.

### `handling-review-feedback`

Interpret feedback technically, verify it against the code and requirements, clarify ambiguous or conflicting items, and then implement accepted changes. Avoid both performative agreement and reflexive rejection.

### `verifying-work`

Require fresh, relevant evidence before claiming completion, correctness, passing tests, or readiness. Match evidence to the claim and state limitations precisely. Keep this skill small enough to trigger frequently without dominating context.

### `handing-off-work`

Create a concise, resumable handoff in a temporary location. Reference existing specs, plans, issues, commits, and diffs rather than duplicating them. Include current state, remaining work, verified facts, blockers, and suggested skills; redact secrets.

### `strict-mode`

Provide the compact policy injected by the hook. It makes applicable skill selection, ordered execution, checkpoints, and fresh verification explicit. It should improve adherence without changing user intent or adding external side effects.

### `curating-skills`

Fetch configured upstream repositories, review changes since the last recorded commits, identify new ideas and regressions, and propose conceptual adaptations. It updates provenance only after local decisions and validation are complete.

### Existing skills

`zellij-agent-herder` remains intact. Worktree management, branch finishing, parallel-agent orchestration, and PR lifecycle may be added later as optional skills, but they are excluded from the initial portable core.

### `zellij-agent-herder` harmonization

The curated skills and `zellij-agent-herder` must compose without depending on one another:

- No curated skill requires zellij, Herdr, subagents, or parallel execution.
- `zellij-agent-herder` does not require the curated workflow or strict mode.
- When zellij orchestration is available and the task benefits from independent work, a curated skill may recommend or invoke `zellij-agent-herder` through normal skill discovery rather than duplicating pane-management instructions.
- Plans and reviews should describe units of work, dependencies, fixed comparison points, expected outputs, and verification clearly enough to become peer-agent briefs.
- Parallel execution remains conditional on independence and file ownership. Sequential execution remains valid.
- Strict mode may require explicit coordination and verification when peers are used, but it must not require peers to be used.
- Peer results remain inputs to the primary agent's verification; orchestration success is not evidence that the underlying work is correct.

This creates a clean seam: the curated skills decide what engineering work is appropriate, while `zellij-agent-herder` can provide the execution topology when the user or environment chooses it.

#### Pane identity breadcrumbs

Agent panes receive a stable breadcrumb identity when `zellij-agent-herder` creates them or its lifecycle hook first observes them. Each identity contains a curated emoji, a full name, and initials. A useful native agent session name is preferred; generic labels such as `agent`, `claude`, `codex`, `yolo-claude`, `yolo-codex`, spinner-prefixed variants, and names identical to the repository or directory are rejected. When no useful native name is available, the skill generates and persists an adjective-noun fallback.

Lineage metadata is stored in a cache keyed by zellij session and pane ID rather than recovered from presentation text. Child panes inherit the parent's lineage and can propagate it to grandchildren. Identities remain stable once assigned.

Titles render the full leaf and abbreviated ancestors while preserving the existing byte-compatible status suffix:

```text
mk-skills (🦀 funky-crab) · working
🦀 f-c > 🌿 glamorous-lemur · working
🦀 f-c > 🌿 g-l > 🍜 mutinous-ocelot · working
```

The emoji allowlist uses concrete animals, plants, foods, tools, vehicles, and ordinary objects. It excludes faces, people, gestures, flags, abstract symbols, geometric shapes, and presentation-dependent sequences. Plain panes remain unaffected unless created through the peer wrapper or observed through the installed agent lifecycle hook.

## Repository Layout

```text
mk-skills/
├── .codex-plugin/plugin.json
├── hooks/
│   ├── hooks.json
│   └── select-mode.js
├── skills/
│   ├── clarifying-work/
│   ├── specifying-work/
│   ├── planning-work/
│   ├── test-driven-development/
│   ├── diagnosing-bugs/
│   ├── implementing-work/
│   ├── reviewing-code/
│   ├── handling-review-feedback/
│   ├── verifying-work/
│   ├── handing-off-work/
│   ├── strict-mode/
│   ├── curating-skills/
│   └── zellij-agent-herder/
├── adapters/
│   └── claude/
├── config/
│   ├── mode-policy.json
│   └── sources.yaml
├── scripts/
│   ├── review-upstreams.*
│   └── validate.*
└── tests/
    ├── hooks/
    ├── skills/
    └── fixtures/
```

Exact script extensions and test framework will follow the repository's chosen minimal runtime. The design requires deterministic scripts but does not require a new application framework.

## Provenance and Upstream Curation

`config/sources.yaml` records, for each upstream:

- repository URL and tracked branch;
- last reviewed commit;
- license and attribution;
- upstream paths relevant to each local skill.

Provenance stays outside runtime skill text so normal invocation carries no provenance token cost. A repository-level third-party notice preserves attribution required by the MIT licenses used by Superpowers, Matt Pocock's skills, and Spec Kitty.

The upstream review script clones or fetches sources into temporary/cache storage and produces a review bundle containing:

- commits since the recorded revision;
- added, removed, and changed skills;
- diffs for mapped source paths;
- local skills potentially affected.

The curation workflow then compares three conceptual states:

1. Current local behavior.
2. Previously reviewed upstream behavior at the recorded commit.
3. New upstream behavior.

No upstream file automatically replaces a local file. The agent proposes adaptations, evaluates them against local principles, runs relevant skill and hook tests, records the decision, and only then advances the reviewed commit. This supports both adoption and explicit rejection of upstream ideas without repeatedly reconsidering the same change.

All installed skills remain usable without network access. Network access is needed only during deliberate curation.

## Error Handling and Safety

- Hook failures select `selective` and emit a concise diagnostic.
- Curation failures leave recorded revisions unchanged.
- Upstream repositories are read-only inputs; the workflow does not push or open pull requests without an explicit request.
- Skills do not infer authority to commit, push, create PRs, mutate trackers, create worktrees, merge, or delete data.
- Existing dirty-worktree changes are preserved and unrelated files remain untouched.
- Unsupported harness features degrade to a documented manual path rather than silently changing behavior.

## Verification Strategy

### Structural validation

- Validate every `SKILL.md` frontmatter block and skill directory name.
- Enforce concise size budgets, with tighter limits for frequently invoked skills.
- Validate the Codex plugin manifest and hook schema.
- Verify every referenced local file exists and provenance mappings resolve.

### Hook tests

- Known smaller models select `strict`.
- Known capable models select `selective`.
- Explicit `strict`, `selective`, and `off` overrides win.
- Unknown models and malformed configuration fail open.
- Startup, resume, clear, and compaction paths behave consistently where applicable.
- Codex and Claude adapters produce the same policy decision from shared fixtures.

### Behavioral skill tests

Use representative pressure scenarios to compare baseline, selective, and strict behavior. At minimum, test:

- a trivial edit does not trigger a lengthy design ceremony;
- an integration-heavy change surfaces downstream consumers and failure modes;
- a bug investigation reproduces before fixing;
- TDD tests public behavior rather than implementation details;
- review distinguishes correctness, specification, and standards findings;
- completion claims cite fresh evidence;
- strict mode increases sequencing adherence without inventing PR or tracker work.
- the same plan can execute locally or through `zellij-agent-herder` without changing its engineering requirements;
- peer-agent use adds coordination and result verification without becoming mandatory.
- parent, child, and grandchild agent panes render stable emoji-and-name breadcrumbs while preserving status parsing;
- generic native pane names fall back to a persisted curated identity.

### Curation tests

- Fixtures cover new, changed, renamed, and removed upstream skills.
- The review bundle is deterministic for the same source revisions.
- Failed fetches and malformed manifests do not advance provenance.
- Accepted and rejected upstream changes can both be recorded without copying entire upstream repositories.

## Delivery Sequence

1. Establish the Codex plugin, policy schema, selector, and strict-mode injection.
2. Add the curated skills and structural validation.
3. Add behavioral tests for selective and strict profiles, including optional `zellij-agent-herder` composition.
4. Add stable pane identity breadcrumbs to `zellij-agent-herder`.
5. Add provenance, upstream-review tooling, and attribution.
6. Complete the Claude Code adapter using shared policy fixtures.
7. Update installation documentation for both supported harnesses.

Claude compatibility is a required delivery milestone. It may follow the Codex implementation, but the initial project is not complete until both adapters pass the shared policy tests.

## Explicit Non-Goals

- Reimplementing `mk-pr` or Spec Kitty's mission/runtime state machines.
- Automatically merging upstream skill text.
- Requiring one issue tracker, PR host, test framework, or worktree convention.
- Making all skills auto-invoke.
- Guaranteeing reasoning-effort detection through undocumented Codex internals.
- Replacing the existing `zellij-agent-herder` skill.
