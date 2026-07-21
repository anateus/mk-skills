# Skill Activation, Adversarial Refinement, and Progressive Disclosure Implementation Plan

> **Feature Name:** Reliable skill activation and progressive disclosure
>
> **Required sub-skill:** Use `implementing-work` to execute this plan task-by-task. Use the additional skills named in each task only when their stated condition applies.
>
> **Goal:** Make every installed skill easy to trigger from realistic requests, add an optional cross-workflow `adversarial-refinement` capability, preserve enough guidance in each base `SKILL.md`, move specialized operational detail into directly routed references, and make repository validation cover the resulting contracts.
>
> **Architecture:** Skill descriptions provide capability plus trigger vocabulary. Base skill bodies retain the essential decision loop and route conditionally to exact skill names or one-level references. `adversarial-refinement` is a composable pressure-testing workflow with interactive and artifact-critique modes. Deterministic scripts own fragile mechanics such as review-package generation. Repository tests validate structure, routing, provenance, and bundled helpers; clean-session forward tests evaluate actual activation behavior.
>
> **Tech Stack:** Markdown Agent Skills, Node.js 20+ standard library and `node:test`, Python 3.11+ standard library and `unittest`, POSIX shell, Git, JSON-compatible YAML, Codex and Claude Code plugin hooks.

## Global Constraints

- Selective invocation remains the default. Do not turn any skill into a universal gate.
- Keep essential workflow, selection, safety, and exit guidance in each base `SKILL.md`; move only specialized operational detail, extended examples, or variant-specific lenses into references.
- Every skill description must state both what the skill does and concrete contexts or user phrases that should trigger it.
- Every bundled reference must be linked directly from its owning `SKILL.md` with a clear “read when” condition. Do not use `@` links or create nested reference chains.
- Cross-skill routing must use exact installed skill names. Conditional routing does not make the routed skill universally mandatory.
- `adversarial-refinement` is optional and risk-scaled. It must never become a prerequisite for every specification, plan, implementation, or creative change.
- Preserve the strongest ideas from upstream `grilling` and `brainstorming` without importing relentless exhaustive questioning, mandatory design for trivial work, fixed approval gates, commits, tracker state, or a forced implementation transition.
- Preserve repository independence from commits, pull requests, trackers, worktrees, Zellij, Herdr, peers, subagents, and external lifecycle actions unless the user or repository explicitly requires them.
- Skills and scripts must use paths relative to the skill base directory or an explicitly discovered target repository. Never hardcode an installation path.
- Keep the same skill content usable by Codex and Claude Code. Host adapters may differ; workflow semantics must not fork.
- Preserve unrelated working-tree changes. The existing untracked `tests/curation/__pycache__/` belongs to the user; do not delete it as part of this work.
- Use behavioral red-green evidence for testable changes. A failing test must fail for the intended missing behavior, not because of broken setup.
- Do not advance an upstream `reviewedCommit` until every newly covered upstream change has a durable accept/reject decision and repository validation passes.
- Do not add scripts, references, metadata, or documentation merely for symmetry. Every added resource must solve a demonstrated activation, reliability, or context-loading problem.

## Current Verified State

- The repository contains 13 skills: 12 compact workflow skills and `zellij-agent-herder`.
- The 12 compact workflow bodies are approximately 156–278 words and contain useful core loops. Their primary underuse risk is description and routing quality, not body length.
- `zellij-agent-herder/SKILL.md` is approximately 1,223 body words and mixes everyday pane control with specialized worktree/Hunk stream behavior.
- The installed `curating-skills` copy contains `SKILL.md` and `scripts/review-upstreams.py`, but not repository-level `config/sources.yaml`; its current command works only when invoked from the mk-skills repository root.
- `strict-mode/SKILL.md` and the injected strict policy substantially duplicate one another, while the injected text does not explicitly say strict mode is active or route to `strict-mode`.
- `scripts/validate.js` runs top-level hook, skill, curation, plugin-schema-when-available, and diff checks, but it does not run `skills/zellij-agent-herder/tests/*`.
- Existing validation is green: 44 top-level Node tests, 8 curation tests, and all separately invoked Zellij Python and shell suites passed on 2026-07-21.
- Plugin-schema and skill-creator validators currently skip/fail locally because the active Python environment does not provide PyYAML.
- The current upstream review contains one mapped change: Matt Pocock’s `to-tickets` removed a redundant instruction to execute tickets one at a time. Local `planning-work` already separates planning from execution, so the approved decision is **accept with no local skill change**.

## Approved Design Decisions

### Skill boundaries

| Skill | Primary responsibility |
|---|---|
| `clarifying-work` | Discover facts and resolve consequential uncertainty before selecting a solution. |
| `adversarial-refinement` | Deliberately challenge a coherent idea, decision, specification, plan, architecture, diagnosis, or proposal. |
| `specifying-work` | Record agreed behavior, constraints, acceptance criteria, seams, and non-goals as a reviewable contract. |
| `planning-work` | Produce a codebase-grounded implementation sequence from an accepted request or specification. |
| `reviewing-code` | Review a fixed code change against correctness, risk, requirements, and repository standards. |

`adversarial-refinement` owns constructive opposition. It does not replace discovery, specification, planning, code review, or user authority.

### `adversarial-refinement` modes

1. **Interactive grill:** Triggered by requests such as “grill me,” “challenge this,” “poke holes in this,” “red-team this,” or “stress-test this.” Ask one material question at a time, include a recommended answer and rationale, wait for the user, and maintain a compact record of what survived, changed, or remains open.
2. **Artifact critique:** Triggered when another skill explicitly requests a pressure test. Inspect facts autonomously, challenge the artifact, return findings and proposed refinements, and ask the user only about material choices the environment cannot resolve.

Both modes must:

- establish the artifact and decision under review;
- inspect discoverable facts before asking questions;
- steelman the current proposal before attacking it;
- test assumptions, counterexamples, failure modes, downstream effects, reversibility, opportunity cost, and the strongest materially different alternative;
- prioritize challenges by decision impact rather than exhaustively walking every branch;
- stop when remaining uncertainty is acceptable or the user asks to stop;
- return the refined position, important changes, rejected alternatives, and residual risks to the caller;
- avoid writing implementation code, committing artifacts, or taking external lifecycle actions merely because refinement completed.

### Progressive-disclosure policy

