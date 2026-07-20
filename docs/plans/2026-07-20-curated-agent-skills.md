# Curated Agent Skills Implementation Plan

> Execute task-by-task. Each task is independently reviewable and may run inline or through `zellij-agent-herder`; peer execution is optional. Mark checkboxes as work is verified.

**Goal:** Ship a self-contained Codex-first skill plugin with selective and strict operating profiles, a required Claude Code adapter, upstream curation tooling, and optional composition with `zellij-agent-herder`.

**Architecture:** Portable skills live under `skills/`. A shared Node.js selector reads a harness-neutral JSON policy and emits host-specific `SessionStart` context through thin Codex and Claude hook adapters. Python standard-library tooling reviews pinned upstream revisions recorded in JSON-compatible YAML. Node's built-in test runner and Python's built-in unittest framework keep the repository dependency-free.

**Tech stack:** Markdown Agent Skills, Node.js 20+ standard library, Python 3.11+ standard library, JSON-compatible YAML, Codex and Claude Code command hooks.

## Global Constraints

- Default to selective invocation; strict mode is injected only by policy or explicit override.
- Unknown models and malformed overrides fail open to `selective` with a concise diagnostic.
- Do not inspect unstable Codex transcript internals for reasoning effort.
- No core skill may require commits, PRs, trackers, worktrees, zellij, Herdr, subagents, or network access.
- `zellij-agent-herder` remains independently usable and unmodified unless a verified documentation defect is found.
- Claude compatibility is required before the project is complete.
- Preserve unrelated working-tree changes.

## File Map

- `.codex-plugin/plugin.json`: Codex plugin metadata and skill discovery.
- `hooks/hooks.json`: shared lifecycle declaration discovered by Codex and packaged for Claude.
- `hooks/run-hook.js`: host adapter; reads stdin, selects mode, emits the correct hook payload.
- `lib/mode-policy.js`: pure policy loading, validation, matching, and context rendering.
- `config/mode-policy.json`: model rules, defaults, and injected strict/selective text.
- `adapters/claude/hooks.json`: Claude-facing hook declaration using the shared runner.
- `skills/*/SKILL.md`: eleven new portable skills plus the existing zellij skill.
- `skills/curating-skills/scripts/review-upstreams.py`: deterministic upstream change report.
- `config/sources.yaml`: JSON-compatible YAML provenance manifest.
- `THIRD_PARTY_NOTICES.md`: upstream MIT attribution and conceptual provenance.
- `tests/hooks/*.test.js`: selector and adapter tests.
- `tests/skills/*.test.js`: structural and behavioral-contract tests.
- `tests/curation/test_review_upstreams.py`: hermetic curation tests.
- `tests/fixtures/`: hook inputs, policy variants, miniature git remotes, and skill scenarios.
- `scripts/validate.js`: one-command structural validation.
- `README.md`: installation, profiles, overrides, curation, and Claude fast-follow usage.

---

### Task 1: Shared mode policy and strict context

**Depends on:** None

**Files:**

- Create: `lib/mode-policy.js`
- Create: `config/mode-policy.json`
- Create: `tests/hooks/mode-policy.test.js`
- Create: `tests/fixtures/policies/valid.json`
- Create: `tests/fixtures/policies/malformed.json`

**Interfaces:**

- Produce `loadPolicy(path): { policy, diagnostics }`.
- Produce `selectMode({ model, override, policy }): { mode, reason, diagnostics }`.
- Produce `renderContext({ mode, policy }): string`.
- Supported modes are exactly `strict`, `selective`, and `off`.
- Override variable name is `MK_SKILLS_MODE`.

- [ ] **Step 1: Write failing policy tests**

Cover these exact cases with `node:test` and `node:assert/strict`:

1. `MK_SKILLS_MODE=strict|selective|off` wins over model rules.
2. A configured smaller-model regex selects `strict`.
3. A configured capable-model regex selects `selective`.
4. An unknown model selects the configured default `selective`.
5. An invalid override selects `selective` and records one diagnostic.
6. Missing or malformed policy selects a built-in selective fallback.
7. `renderContext({mode: "off"})` returns an empty string.
8. Strict context is between 150 and 250 words and explicitly requires ordered checkpoints and fresh verification while explicitly leaving commits, PRs, trackers, worktrees, and peers optional.
9. Selective context is under 100 words and tells the model to load skills only on clear triggers.

- [ ] **Step 2: Confirm the tests fail**

Run: `node --test tests/hooks/mode-policy.test.js`

Expected: failure because `lib/mode-policy.js` and policy fixtures do not exist.

- [ ] **Step 3: Implement the pure selector**