- Keep `clarifying-work`, `specifying-work`, `test-driven-development`, `diagnosing-bugs`, `verifying-work`, and `handing-off-work` self-contained in their base files.
- Improve activation and exact-name routing in `planning-work`, `implementing-work`, and `handling-review-feedback` without splitting their core loops.
- Add targeted operational resources to `reviewing-code` and `curating-skills` only where the base currently lacks deterministic mechanics or durable records.
- Make `strict-mode` the named expanded workflow while retaining a compact, self-sufficient injected fallback for smaller models.
- Rechunk `zellij-agent-herder` so base guidance covers the environment guard, addressing, helper loading, critical spawn safety, quick reference, and routing; specialized activation, lifecycle hook, shared-agent configuration, and worktree/Hunk stream details live in one-level references.

### Exact description targets

Use these descriptions verbatim unless a validator requires only YAML quoting changes:

| Skill | Description |
|---|---|
| `clarifying-work` | Reduce consequential uncertainty by inspecting facts, separating assumptions from decisions, and mapping integration risks. Use when a request is ambiguous, integration-heavy, cross-boundary, or likely to hide decisions that could cause substantial rework. |
| `adversarial-refinement` | Stress-test and improve proposals, decisions, specifications, plans, architectures, and diagnoses using adversarial questions, counterexamples, alternative approaches, and tradeoff analysis. Use when the user asks to grill, challenge, red-team, stress-test, or poke holes in an idea, or when another workflow explicitly requests a pressure test before commitment. |
| `specifying-work` | Turn agreed intent and repository evidence into a concise behavior contract with acceptance criteria, testing seams, constraints, and non-goals. Use when the user asks for a specification, design contract, requirements, or acceptance criteria before planning or implementation. |
| `planning-work` | Create a codebase-grounded, executable implementation sequence using narrow vertical slices, dependencies, owned files, expected outputs, and verification. Use when the user asks for an implementation plan or when a reviewed request or specification has multi-step dependencies. |
| `test-driven-development` | Implement observable behavior changes through narrow red-green cycles at public seams, with proportional alternatives when a test adds little value. Use when the user asks for test-first or TDD work, or when implementing a behavior change or defect fix that has a useful observable seam. |
| `diagnosing-bugs` | Diagnose failures by reproducing, minimizing, and testing competing hypotheses before changing behavior. Use when behavior is failing, inconsistent, flaky, regressed, or unexplained and the cause is not established by evidence. |
| `implementing-work` | Route and implement approved or sufficiently clear changes in an existing codebase as coherent, verified slices. Use when the user asks to add, build, change, fix, or implement behavior from a request, specification, plan, or review feedback. |
| `reviewing-code` | Review a fixed code change or diff for correctness, risk, specification compliance, repository standards, and test adequacy. Use when the user asks to review, audit, or assess a diff, patch, pull request, commit range, or completed implementation before acceptance or release. |
| `handling-review-feedback` | Evaluate review comments as technical claims, classify them, and apply accepted changes with verification. Use when review feedback, inline comments, or requested changes need assessment, implementation, or response. |
| `verifying-work` | Map completion and readiness claims to fresh direct evidence, run the relevant checks, and report limitations precisely. Use when asked to verify, check, test, confirm, or prove that work is correct, complete, passing, buildable, or ready. |
| `handing-off-work` | Create a concise, redacted, resumable transfer that references durable artifacts and distinguishes verified facts from remaining work. Use when work must move to another session, agent, or collaborator, whether unfinished or complete. |
| `strict-mode` | Apply the active strict operating profile through explicit skill selection, ordered execution, checkpoints, and fresh verification without expanding authority. Use when injected context says strict mode is active or the user explicitly requests strict execution. |
| `curating-skills` | Compare configured upstream skill changes against recorded revisions and local behavior, record accept or reject decisions, and update provenance only after validation. Use only when maintaining the mk-skills source repository and deliberately reviewing its configured upstream skill repositories. |
| `zellij-agent-herder` | Control Zellij panes, sessions, peer agents, waits, and live Hunk review streams using the bundled helpers. Use when running inside Zellij (`ZELLIJ` is set, including `0`) and the task requires pane orchestration, peer coordination, status waiting, or live diff watching. Requires Zellij 0.44 or newer. |

## Final File Map

### Create

- `skills/adversarial-refinement/SKILL.md`
- `skills/adversarial-refinement/references/challenge-lenses.md`
- `skills/reviewing-code/references/diff-provenance.md`
- `skills/reviewing-code/scripts/review-package`
- `skills/zellij-agent-herder/references/activation-hook.md`
- `skills/zellij-agent-herder/references/lifecycle-hooks.md`
- `skills/zellij-agent-herder/references/shared-agent-config.md`
- `skills/zellij-agent-herder/references/worktree-review-streams.md`
- `config/curation-decisions.json`
- `tests/helpers/skills.js`
- `tests/skills/activation-contracts.test.js`
- `tests/skills/adversarial-refinement.test.js`
- `tests/skills/review-package.test.js`
- `tests/fixtures/activation-cases.json`
- `docs/validation/skill-activation-forward-tests.md`

### Modify

- `skills/clarifying-work/SKILL.md`
- `skills/curating-skills/SKILL.md`
- `skills/diagnosing-bugs/SKILL.md`
- `skills/handing-off-work/SKILL.md`
- `skills/handling-review-feedback/SKILL.md`
- `skills/implementing-work/SKILL.md`
- `skills/planning-work/SKILL.md`
- `skills/reviewing-code/SKILL.md`
- `skills/specifying-work/SKILL.md`
- `skills/strict-mode/SKILL.md`
- `skills/test-driven-development/SKILL.md`
- `skills/verifying-work/SKILL.md`
- `skills/zellij-agent-herder/SKILL.md`
- `skills/zellij-agent-herder/references/command-reference.md` only if moved text leaves an inaccurate cross-reference
- `skills/zellij-agent-herder/references/peer-agents.md` only to correct routing or removed duplication
- `skills/zellij-agent-herder/references/pitfalls.md` only to correct routing or removed duplication
- `config/mode-policy.json`
- `config/sources.yaml`
- `tests/curation/test_review_upstreams.py`
- `tests/hooks/mode-policy.test.js`
- `tests/hooks/claude-adapter.test.js`
- `tests/skills/execution-contracts.test.js`
- `tests/skills/planning-contracts.test.js`
- `tests/skills/profile-behavior.test.js`
- `tests/skills/review-contracts.test.js`
- `tests/skills/structure.test.js`
- `scripts/validate.js`
- `README.md`
- `.gitignore`

### Remove after all links are migrated

- `skills/zellij-agent-herder/references/hooks.md`

Do not remove `hooks.md` until repository-wide search proves no current source, test, or README link still targets it.

## Execution Topology

Execute the tasks sequentially. Several tasks modify the same test and skill files, so parallel implementation would create unnecessary conflicts. A peer reviewer may review a fixed diff after a task, but the responsible executor must inspect the actual changes and rerun the task’s verification.

---

## Task 1: Add `adversarial-refinement` as a complete vertical slice

**Outcome:** A selectively invoked, self-contained pressure-testing skill exists with an optional deep-lens reference and explicit composition boundaries.

**Depends on:** None.

**Files:**

- Create: `tests/skills/adversarial-refinement.test.js`
- Create: `skills/adversarial-refinement/SKILL.md`
- Create: `skills/adversarial-refinement/references/challenge-lenses.md`
- Modify: `config/sources.yaml`
- Modify: `tests/curation/test_review_upstreams.py`
- Modify: `README.md`

### Test-first steps

- [ ] Add `tests/skills/adversarial-refinement.test.js` before creating the skill. Assert that the future base file contains:
  - both `interactive grill` and `artifact critique` modes;
  - local fact discovery before user questions;
  - steelmanning before criticism;
  - one material question at a time in interactive mode;
  - a recommended answer with each interactive question;
  - challenges covering assumptions, counterexamples, failure modes, downstream effects, reversibility, opportunity cost, and a strongest alternative;
  - risk-scaled stopping rather than exhaustive branch walking;
  - an outcome containing changes, rejected alternatives, unresolved decisions, and residual risks;
  - an explicit statement that the skill does not own implementation or external lifecycle actions;
  - a direct Markdown link to `references/challenge-lenses.md` with a condition describing when to read it.
- [ ] Assert that the base file does **not** require universal invocation, mandatory design documents, commits, implementation, or user approval after every section.
- [ ] Run `node --test tests/skills/adversarial-refinement.test.js` and confirm the failure is caused by the missing skill.

### Implementation steps

- [ ] Create `skills/adversarial-refinement/SKILL.md` with only `name` and the exact approved description in frontmatter.
- [ ] Keep the base body below 500 words. Use these sections: `Purpose and boundary`, `Choose a mode`, `Refinement loop`, `Exit and return`, and `Conditional reference`.
- [ ] In interactive mode, require one question per turn and a recommendation, but allow the user to stop or set a challenge budget.
- [ ] In artifact-critique mode, resolve discoverable facts autonomously and return a compact critique without manufacturing user questions.
- [ ] Create `references/challenge-lenses.md` with one-level sections for:
  - universal decision lenses;
  - product and user behavior;
  - specifications and interfaces;
  - architecture, data, security, and operations;
  - plans, rollout, and rollback;
  - diagnoses and competing hypotheses.
- [ ] Keep core challenge categories in `SKILL.md`; put extended prompts and examples in the reference to avoid making the base too lean.
- [ ] Add a direct base-file instruction: read the reference only when the artifact is consequential or a generic challenge has not exposed enough risk.
- [ ] Add `adversarial-refinement` to the README’s curated skill inventory.
- [ ] Add source mappings for `adversarial-refinement`:
  - Matt Pocock: `skills/productivity/grilling`;
  - Superpowers: `skills/brainstorming`.
  Existing mappings to `clarifying-work` remain; one upstream path may inform multiple local skills.
- [ ] Extend the checked-in provenance test to assert that both mappings exist and that every mapped `localSkill` has a real `skills/<name>/SKILL.md`.

### Verification

- [ ] Run `node --test tests/skills/adversarial-refinement.test.js tests/skills/structure.test.js`.
- [ ] Run `python3 -B -m unittest tests.curation.test_review_upstreams -v`.
- [ ] Inspect the base and reference together to confirm important workflow guidance is not duplicated.

**Review boundary:** The new skill can pressure-test any supported artifact without taking over clarification, specification, planning, implementation, or code review.

---

## Task 2: Strengthen front-end reasoning activation and refinement routing

**Outcome:** Clarification, specification, and planning activate from realistic requests and hand coherent but insufficiently tested artifacts to `adversarial-refinement` without making it mandatory.

**Depends on:** Task 1.

**Files:**

- Create: `tests/skills/activation-contracts.test.js`
- Create: `tests/helpers/skills.js`
- Modify: `skills/clarifying-work/SKILL.md`
- Modify: `skills/specifying-work/SKILL.md`
- Modify: `skills/planning-work/SKILL.md`
- Modify: `tests/skills/planning-contracts.test.js`
- Modify: `tests/skills/structure.test.js`

### Test-first steps

- [ ] Extract the existing simple frontmatter parser from `tests/skills/structure.test.js` into `tests/helpers/skills.js`. Export helpers to parse/read one skill, enumerate installed skill directories, and enumerate Markdown references. Preserve the current deliberately narrow two-field frontmatter contract; do not introduce a YAML dependency.
- [ ] Update `tests/skills/structure.test.js` and the new `tests/skills/activation-contracts.test.js` to use the shared helper rather than maintaining two parsers.
- [ ] Add cases for `clarifying-work`, `specifying-work`, and `planning-work`. For each case, assert that the description includes both the capability and the approved trigger vocabulary from “Exact description targets.”
- [ ] Update `tests/skills/structure.test.js` to stop requiring descriptions to begin with `Use when`. Continue requiring only `name` and `description` frontmatter, valid names, matching directories, and non-empty single-line descriptions.
- [ ] Add routing assertions:
  - `clarifying-work` routes to exact `adversarial-refinement` when the request is understood but a proposed direction needs pressure-testing;
  - `specifying-work` may route a consequential draft through exact `adversarial-refinement` before approval;
  - `planning-work` may route sequencing, dependency, rollout, or rollback assumptions through exact `adversarial-refinement`.
- [ ] Preserve negative assertions that peers, Zellij, trackers, worktrees, and commits remain optional.
- [ ] Run the focused tests and confirm failures point to the old descriptions and missing routes.