Use only `node:fs` and `node:path`. Validate the parsed policy shape before matching. Treat model rules as ordered entries with `{ "pattern": "...", "mode": "..." }`; the first matching regex wins. Catch invalid regexes, append diagnostics, and continue. Never throw from the exported selection path.

The checked-in policy must contain:

```json
{
  "version": 1,
  "defaultMode": "selective",
  "modelRules": [],
  "contexts": {
    "selective": "...",
    "strict": "..."
  }
}
```

Leave `modelRules` empty until tests or documented model identifiers justify entries. Document explicit overrides as the reliable mechanism for low reasoning effort.

- [ ] **Step 4: Verify the policy tests pass**

Run: `node --test tests/hooks/mode-policy.test.js`

Expected: all nine cases pass with no network access.

**Review boundary:** Policy decisions are pure, deterministic, fail-open, and independent of either harness.

---

### Task 2: Codex plugin and lifecycle hook

**Depends on:** Task 1

**Files:**

- Create: `.codex-plugin/plugin.json`
- Create: `hooks/hooks.json`
- Create: `hooks/run-hook.js`
- Create: `tests/hooks/run-hook.test.js`
- Create: `tests/fixtures/hooks/codex-session-start.json`
- Create: `tests/fixtures/hooks/unknown-model.json`

**Interfaces:**

- `run-hook.js` reads one JSON event from stdin.
- It resolves plugin files from `PLUGIN_ROOT`, then `CLAUDE_PLUGIN_ROOT`, then its own directory.
- Codex input consumes `hook_event_name`, `model`, and `cwd` only.
- Codex output must inject selected context using the documented/session-compatible output shape verified against the installed Codex hook schema.
- Exit code remains zero for malformed input, with selective fallback output and a concise diagnostic.

- [ ] **Step 1: Write failing adapter tests**

Spawn `node hooks/run-hook.js` with fixture JSON and controlled environment variables. Assert:

1. Startup with explicit strict override returns strict context.
2. Startup with `off` returns no injected context.
3. Unknown model returns selective context.
4. Malformed stdin exits zero and returns selective context plus a diagnostic.
5. `startup`, `resume`, `clear`, and `compact` all use the same selector.
6. Output parses as JSON and contains no absolute checkout path.

- [ ] **Step 2: Confirm the adapter tests fail**

Run: `node --test tests/hooks/run-hook.test.js`

Expected: failure because the runner and hook declarations do not exist.

- [ ] **Step 3: Add the plugin manifest and hook**

Create a minimal valid manifest named `mk-skills`, version `0.1.0`, with repository, author, license, description, interface metadata, and `skills: "./skills/"`. Rely on default `hooks/hooks.json` discovery rather than adding a manifest field rejected by the local validator.

Configure `SessionStart` for `startup|resume|clear|compact`, synchronous command execution, a short timeout, and the shared runner. Use plugin-root environment variables rather than the session working directory.

- [ ] **Step 4: Implement Codex output adaptation**

Keep host-shape conversion in `run-hook.js`; keep mode logic in `lib/mode-policy.js`. Do not read transcript files. Ensure diagnostics are visible but do not replace the selected context.

- [ ] **Step 5: Run focused tests and validate the plugin**

Run:

```bash
node --test tests/hooks/mode-policy.test.js tests/hooks/run-hook.test.js
python3 /Users/mike/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

Expected: all hook tests pass and the plugin validator exits zero.

**Review boundary:** Codex can discover the plugin and inject the shared policy on every required session lifecycle path.

---

### Task 3: Clarification, specification, and planning skills

**Depends on:** Task 1

**Files:**

- Create: `skills/clarifying-work/SKILL.md`
- Create: `skills/specifying-work/SKILL.md`
- Create: `skills/planning-work/SKILL.md`
- Create: `tests/skills/structure.test.js`
- Create: `tests/skills/planning-contracts.test.js`

**Interfaces:**

- Every skill has valid `name` and trigger-only `description` frontmatter.
- `clarifying-work` produces only material questions and an integration map when warranted.
- `specifying-work` produces problem, behavior, constraints, acceptance criteria, seams, and non-goals.
- `planning-work` produces vertical slices with dependencies, expected outputs, and verification.
- Plans remain executable inline or as peer-agent briefs.

- [ ] **Step 1: Write failing structural and contract tests**

Structural tests enumerate every skill directory and assert valid frontmatter, matching directory/name, no broken local Markdown links, and a 500-word budget for new core skills unless explicitly allowlisted.

Contract tests assert the three skill bodies contain the approved positive behaviors and do not contain unconditional requirements to interview, commit, create a worktree, publish tracker tickets, or dispatch peers.

- [ ] **Step 2: Confirm the tests fail**

Run: `node --test tests/skills/structure.test.js tests/skills/planning-contracts.test.js`

Expected: failure listing the three missing skills.

- [ ] **Step 3: Write `clarifying-work`**

Adapt the `mk-clarify` taxonomy into a compact risk-scaled reference: integration consumers, failure modes, schema propagation, lifecycle, authorization, dependency scope, configuration, and edge cases. Direct the agent to discover facts locally, rank uncertainties by rework risk, and ask one material question at a time only when needed.

- [ ] **Step 4: Write `specifying-work` and `planning-work`**

Use synthesis-first specification and tracer-bullet planning. Make approvals conditional on material unresolved choices. Explicitly state that peer-ready task boundaries improve portability but do not imply peer execution.

- [ ] **Step 5: Verify the skill contracts**

Run: `node --test tests/skills/structure.test.js tests/skills/planning-contracts.test.js`

Expected: all structural and planning contract tests pass.

**Review boundary:** Front-end reasoning is integration-aware and reviewable without imposing Superpowers' universal ceremony.

---

### Task 4: TDD, debugging, and implementation skills

**Depends on:** Task 3

**Files:**

- Create: `skills/test-driven-development/SKILL.md`
- Create: `skills/diagnosing-bugs/SKILL.md`
- Create: `skills/implementing-work/SKILL.md`
- Create: `tests/skills/execution-contracts.test.js`

**Interfaces:**

- TDD guidance returns a behavior seam, red evidence, minimal green change, and fresh verification when applicable.
- Debugging guidance returns a reproduction, minimized evidence, tested hypothesis, cause-level fix, and regression protection or a documented limitation.
- Implementation guidance consumes a request/spec/plan and routes to applicable skills without owning external lifecycle state.

- [ ] **Step 1: Write failing execution-contract tests**

Assert required concepts and prohibited unconditional workflow requirements. Include fixtures representing a behavior change, mechanical rename, generated file update, reproducible bug, and non-reproducible bug.

- [ ] **Step 2: Confirm the tests fail**

Run: `node --test tests/skills/execution-contracts.test.js`

Expected: failure listing missing execution skills.

- [ ] **Step 3: Write the three skills**

For TDD, preserve public behavior, independent expected values, narrow red-green slices, and proportional exceptions. For debugging, use a tight loop and competing hypotheses before edits. For implementation, keep the body a small router that scales verification and review to risk.

- [ ] **Step 4: Verify focused and cumulative skill tests**

Run: `node --test tests/skills/*.test.js`

Expected: all skill tests pass.

**Review boundary:** Implementation discipline remains evidence-driven while low-value ceremony is explicitly avoided.

---

### Task 5: Review, feedback, verification, and handoff skills

**Depends on:** Task 4

**Files:**

- Create: `skills/reviewing-code/SKILL.md`
- Create: `skills/handling-review-feedback/SKILL.md`
- Create: `skills/verifying-work/SKILL.md`
- Create: `skills/handing-off-work/SKILL.md`
- Create: `tests/skills/review-contracts.test.js`

**Interfaces:**

- Review accepts a fixed comparison point and optional spec, then reports findings by severity across correctness/risk, spec, and standards axes.
- Feedback handling classifies each item as accepted, rejected with evidence, or clarification-needed.
- Verification maps each completion claim to fresh evidence.
- Handoff writes a temporary, redacted summary that references durable artifacts.

- [ ] **Step 1: Write failing review-contract tests**

Assert the skills require fixed diff provenance, separate review axes, technical evaluation of feedback, fresh evidence, secret redaction, and references instead of artifact duplication. Assert peers are optional and peer reports require primary verification.

- [ ] **Step 2: Confirm the tests fail**

Run: `node --test tests/skills/review-contracts.test.js`

Expected: failure listing four missing skills.

- [ ] **Step 3: Write the four concise skills**

Keep `verifying-work` under 250 words because it may trigger frequently. Let `reviewing-code` recommend independent passes only when the diff size or risk benefits. Keep GitHub-specific comment mechanics outside the portable skill.

- [ ] **Step 4: Verify all skill tests**

Run: `node --test tests/skills/*.test.js`

Expected: every skill structure and contract test passes.

**Review boundary:** Review and completion behavior is rigorous, portable, and proportionate.

---

### Task 6: Strict-mode skill and zellij harmonization

**Depends on:** Tasks 3-5

**Files:**

- Create: `skills/strict-mode/SKILL.md`
- Modify: `config/mode-policy.json`
- Create: `tests/skills/profile-behavior.test.js`
- Create: `tests/fixtures/scenarios/trivial-edit.md`
- Create: `tests/fixtures/scenarios/integration-change.md`
- Create: `tests/fixtures/scenarios/peer-ready-plan.md`

**Interfaces:**

- `strict-mode/SKILL.md` is the authoritative expanded reference for injected strict context.
- Injected context and skill body share the same obligations: identify applicable skills, sequence dependent work, preserve checkpoints, and verify before claims.
- The peer-ready plan fixture is valid both inline and when handed to `zellij-agent-herder`.

- [ ] **Step 1: Write failing profile behavior tests**

Use deterministic text contracts plus scenario fixtures to assert:

1. Selective mode does not demand a design for the trivial edit.
2. Strict mode adds explicit sequencing but no external side effects.
3. Integration-heavy work routes through clarification and planning.
4. A peer-ready plan names scope, dependencies, expected output, and verification.
5. Neither profile requires zellij or forbids its use.
6. Peer output is treated as evidence to verify, not proof of completion.

- [ ] **Step 2: Confirm the tests fail**

Run: `node --test tests/skills/profile-behavior.test.js`

Expected: failure because strict-mode and scenarios do not exist.

- [ ] **Step 3: Write strict-mode and harmonization text**

Keep orchestration decisions outside strictness. Reference `zellij-agent-herder` only conditionally: use it when available, requested, and tasks are independent; otherwise execute sequentially. Do not modify the existing zellij skill unless tests expose contradictory wording.

- [ ] **Step 4: Verify profiles and existing zellij integrity**

Run:

```bash
node --test tests/hooks/*.test.js tests/skills/*.test.js
git diff --exit-code -- skills/zellij-agent-herder
```

Expected: tests pass; the zellij directory has no implementation changes from this task.

**Review boundary:** Strict mode and zellij work in tandem without dependency in either direction.

---

### Task 7: Provenance and upstream conceptual-merge tooling

**Depends on:** Tasks 3-6

**Files:**

- Create: `skills/curating-skills/SKILL.md`
- Create: `skills/curating-skills/scripts/review-upstreams.py`
- Create: `config/sources.yaml`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `tests/curation/test_review_upstreams.py`
- Create: `tests/fixtures/curation/`

**Interfaces:**

- `review-upstreams.py --manifest PATH --output PATH [--cache-dir PATH]` writes a deterministic Markdown review bundle.
- `sources.yaml` is valid YAML represented as JSON so Python's standard `json` module can parse it.
- Each source entry contains `name`, `url`, `branch`, `reviewedCommit`, `license`, and `mappings`.
- Each mapping contains `localSkill` and `upstreamPaths`.
- The script never changes `reviewedCommit`; curation updates it only after an accepted or explicitly rejected review decision.

- [ ] **Step 1: Create hermetic failing curation tests**

Build miniature local bare git remotes in temporary directories. Cover added, changed, renamed, and removed upstream skill files; missing commits; fetch failure; malformed manifest; deterministic ordering; and mapping from upstream paths to local skills.

- [ ] **Step 2: Confirm the tests fail**

Run: `python3 -m unittest tests.curation.test_review_upstreams -v`

Expected: import/file failure because the review script does not exist.

- [ ] **Step 3: Implement the review script**

Use `argparse`, `json`, `pathlib`, `subprocess`, and temporary directories only. Resolve the recorded commit and remote head, use `git log` and `git diff --name-status --find-renames`, and emit stable headings for commits, inventory changes, mapped diffs, and affected local skills. Return nonzero on fetch/manifest failure and leave the manifest untouched.

- [ ] **Step 4: Add real upstream provenance**

Record the reviewed commits used during design:

- Matt Pocock skills: `9603c1cc8118d08bc1b3bf34cf714f62178dea3b`
- Spec Kitty: `0a79355f821af9038d8b150b03c930f15970ef4c`
- Superpowers: `d884ae04edebef577e82ff7c4e143debd0bbec99`

Map only relevant upstream skill paths. Add the original `mk-*` skill paths as documented local provenance, not fetchable upstream sources. Preserve MIT notices for all three repositories.

- [ ] **Step 5: Write the curation skill**

Require a three-way conceptual comparison: current local behavior, behavior at the recorded upstream commit, and current upstream behavior. Record accept/reject decisions, validate affected local skills, and advance pins only after the review decision. Never auto-copy or auto-push.

- [ ] **Step 6: Verify curation and structure**

Run:

```bash
python3 -m unittest tests.curation.test_review_upstreams -v
node --test tests/skills/structure.test.js
```

Expected: all tests pass and fixture manifests remain byte-for-byte unchanged after failure cases.

**Review boundary:** Upstream evolution is discoverable and auditable without making installed skills network-dependent or fork-like.

---

### Task 8: Claude adapter, unified validation, and documentation

**Depends on:** Tasks 2 and 6-7

**Files:**

- Create: `adapters/claude/hooks.json`
- Modify: `hooks/run-hook.js`
- Create: `tests/hooks/claude-adapter.test.js`
- Create: `tests/fixtures/hooks/claude-session-start.json`
- Create: `scripts/validate.js`
- Modify: `README.md`

**Interfaces:**

- Claude adapter invokes the same `hooks/run-hook.js` and `config/mode-policy.json`.
- Claude output uses `hookSpecificOutput.hookEventName = "SessionStart"` and `additionalContext` exactly once.
- `node scripts/validate.js` runs structural, hook, skill, and curation tests and returns the first nonzero status.

- [ ] **Step 1: Write failing Claude parity tests**

For the same model/override fixtures, assert Codex and Claude select identical modes and context text while emitting their required outer JSON shapes. Assert Claude receives context once, not through duplicate top-level and nested fields.

- [ ] **Step 2: Confirm parity tests fail**

Run: `node --test tests/hooks/claude-adapter.test.js`

Expected: failure because the Claude adapter is absent.

- [ ] **Step 3: Implement the Claude adapter**

Detect Claude through `CLAUDE_PLUGIN_ROOT` when Codex's `PLUGIN_ROOT` is absent. Reuse the shared runner and policy; do not fork selector logic or strict text. Configure startup, resume, clear, and compact where supported by Claude's hook schema.

- [ ] **Step 4: Add unified validation**

Have `scripts/validate.js` spawn, in order:

```text
node --test tests/hooks/*.test.js tests/skills/*.test.js
python3 -m unittest tests.curation.test_review_upstreams -v
python3 <plugin-validator> .
git diff --check
```

Accept `PLUGIN_VALIDATOR` as an optional environment override. If the system validator is unavailable, report the skipped plugin-schema check clearly while continuing repository-owned checks.

- [ ] **Step 5: Update README**

Document:

- the curated skill inventory and selective invocation philosophy;
- Codex plugin installation and hook trust review;
- `MK_SKILLS_MODE=strict|selective|off`;
- the low-reasoning Codex profile pairing until effort becomes a stable hook field;
- Claude adapter installation as a supported required deliverable;
- offline behavior and deliberate upstream curation;
- optional, bidirectional independence from `zellij-agent-herder`;
- the unified validation command.

- [ ] **Step 6: Run final verification**

Run:

```bash
node scripts/validate.js
git status --short
```

Expected: all repository-owned suites pass, plugin validation passes when the configured validator exists, `git diff --check` is silent, and status contains only intentional implementation changes.

**Review boundary:** Both harnesses share behavior, installation is documented, and the entire repository has one repeatable verification entrypoint.

## Execution Topology

The dependency frontier is:

```text
Task 1
├── Task 2 ───────────────┐
└── Task 3 → Task 4 → Task 5 → Task 6
                                  ├── Task 7
                                  └─────────── Task 8 (also needs Task 2 and Task 7)
```

Tasks on the same frontier may run through `zellij-agent-herder` when the user chooses peer execution and file ownership is kept disjoint. A safe initial split after Task 1 is:

- one worker on Task 2 (`.codex-plugin/`, `hooks/`, hook tests);
- one worker on Task 3 (`skills/clarifying-work`, `specifying-work`, `planning-work`, skill tests).

Tasks 4-6 should remain sequential because they share skill contract tests and profile language. Task 7 can begin after Task 6 while a separate reviewer checks Tasks 2-6, but Task 8 integrates all prior interfaces and should run last.

Regardless of topology, the primary agent inspects diffs and reruns each review boundary before accepting peer results.

## Plan Self-Review

- **Spec coverage:** All curated skills, Codex hook selection, strict/selective profiles, low-effort override, Claude fast-follow, provenance review, offline use, safety boundaries, and zellij harmonization map to Tasks 1-8.
- **Scope:** PR state machines, tracker mutation, worktree policy, and automatic upstream merging remain excluded.
- **Interface consistency:** `MK_SKILLS_MODE`, `loadPolicy`, `selectMode`, `renderContext`, `run-hook.js`, `mode-policy.json`, and the curation CLI retain the same names across tasks.
- **Execution independence:** Every task has a dependency, exact files, focused verification, and a reviewer boundary suitable for inline or peer execution.