### Implementation steps

- [ ] Replace the three descriptions with the exact approved text.
- [ ] Add one concise conditional route to each base body. Do not add a second workflow loop or copy the adversarial skill’s challenge taxonomy.
- [ ] Use wording equivalent to:
  - clarification: “When the request is understood but a proposed direction remains insufficiently challenged, use `adversarial-refinement`; do not keep inventing clarification questions.”
  - specification: “For a consequential draft whose assumptions or alternatives need pressure-testing, use `adversarial-refinement` before seeking final approval.”
  - planning: “When sequencing, dependency, rollout, or rollback assumptions are materially uncertain, use `adversarial-refinement` on the draft plan.”
- [ ] Preserve the existing integration taxonomy in `clarifying-work`; it is core guidance and must not be moved to a reference.
- [ ] Preserve the specification shape and vertical-slice plan fields in their base files.

### Verification

- [ ] Run `node --test tests/skills/activation-contracts.test.js tests/skills/planning-contracts.test.js tests/skills/structure.test.js`.
- [ ] Read all three changed base files consecutively and confirm their responsibilities remain distinct.

**Review boundary:** The front-end skills activate more reliably and compose with adversarial refinement without adding universal design ceremony.

---

## Task 3: Strengthen execution activation and exact-name routing

**Outcome:** Direct implementation requests trigger `implementing-work`, while testable behavior and unknown causes route to the correct exact skill names.

**Depends on:** Task 2.

**Files:**

- Modify: `tests/skills/activation-contracts.test.js`
- Modify: `tests/skills/execution-contracts.test.js`
- Modify: `skills/test-driven-development/SKILL.md`
- Modify: `skills/diagnosing-bugs/SKILL.md`
- Modify: `skills/implementing-work/SKILL.md`

### Test-first steps

- [ ] Extend activation cases for `test-driven-development`, `diagnosing-bugs`, and `implementing-work` using the exact approved descriptions.
- [ ] Add an assertion that a direct request to “add,” “build,” “change,” “fix,” or “implement” behavior is covered by `implementing-work`; do not require a pre-existing reviewed plan.
- [ ] Add assertions that `implementing-work` names these routed skills exactly:
  - `clarifying-work` for consequential unresolved choices;
  - `specifying-work` when agreed behavior needs a reviewable contract;
  - `planning-work` for dependent multi-step work;
  - `adversarial-refinement` when a consequential proposal needs pressure-testing;
  - `test-driven-development` for observable behavior seams;
  - `diagnosing-bugs` while the cause is unknown;
  - `verifying-work` before completion claims;
  - `reviewing-code` when risk warrants a bounded review.
- [ ] Preserve all proportional-exception and no-external-ceremony assertions.
- [ ] Run the focused tests and observe the intended failures.

### Implementation steps

- [ ] Replace all three descriptions with the exact approved text.
- [ ] Replace the generic routing sentence in `implementing-work` with a compact condition-to-skill list using exact names.
- [ ] State that the router chooses the smallest applicable set; naming eight possible skills does not require loading all eight.
- [ ] In `diagnosing-bugs`, add only a narrow optional route to `adversarial-refinement` for a stuck investigation or suspiciously premature convergence. Competing hypotheses remain part of the debugging base loop.
- [ ] Do not add `adversarial-refinement` to the TDD cycle; TDD already supplies a direct behavioral discriminator.
- [ ] Preserve the existing implementation ownership boundary.

### Verification

- [ ] Run `node --test tests/skills/activation-contracts.test.js tests/skills/execution-contracts.test.js`.
- [ ] Run `node --test tests/skills/planning-contracts.test.js tests/skills/execution-contracts.test.js tests/skills/review-contracts.test.js` to catch cross-family wording regressions.

**Review boundary:** Straightforward implementation remains straightforward, bugs still diagnose before fixing, and routed skills are discoverable by exact name.

---

## Task 4: Strengthen review, verification, and handoff activation

**Outcome:** Review-family skills trigger from common user vocabulary and accepted feedback routes to testing, diagnosis, and verification by exact skill name.

**Depends on:** Task 3.

**Files:**

- Modify: `tests/skills/activation-contracts.test.js`
- Modify: `tests/skills/review-contracts.test.js`
- Modify: `skills/reviewing-code/SKILL.md`
- Modify: `skills/handling-review-feedback/SKILL.md`
- Modify: `skills/verifying-work/SKILL.md`
- Modify: `skills/handing-off-work/SKILL.md`

### Test-first steps

- [ ] Extend activation cases for all four review-family skills using the approved descriptions.
- [ ] Require `reviewing-code` trigger vocabulary to cover `diff`, `patch`, `pull request`, `commit range`, `audit`, and `review`.
- [ ] Require `verifying-work` trigger vocabulary to cover `verify`, `check`, `test`, `confirm`, and `prove`, plus readiness states.
- [ ] Require `handling-review-feedback` to name exact routes:
  - `diagnosing-bugs` when a claimed defect’s cause is uncertain;
  - `test-driven-development` when accepted feedback changes observable behavior;
  - `verifying-work` before closing an accepted item.
- [ ] Preserve review provenance, classification, fresh-evidence, redaction, and no-external-ceremony contracts.
- [ ] Run the focused tests and observe description/routing failures.

### Implementation steps

- [ ] Replace all four descriptions with the exact approved text.
- [ ] Add the three exact-name routes to the accepted-feedback section without copying the downstream workflows.
- [ ] Keep `verifying-work` compact and under 250 words after frontmatter, unless a focused test demonstrates that a slightly larger base materially improves execution.
- [ ] Do not add a handoff template reference: its current required fields are short enough to remain in the base.
- [ ] Do not turn ordinary code review into `adversarial-refinement`; code review already supplies a bounded adversarial pass over a fixed diff. Route to refinement only when the disputed object is an upstream design or decision rather than the code change itself.

### Verification

- [ ] Run `node --test tests/skills/activation-contracts.test.js tests/skills/review-contracts.test.js`.
- [ ] Confirm the four outcomes remain different: findings, feedback classification, completion evidence, and resumable transfer.

**Review boundary:** Common review requests activate reliably without merging distinct review workflows.

---

## Task 5: Make strict-mode activation explicit without losing fallback discipline

**Outcome:** A strict profile explicitly activates `strict-mode`, while the injected text remains sufficiently complete for smaller models that fail to load the skill.

**Depends on:** Task 4.

**Files:**

- Modify: `tests/skills/activation-contracts.test.js`
- Modify: `tests/hooks/mode-policy.test.js`
- Modify: `tests/hooks/claude-adapter.test.js`
- Modify: `tests/skills/profile-behavior.test.js`
- Modify: `skills/strict-mode/SKILL.md`
- Modify: `config/mode-policy.json`

### Test-first steps

- [ ] Add the exact `strict-mode` description to activation contracts.
- [ ] Require rendered strict context to state that the strict operating profile is active and name exact `strict-mode` with an instruction to read/apply it.
- [ ] Retain the 150–250 word strict-context budget.
- [ ] Retain direct fallback obligations in injected context: skill selection, dependent-step order, checkpoints, material-question threshold, evidence-driven changes, fresh verification, preserved unrelated work, and optional external lifecycle/orchestration.
- [ ] Require Codex and Claude outputs to contain identical strict-mode activation text.
- [ ] Run focused hook/profile tests and observe the missing activation sentence failure.

### Implementation steps

- [ ] Replace the `strict-mode` description with the exact approved text.
- [ ] Begin strict injected context with wording equivalent to: “The strict operating profile is active. Read and apply the `strict-mode` skill before acting.”
- [ ] Remove lower-value duplicated phrasing as needed to remain under 250 words, but keep the fallback obligations listed above.
- [ ] Keep the full expanded obligations and optional-orchestration boundary in `strict-mode/SKILL.md`.
- [ ] Do not make strict mode require `adversarial-refinement`; it remains a conditionally selected workflow.

### Verification

- [ ] Run `node --test tests/hooks/mode-policy.test.js tests/hooks/run-hook.test.js tests/hooks/claude-adapter.test.js tests/skills/profile-behavior.test.js tests/skills/activation-contracts.test.js`.
- [ ] Count rendered strict-context words from the test output or a one-line Node inspection and record the exact count.

**Review boundary:** Strict mode has one named expanded workflow and one compact fail-safe bootstrap, with identical host behavior.

---

## Task 6: Add deterministic review-package generation and provenance guidance

**Outcome:** Reviewers can receive a stable multi-commit comparison in one artifact without truncating the range or flooding the controlling agent’s context.

**Depends on:** Task 4. May be implemented after Task 5.

**Files:**

- Create: `tests/skills/review-package.test.js`
- Create: `skills/reviewing-code/scripts/review-package`
- Create: `skills/reviewing-code/references/diff-provenance.md`
- Modify: `skills/reviewing-code/SKILL.md`
- Modify: `tests/skills/review-contracts.test.js`

### Contract

The public command is:

```bash
"<skill-base-dir>/scripts/review-package" BASE HEAD
```

It must:

- run inside the repository being reviewed;
- require two explicit revisions;
- verify both revisions resolve to commits and `BASE` is an ancestor of `HEAD`;
- create a uniquely named Markdown file under `${TMPDIR:-/tmp}` using `mktemp` or an equivalently safe primitive;
- include repository root, resolved base SHA, resolved head SHA, commit list for `BASE..HEAD`, diff stat, and full `git diff --no-ext-diff --find-renames --unified=10 BASE HEAD`;
- print only the generated file path to stdout on success;
- write errors to stderr and exit nonzero without producing a misleading partial package;
- leave the repository unchanged.

### Test-first steps

- [ ] Create a temporary Git repository in `tests/skills/review-package.test.js` using Node standard-library helpers and `spawnSync`.
- [ ] Record a base, create two commits, run the future script over the full range, and assert both commit subjects and both file changes appear.
- [ ] Assert that the output contains the base/head SHAs and stat. Construct fixture files with enough unchanged surrounding lines to prove the diff retained ten lines of context rather than the default three.
- [ ] Assert the generated file is outside the fixture repository and the fixture working tree remains clean.
- [ ] Assert invalid revisions and a non-ancestor base fail without printing a package path.
- [ ] Add a regression assertion demonstrating that the recorded base covers both commits; never construct the expected range with `HEAD~1`.
- [ ] Run `node --test tests/skills/review-package.test.js` and confirm failure is the missing script.

### Implementation steps

- [ ] Implement the script in portable POSIX shell and mark it executable.
- [ ] Quote every path and revision. Do not evaluate revision strings as shell source.
- [ ] Use a cleanup trap so a failed package is removed; clear the trap only after the complete file is written.
- [ ] Create `references/diff-provenance.md` covering:
  - fixed base/head committed ranges;
  - recording `BASE` before implementation or peer dispatch;
  - why `HEAD~1` truncates multi-commit work;
  - staged and unstaged working-tree inspection;
  - untracked-file inventory using `git ls-files --others --exclude-standard`;
  - declaring generated or excluded content;
  - rechecking that the comparison point has not moved before reporting.
- [ ] In `reviewing-code/SKILL.md`, keep the fixed-comparison rule in the base, add the package command, and link directly to the reference with “read when the review includes staged, unstaged, untracked, generated, or mixed state.”
- [ ] State that the package covers committed `BASE..HEAD`; working-tree state requires the additional reference procedure and explicit provenance.

### Verification

- [ ] Run `node --test tests/skills/review-package.test.js tests/skills/review-contracts.test.js tests/skills/structure.test.js`.
- [ ] Run `shellcheck skills/reviewing-code/scripts/review-package` when `shellcheck` is available.
- [ ] Manually inspect one generated package and confirm the stdout contract is path-only.

**Review boundary:** A reviewer receives the complete fixed range, while working-tree inclusion remains explicit rather than silently partial.

---

## Task 7: Make upstream curation portable and decisions durable

**Outcome:** An installed maintainer skill can curate a checked-out mk-skills repository from any working directory inside that checkout, and completed upstream decisions are recorded instead of disappearing when pins advance.

**Depends on:** Task 1 source mappings.

**Files:**

- Create: `config/curation-decisions.json`
- Modify: `skills/curating-skills/SKILL.md`
- Modify: `config/sources.yaml`
- Modify: `tests/curation/test_review_upstreams.py`
- Modify: `README.md`

### Approved portability model

`curating-skills` is a maintainer workflow, not a generic installed-skill curator. Its script remains bundled with the skill, while the target repository provides `config/sources.yaml`, `config/curation-decisions.json`, local skills, tests, and notices. The skill must discover the target checkout explicitly and must not claim to work without it.

### Decision-ledger schema

Create JSON with this shape:

```json
{
  "version": 1,
  "decisions": [
    {
      "source": "matt-pocock-skills",
      "fromCommit": "9603c1cc8118d08bc1b3bf34cf714f62178dea3b",
      "toCommit": "ed37663cc5fbef691ddfecd080dff42f7e7e350d",
      "decision": "accept",
      "disposition": "no-local-change",
      "localSkills": ["planning-work"],
      "summary": "Upstream removed a redundant instruction to execute tickets one at a time.",
      "rationale": "Local planning-work already separates planning from implementation and therefore already embodies the change.",
      "validation": [
        "python3 -B -m unittest tests.curation.test_review_upstreams -v",
        "node scripts/validate.js"
      ]
    }
  ]
}
```

Allowed `decision` values are exactly `accept` and `reject`. Allowed `disposition` values are `adapted`, `no-local-change`, and `rejected`. Commit fields are full 40-character lowercase hexadecimal SHAs.

The example records the upstream head observed on 2026-07-21. If a fresh implementation-time review reports a later head, do not copy this range blindly: add decisions covering all newly included relevant changes and set `toCommit` to the exact head actually reviewed.

### Test-first steps

- [ ] Replace the provenance test’s assumption that every reviewed commit is permanently hardcoded in test source with assertions over manifest shape, exact source set, real local skills, notices, and the decision ledger.
- [ ] Add ledger validation for required fields, enum values, commit shape, known source names, and real local skill names.
- [ ] Add a focused assertion for the currently approved Matt Pocock decision from `9603c1cc8118d08bc1b3bf34cf714f62178dea3b` to the exact fetched head represented by the generated review bundle.
- [ ] Add a test or source inspection proving the skill command uses `<skill-base-dir>/scripts/review-upstreams.py` and a discovered repository root rather than `skills/curating-skills/scripts/...` relative to the current directory.
- [ ] Run curation tests and observe failures for the missing ledger and old command.

### Implementation steps

- [ ] Replace the description with the exact approved maintainer-only text.
- [ ] Change the documented command to this logical sequence:

  ```bash
  REPO_ROOT="$(git rev-parse --show-toplevel)"
  python3 "<skill-base-dir>/scripts/review-upstreams.py" \
    --manifest "$REPO_ROOT/config/sources.yaml" \
    --output /tmp/upstream-review.md
  ```

- [ ] Before running, require inspection of `$REPO_ROOT/.codex-plugin/plugin.json` and confirm its `name` is `mk-skills`. Fail clearly if the current repository is not the target project.
- [ ] Tell the executor to read `config/curation-decisions.json` before making new decisions and append one record spanning the prior pin to the reviewed head.
- [ ] Regenerate the upstream review at implementation time. If Matt Pocock’s upstream has advanced beyond the one known commit, review and record every newly covered relevant change before advancing the pin.
- [ ] Record the approved no-local-change decision shown above, using the exact current fetched head and the commands actually run.
- [ ] Advance `matt-pocock-skills.reviewedCommit` only after the ledger record and full validation are complete. Do not change the Spec Kitty or Superpowers pins unless their freshly generated reports contain reviewed changes with recorded decisions.
- [ ] Update README wording: ordinary execution skills are self-contained and offline; curation additionally requires an mk-skills source checkout and deliberate network access.

### Verification

- [ ] From a nested directory inside the repository, run the installed or workspace skill script using the new documented path model and generate a report.
- [ ] Run `python3 -B -m unittest tests.curation.test_review_upstreams -v`.
- [ ] With local adaptations and the ledger record complete but the old pin still present, run the affected skill tests and `node scripts/validate.js`.
- [ ] Advance the pin only after that validation passes, then rerun the curation tests and `node scripts/validate.js` because the manifest is a relevant input to the completion claim.
- [ ] Confirm `git diff -- config/sources.yaml config/curation-decisions.json` shows a decision range ending exactly at the advanced pin.

**Review boundary:** Every advanced pin is backed by a durable decision; installed skill paths no longer depend on repository-root cwd assumptions.

---

## Task 8: Rechunk `zellij-agent-herder` around explicit read conditions

**Outcome:** The base skill remains sufficiently operational for everyday pane work while specialized installation, shared-config, and worktree-review workflows load only when needed.

**Depends on:** Task 2 structure-test changes. Independent of Tasks 6–7 after that dependency.

**Files:**

- Modify: `tests/skills/structure.test.js`
- Modify: `skills/zellij-agent-herder/SKILL.md`
- Create: `skills/zellij-agent-herder/references/activation-hook.md`
- Create: `skills/zellij-agent-herder/references/lifecycle-hooks.md`
- Create: `skills/zellij-agent-herder/references/shared-agent-config.md`
- Create: `skills/zellij-agent-herder/references/worktree-review-streams.md`
- Modify if necessary: `skills/zellij-agent-herder/references/command-reference.md`
- Modify if necessary: `skills/zellij-agent-herder/references/peer-agents.md`
- Modify if necessary: `skills/zellij-agent-herder/references/pitfalls.md`
- Remove after migration: `skills/zellij-agent-herder/references/hooks.md`
- Modify: `README.md`

### Target base contents

Keep these in `SKILL.md`:

- the `$ZELLIJ` presence guard, including `ZELLIJ=0`;
- session → tabs → panes hierarchy and `(session, pane_id)` addressing;
- session targeting and title-versus-address distinction;
- the critical rule to spawn only through `zj_spawn` because attached and headless behavior differ;
- skill-base-relative helper loading for POSIX and non-POSIX shells;
- the core quick-reference table;
- short conditional routes to peer workflows, worktree/Hunk streams, activation hooks, lifecycle hooks, shared configuration, command details, and troubleshooting;
- one non-negotiable worktree warning: capture one fixed branch-point `BASE` before fan-out and never substitute advancing `main` or current `HEAD`.

Target 500–800 body words. Do not reduce the base to a pure table of contents.

### Target reference boundaries

- `activation-hook.md`: only reliable skill-discovery hook installation, behavior, and removal.
- `lifecycle-hooks.md`: status, identity, origin, auto-diff hook installation, trust, event mapping, and ownership-scoped uninstall. Worktree/live-session operation remains in the separately base-linked `worktree-review-streams.md`; neither reference is required to discover the other.
- `shared-agent-config.md`: shared `AGENTS.md`/Claude guidance and Hindsight setup, validation, backup, and local-source installation.
- `worktree-review-streams.md`: headless worktree watchers, fixed-base capture, stream identity, fan-out, roll-up, explicit reopen, placement behavior, Hunk review-skill handoff, and lineage titles.
- `command-reference.md`: helper signatures and verified Zellij command semantics.
- `peer-agents.md`: peer wrapper lifecycle and prompting.
- `pitfalls.md`: symptoms, sharp edges, and troubleshooting.

### Test-first steps

- [ ] Extend `tests/skills/structure.test.js` to enumerate every `references/**/*.md` under every skill.
- [ ] Require every reference Markdown file to be linked directly from its owning `SKILL.md`.
- [ ] Require all local Markdown links in both base files and references to resolve.
- [ ] Require each base-to-reference link to appear in a sentence or bullet containing a read condition such as `Read`, `when`, `for`, or `required reference`; keep the check simple enough to avoid testing prose style.
- [ ] Add an explicit Zellij base budget of at most 800 body words instead of an unlimited allowlist.
- [ ] Run the structure test and observe failures caused by plain-text pointers, the oversized base, or newly expected reference layout.

### Implementation steps

- [ ] Replace the Zellij description with the exact approved text, including the corrected possessive grammar and version wording.
- [ ] Convert every reference route to a real Markdown link. Do not use `@` syntax.
- [ ] Replace “REQUIRED SUB-SKILL” for `peer-agents.md` with “REQUIRED REFERENCE” because it is a bundled document, not another installed skill.
- [ ] Move content from the old base and `hooks.md` into the target references. Move rather than duplicate.
- [ ] Preserve the instruction to run `hunk skill path` and read the installed `hunk-review` skill completely before annotating a live session.
- [ ] Keep all reference files one level from `SKILL.md`; references must not require another reference to discover required instructions.
- [ ] Update README links:
  - lifecycle/status/Hunk hook setup → `references/lifecycle-hooks.md`;
  - shared guidance/Hindsight setup → `references/shared-agent-config.md`;
  - worktree/Hunk operation → `references/worktree-review-streams.md` where applicable.
- [ ] Search before removing the old file:

  ```bash
  rg -n 'references/hooks\.md|hooks\.md' README.md skills tests docs
  ```

- [ ] Remove `references/hooks.md` only when all live links are migrated. Historical design/plan documents may remain historical if they are explicitly describing the old layout; otherwise update links that readers are expected to follow.
- [ ] Re-read the scripts and current references before changing any technical claim about events, helper signatures, placement, or cache identity.

### Verification

- [ ] Run `node --test tests/skills/structure.test.js tests/skills/profile-behavior.test.js`.
- [ ] Run all Zellij-owned suites:

  ```bash
  python3 -B skills/zellij-agent-herder/tests/test-pane-identity.py -v
  python3 -B skills/zellij-agent-herder/tests/test-hunk-focus-guard.py -v
  bash skills/zellij-agent-herder/tests/test-hunk-stream.sh
  bash skills/zellij-agent-herder/tests/test-install-hooks.sh
  bash skills/zellij-agent-herder/tests/test-shared-agent-config.sh
  ```

- [ ] Run `shellcheck -x skills/zellij-agent-herder/scripts/*.sh skills/zellij-agent-herder/references/hooks/*.sh` and distinguish pre-existing non-blocking warnings from introduced warnings.
- [ ] Count base words and record the result; confirm the file still contains executable everyday guidance.

**Review boundary:** Common pane work requires only the base; each specialized operation has one obvious directly linked reference.

---

## Task 9: Unify validation and prevent generated Python cache noise

**Outcome:** The documented validator actually runs every repository-owned skill suite and reports optional plugin-schema limitations accurately.

**Depends on:** Tasks 1–8.

**Files:**

- Modify: `scripts/validate.js`
- Modify: `tests/hooks/claude-adapter.test.js`
- Modify: `.gitignore`
- Modify: `README.md`

### Test-first steps

- [ ] Extend the validator source-contract test to require all five Zellij-owned commands after top-level skill tests and before the final diff check.
- [ ] Require Python invocations owned by the validator to use `-B` or an equivalent `PYTHONDONTWRITEBYTECODE=1` environment so validation does not create new `__pycache__` directories.
- [ ] Require plugin-schema skip output to distinguish at least:
  - validator file absent;
  - validator present but PyYAML unavailable.
- [ ] Run `node --test tests/hooks/claude-adapter.test.js` and observe the missing-suite assertions fail.

### Implementation steps

- [ ] Add the two Zellij Python tests and three Zellij shell tests to `scripts/validate.js` with clear labels.
- [ ] Use `python3 -B` for curation and Zellij Python tests.
- [ ] Preserve fail-fast ordering: top-level contracts, curation, Zellij helpers, optional plugin schema, then `git diff --check`.
- [ ] Make skip diagnostics precise without turning PyYAML into a required runtime dependency for installed skills.
- [ ] Add `__pycache__/` and `*.pyc` to `.gitignore`. Do not delete pre-existing untracked cache content as part of this task.
- [ ] Update README so `node scripts/validate.js` accurately describes every included suite and the optional plugin-schema dependency.

### Verification

- [ ] Run `node --test tests/hooks/claude-adapter.test.js`.
- [ ] Run `node scripts/validate.js` and confirm every labeled suite executes.
- [ ] Run `git status --short` and confirm validation did not create new untracked cache paths.

**Review boundary:** The one-command validator proves the repository’s actual skill surface, including the bundled Zellij implementation.

---

## Task 10: Add activation fixtures and a repeatable clean-session evaluation

**Outcome:** Maintainers can detect under-triggering, over-triggering, and incorrect reference loading that static phrase tests cannot prove.

**Depends on:** Tasks 1–9.

**Files:**

- Create: `tests/fixtures/activation-cases.json`
- Create: `docs/validation/skill-activation-forward-tests.md`
- Modify: `tests/skills/activation-contracts.test.js`
- Modify: `README.md`

### Fixture schema

Each case must contain:

```json
{
  "id": "stable-kebab-case-id",
  "prompt": "The raw prompt sent to a clean session.",
  "expectedSkills": ["skill-name"],
  "forbiddenSkills": ["skill-name"],
  "expectedReferences": ["skills/name/references/file.md"],
  "rubric": ["Observable behavior expected from the response."]
}
```

An empty expected or forbidden list is valid. Every named skill and reference must exist.

### Required cases

- [ ] Ambiguous cross-system change → `clarifying-work`; integration risks surfaced.
- [ ] Explicit “write a specification with acceptance criteria” → `specifying-work`.
- [ ] Explicit “make an implementation plan” → `planning-work`.
- [ ] Explicit “use TDD/write tests first” → `test-driven-development`.
- [ ] Flaky unexplained failure → `diagnosing-bugs`, not immediate implementation.
- [ ] Direct clear “add/build/change/implement” request → `implementing-work` without requiring a formal spec.
- [ ] “Review this diff/patch/PR” → `reviewing-code`; load diff provenance only when mixed working-tree state is present.
- [ ] Review comments needing assessment → `handling-review-feedback`.
- [ ] “Verify/check/confirm this is ready” → `verifying-work`.
- [ ] Resume in another session → `handing-off-work`.
- [ ] Explicit strict execution → `strict-mode`.
- [ ] Deliberate upstream review inside mk-skills → `curating-skills`.
- [ ] Zellij pane-control prompt with environment context indicating `ZELLIJ=0` → `zellij-agent-herder`; load only the relevant reference.
- [ ] “Grill me on this architecture decision” → `adversarial-refinement` interactive mode.
- [ ] “Stress-test this rollout plan and return findings” → `adversarial-refinement` artifact-critique mode, optionally composed with `planning-work`.
- [ ] Trivial typo or local mechanical edit → no `adversarial-refinement`, specification, or plan ceremony.
- [ ] Straightforward specification request → no automatic adversarial refinement unless risk or the prompt requests it.

### Test-first steps

- [ ] Extend `activation-contracts.test.js` to validate fixture schema, unique ids, non-empty prompts/rubrics, real skill names, and real reference paths.
- [ ] Make the test fail before creating the fixture.
- [ ] Create the complete fixture with the required cases and make the schema test pass.

### Evaluation procedure

- [ ] Write `docs/validation/skill-activation-forward-tests.md` for a maintainer with no conversation context. Include:
  1. validate and install/link the exact branch under test;
  2. start a clean selective-profile Codex or Claude session per case;
  3. send only the raw fixture prompt, without expected skills or rubric;
  4. inspect available trace/context output for loaded skills and references;
  5. compare behavior with the rubric;
  6. record false negatives, false positives, unnecessary references, and behavior failures separately;
  7. repeat representative failures after a description/body change;
  8. run at least the adversarial, direct-implementation, trivial-edit, mixed-state review, and Zellij-reference cases on both hosts before release.
- [ ] Explicitly forbid leaking expected answers, suspected bugs, or intended fixes into clean-session prompts.
- [ ] State that static tests validate contracts but do not substitute for clean-session activation evidence.
- [ ] Link the forward-test guide from README’s validation section.

### Verification

- [ ] Run `node --test tests/skills/activation-contracts.test.js`.
- [ ] Run at least one Codex and one Claude smoke case if both hosts are available; otherwise record the unavailable host as a limitation rather than predicting parity.

**Review boundary:** Activation quality has a durable evaluation surface without adding a network-dependent test to normal repository validation.

---

## Task 11: Whole-repository verification and plan-to-implementation audit

**Outcome:** All approved recommendations are implemented, provenance is accurate, and no completion claim exceeds fresh evidence.

**Depends on:** Tasks 1–10.

### Required inspections

- [ ] Run `rg --hidden --files -g '!.git/**' skills | sort` and confirm every expected base, script, and reference exists and no obsolete `references/hooks.md` remains.
- [ ] Run `rg -n 'description:|adversarial-refinement|references/hooks\.md|HEAD~1|REQUIRED SUB-SKILL|it.s presence' skills README.md tests config` and inspect every match rather than relying on absence/presence alone.
- [ ] Confirm every skill description matches the approved description table.
- [ ] Confirm every cross-skill route uses exact names and remains conditional.
- [ ] Confirm every reference is directly linked from its base with a read condition.
- [ ] Confirm `adversarial-refinement` does not own implementation, commits, or universal approval gates.
- [ ] Confirm the curation ledger range and `reviewedCommit` agree exactly.
- [ ] Confirm README does not claim generic standalone curation without a source checkout.

### Fresh verification

- [ ] Run `node scripts/validate.js` and retain the full output and exit status.
- [ ] If PyYAML is available, run the configured plugin validator. If unavailable, report the precise skip and do not claim plugin-schema validation passed.
- [ ] Run `git diff --check` even if the unified validator already ran it, if any file changed after that run.
- [ ] Run `git status --short` and identify all pre-existing, implementation-created, and unrelated paths.
- [ ] Review the complete diff against the recorded base, not `HEAD~1`. For a multi-commit implementation, use `skills/reviewing-code/scripts/review-package BASE HEAD` once it exists.
- [ ] For a broad or risky diff, obtain an independent review with the same fixed provenance; peer output is evidence to verify, not proof of completion.

### Self-review checklist

- [ ] **Coverage map:** Map each Global Constraint and Approved Design Decision to at least one implemented task and test. List any gap explicitly.
- [ ] **Placeholder scan:** Search new and changed non-historical files for `TODO`, `TBD`, placeholder paths, fake SHAs, and incomplete examples. Replace or explain every match.
- [ ] **Contradiction scan:** Compare README, descriptions, base bodies, references, policy text, tests, provenance, and actual scripts for conflicting claims.
- [ ] **Context-load scan:** Ensure no base became so lean that its essential loop moved behind a reference, and no specialized reference material remains duplicated in the base.
- [ ] **Authority scan:** Ensure no skill now requires commits, PRs, trackers, worktrees, peers, releases, or destructive/external actions without explicit authority.
- [ ] **Claim/evidence map:** In the implementation handoff, report each completed behavior beside the fresh command or inspection that proves it and state any unrun host or optional validator.

**Final acceptance:** The repository activates the right skills from realistic language, pressure-tests ideas only when useful, loads specialized references on demand, generates stable review packages, records upstream decisions durably, validates the entire bundled skill surface, and preserves selective low-ceremony execution for trivial work.
