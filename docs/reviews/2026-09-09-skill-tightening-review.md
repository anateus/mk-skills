This records the review before implementation. See [the implementation results](2026-09-09-skill-tightening-results.md) for changes, measurements, and evaluation limits.

The skills can be tightened, but most of the useful cuts are in mandatory loading, repeated policy, and prescribed process. The individual entry files are already compact. I'd preserve their distinct triggers and concrete evidence requirements, then give the agent more freedom over how it gets there.

Reviewed on September 9, 2026 against local commit `954fb58fa40e345402a72784bd422f461e2efb3e`. This is a recommendation artifact. Skills, hooks, host configuration, `config/curation-decisions.json`, and upstream pins remain unchanged.

I read all 20 skill entry files, selected supporting references, the mode-selection runtime, contract tests, activation fixtures, and the configured upstream deltas. This is an instruction and curation review, not a correctness audit of every bundled helper. Measurements below count whitespace-separated words in the checked-in files, not model tokens or observed session consumption.

| Surface | Measured size | What it tells us |
|---|---:|---|
| All 20 `SKILL.md` files, including frontmatter | 6,890 words | Individual entries range from 23 to 63 lines. A wholesale rewrite has limited obvious upside. |
| Descriptions within those files | 954 words | These are discovery overhead even when a skill doesn't activate. Shorten repeated trigger synonyms carefully. |
| Humanizer's mandatory catalog | 4,694 words | The largest clear opportunity to reduce loading for ordinary prose tasks. |
| Shipped always-on guidance block | 1,128 words | Several operational explanations can move behind conditional references. |
| Strict profile injection | 238 words | Much of this repeats the `strict-mode` skill it also instructs the agent to read. |

These surfaces overlap: descriptions are included in the entry-file total. They are not all loaded for every task. No claim about unchanged quality or token savings has been behaviorally validated yet.

The changes I'd make first:

1. Make Humanizer's catalog conditional. Its [entry point](../../skills/humanizer/SKILL.md) requires the complete reference before editing, and the [always-on prose guidance](../../skills/mk-skills-setup/assets/agents-guidance.md) routes ordinary deliverables through it. Keep the factual preservation rule, voice matching, and a short structural checklist in the entry file. Consult catalog sections when a passage needs examples or an explicit audit calls for them. This removes a 4,694-word required read from the proposed short-edit path. It doesn't establish that quality stays constant; the evaluation should check that.

2. Replace wording locks with behavioral evidence. At the reviewed revision, [activation tests](https://github.com/anateus/mk-skills/blob/954fb58fa40e345402a72784bd422f461e2efb3e/tests/skills/activation-contracts.test.js) assert exact descriptions, and [planning tests](https://github.com/anateus/mk-skills/blob/954fb58fa40e345402a72784bd422f461e2efb3e/tests/skills/planning-contracts.test.js) require the phrase `one material question at a time`. Those tests detect an equivalent rewrite as a regression. Keep schema, link, packaging, and executable-helper checks. Replace prose snapshots and selected phrase assertions with agent behavior checks. The [26 existing fixtures](../../tests/fixtures/activation-cases.json) and [forward-test guide](../validation/skill-activation-forward-tests.md) already provide a starting point.

3. Allow small batches of independent questions. Both [clarification](../../skills/clarifying-work/SKILL.md) and [interactive refinement](../../skills/adversarial-refinement/SKILL.md) prescribe one question at a time. Preserve sequencing when one answer changes the next question. Otherwise batch related decisions so the user can resolve them together. A sufficient replacement is: "Ask only about material choices you cannot resolve from evidence. Group independent questions; wait for prerequisites before asking dependent ones." Keep the interactive grill's pacing when the user wants it.

4. Remove duplicate policy from the strict hook. [The injected text](../../config/mode-policy.json) repeats the [skill's obligations](../../skills/strict-mode/SKILL.md). Start by injecting the selected profile and its read instruction, leaving execution detail in the skill. Verify that the host actually loads the skill before removing the fallback detail. Likewise, keep the always-on block's triggers and essential boundaries, but move explanations of claim leases, tracker ownership, peer selection, and prose editing to their relevant references. Installed skills must remain usable independently; a new compulsory shared-policy file would undermine that property.

5. Separate a feedback concern from its proposed remedy. [Handling review feedback](../../skills/handling-review-feedback/SKILL.md) currently defines acceptance as both a supported concern and a suitable proposed direction. That misses the common case where the reviewer found a real bug but suggested the wrong fix. One sentence is enough: "Assess the concern and proposed remedy separately; a valid concern may need a different fix." Keep verification against the original concern.

6. Make output requirements conditional. Most engineering skills finish with a list of everything to report. Those lists repeat evidence already produced during execution and can make a small change sound like a project handoff. Ask for the result, material decisions, verification, and remaining limitations, expanding only where useful. In [handing-off-work](../../skills/handing-off-work/SKILL.md), restrict the regeneration requirement to generated deliverables. A decision record or review doesn't need a generator to be transferable.

7. Clarify verification freshness and negative controls. [Verifying-work](../../skills/verifying-work/SKILL.md) correctly says evidence expires when relevant inputs change. Make that rule govern reuse, so unchanged evidence needn't be regenerated by every stage. Preserve a responsible agent's direct check rather than accepting a peer's claim. For a custom search that reports absence, demonstrate detection using a disposable positive fixture that exercises the same search boundary. The current blanket instruction to plant a positive in every sweep needs that scope; it should never imply modifying the real corpus merely to prove a query works.

The guardrails I'd retain are concrete: fixed review provenance; independently derived expected values; evidence tied to the claim; explicit sample windows and denominators; bounded reads; protection of unrelated changes; and host/user control of external actions. They catch specific failures. Mandatory formatting, repeated explanations, fixed question cadence, and prescribed orchestration are better candidates for removal.

A few small capabilities would add more value than another broad workflow skill:

| Capability | Smallest useful addition | Benefit and limit |
|---|---|---|
| Behavioral evaluation and instruction removal experiments | Run existing activation fixtures in clean sessions against a pinned skill version; keep rubrics out of the agent prompt. Compare the original with one candidate deletion. | Gives evidence for removing instructions. Record outcome quality, false activations, unnecessary questions, reference loads, time, and available token usage. Repeat variable cases before generalizing. |
| Cheap feasibility probes | In clarification/planning: when uncertainty is empirical, make the smallest reversible probe and report the answer before specifying a production solution. | Lets the agent demonstrate an idea. Label temporary artifacts and preserve the task's authority boundaries; a feasibility question doesn't authorize shipping the prototype. |
| Review after a fix | Compare the previous findings with the fix diff, check nearby effects, and reopen broader review when the fix changes contracts or reveals a wider problem. | Reduces repeated whole-branch review while retaining coverage for regressions. No arbitrary number of fix rounds and no automatic acceptance of unresolved defects. |
| Plans that defer uncertain detail | Specify the next executable slice precisely; give later slices their outcomes and dependencies until discovery resolves their interfaces. Add expand/migrate/contract when a broad refactor needs compatibility stages. | Avoids guessing exact edits too early. Preserve a checkable destination and the next verification point. The wide-refactor idea already exists at Matt Pocock's recorded revision; it is not a new upstream delta. |
| Curation that detects stale mappings | Report whether mapped paths still exist at both revisions, surface Git warnings, and link each unique diff once. Flag moved or deprecated sources for manual tracing. | Makes upstream review cheaper and prevents a quiet mapping from being mistaken for unchanged behavior. Path existence alone cannot establish that a file still drives runtime behavior. |

The evaluation runner is the largest addition here, but it has the best compounding value. Start with representative cases from the existing guide. Add short prose preservation, independent versus dependent questions, valid concern with a different remedy, and a fix that changes an interface. Compare both supported hosts where available. The current static suite cannot establish that shorter instructions achieve the same results.

I applied the upstream review workflow against all four configured sources. The exact comparison ranges were:

| Source | Recorded revision | Fetched head |
|---|---|---|
| Matt Pocock skills | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` | `3cca18b368ae95cdbdebbff572ccafa662551015` |
| Spec Kitty | `0a79355f821af9038d8b150b03c930f15970ef4c` | `eee49c83990fdb55c00bf41d49e74fdb5af38c1e` |
| Superpowers | `d884ae04edebef577e82ff7c4e143debd0bbec99` | `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` |
| Humanizer | `e2e92e7b4b8229253ed5c8e81dc65463fdeddda5` | `9862685f575c65a8247f90369951df1b3416e3d6` |

The following records are proposed accept/reject decisions for those exact ranges. Accept means an idea is worth adapting, not that an adaptation has been implemented or validated. Existing decisions in `config/curation-decisions.json` were read first.

| Source and affected local skills | Recorded to current upstream behavior | Proposed decision against local behavior |
|---|---|---|
| Matt: `clarifying-work`, `adversarial-refinement` | Grilling changes from single questions to rounds of questions whose prerequisites are settled. | Accept dependency-aware batching. Reject exhaustive traversal, mandatory exploration subagents, and a new approval gate. Local stopping remains proportional to decision risk. [Source](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/grilling/SKILL.md) |
| Matt: `diagnosing-bugs` | Adds redaction guidance for commands and captured artifacts; removes automatic post-fix architecture handoff. | Accept selective, redacted evidence handling; adapt without authorizing new data access. Accept removal of automatic follow-on work with no local change needed. Local diagnosis already avoids that handoff. [Source](https://github.com/mattpocock/skills/compare/ed37663cc5fbef691ddfecd080dff42f7e7e350d...3cca18b368ae95cdbdebbff572ccafa662551015) |
| Matt: `test-driven-development`, `planning-work`, `specifying-work`, `reviewing-code`, `handing-off-work` | Primarily editorial changes and explicit host Skill-tool calls; TDD adds a `codebase-design` reference. | Accept useful wording cleanup without local changes. Reject compulsory host-specific calls or new external skill dependencies. Preserve local public seams, evidence, and portable invocation. `implementing-work` has no mapped delta. |
| Superpowers: `clarifying-work`, `adversarial-refinement` | Adds spike, bounded, and architectural paths, while retaining approval before every path's implementation and allowing only upgrades in process. | Accept cheap feasibility probes; proportional process is already local. Reject universal approval, compulsory classification announcements, and the one-way escalation rule. [Source](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/brainstorming/SKILL.md) |
| Superpowers: `planning-work` | Adds the originating spec path to the plan; removes a repeated reminder block. | Accept an explicit spec link when a spec exists. Local plans already cover constraints and evidence without requiring full implementation code in every step. [Source](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/writing-plans/SKILL.md) |
| Superpowers: `test-driven-development` | Replaces the anti-pattern reference with guidance about the concrete break a test catches, including behavior tests for agent documents. | Accept the counterexample question and behavioral evaluation. Reject blanket prohibitions on source inspection or mock assertions where structure or interactions are the actual contract. [Source](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/test-driven-development/writing-good-tests.md) |
| Superpowers: `implementing-work`, `reviewing-code` | Adds scoped re-review, resuming implementers for fixes, batching small edits, and plan-specific artifacts; also adds fixed retry rounds and controller rulings. | Accept scoped re-review and reuse of relevant context. Existing AgentPlan projects and session/agent artifact paths already supply identity. Reject fixed escalation counts, accepting unresolved defects because a cap elapsed, compulsory dispatch, and bans on direct verification. [Re-review source](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/subagent-driven-development/re-review-prompt.md) and [controller source](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/subagent-driven-development/SKILL.md). |
| Superpowers: `diagnosing-bugs`, `handling-review-feedback`, `verifying-work` | Removes repeated exhortations and unsupported performance claims; routes verification at the relevant debugging step; repairs file matching in `find-polluter.sh`. | Accept the simplification with no local change needed. Local skills already use direct evidence and concise language. Reject importing an unused polluter helper solely to track its fix. |
| Spec Kitty: `implementing-work`, `reviewing-code`, `planning-work` | Updates governance APIs, mission selectors, workflow transitions, and forced separation of code and planning ownership. | Reject framework-specific machinery. It doesn't fit local interfaces, and splitting every code/documentation change into separate work packages would add ceremony. `specifying-work` has no mapped delta. [Source](https://github.com/spec-kitty/spec-kitty/compare/0a79355f821af9038d8b150b03c930f15970ef4c...eee49c83990fdb55c00bf41d49e74fdb5af38c1e) |
| Spec Kitty: `verifying-work` | The mapped override manifest now declares itself inert; a canonical manifest exists elsewhere. | Accept repairing the mapping before closing curation. Reject adopting mandatory framework artifacts as local verification requirements. Keep this source pin pending the remapped comparison. |
| Humanizer: `humanizer` | Reorganizes 35 patterns into 25, prioritizes structural habits, marks weak signals, and strengthens protection of inline code and ranking/simultaneity claims. | Accept the structural priorities and preservation checks. Retain the stronger local rule against losing claims or inventing a personal reaction. Load examples selectively. [Source](https://github.com/blader/humanizer/blob/9862685f575c65a8247f90369951df1b3416e3d6/SKILL.md) |

One mapping needs repair before provenance can advance. `config/sources.yaml` maps verification to `.kittify/overrides/missions/software-dev/expected-artifacts.yaml`. At the fetched head, that file says it isn't consumed. I traced the built-in path through `src/charter/activation/manifest_loader.py` to `MissionTemplateRepository.default()`, `get_expected_artifacts()`, and `_expected_artifacts_path()`. Its current source is [the built-in manifest](https://github.com/spec-kitty/spec-kitty/blob/eee49c83990fdb55c00bf41d49e74fdb5af38c1e/packs/built-in/missions/software-dev/expected-artifacts.yaml). The deprecation comment's old `src/doctrine` code paths have themselves moved, which is another reason to verify source wiring.

The generated bundle is 1,823,806 bytes. Git also reports that exhaustive rename detection was skipped for Spec Kitty; the helper currently discards stderr from successful Git commands. I inspected the mapped net deltas and selected new skills, not every change across Spec Kitty's repository. Treat source-wide curation as pending rather than advancing its pin on this report alone.

Among Matt's five newly added skill entry files, [writing-for-agents](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/writing-for-agents/SKILL.md) is the best conceptual source: distinct trigger branches, conditional references, and testing whether an instruction changes behavior. Adapt those principles into the maintenance workflow; importing its full 1,777 words would work against this review's goal. Its general claims about model attention and negation remain hypotheses to evaluate locally. `retro` offers a useful checklist for environment improvements but assumes a particular agent topology. `wizard` is useful for recurring human-only setup, with more implementation and credential-handling scope than a small instruction addition. `wait-what` duplicates an ordinary request to re-explain, and `implement-spec` introduces orchestration already covered by local workflows. I would defer those imports.

Coverage and suggested disposition for each local skill:

| Skill | Disposition |
|---|---|
| `clarifying-work` | Keep evidence-first discovery; allow independent question batches and empirical probes. |
| `adversarial-refinement` | Keep interactive and artifact modes; collapse repeated pacing/authority text. |
| `specifying-work` | Keep the behavior contract; treat its fields as coverage, not compulsory headings. |
| `planning-work` | Add a spec pointer and conditional planning depth; keep dependencies and verification. |
| `implementing-work` | Keep selective routing; shorten repeated lifecycle and reporting language. |
| `test-driven-development` | Add the concrete-break question; preserve useful alternatives and independent expected values. |
| `diagnosing-bugs` | Keep the discriminator loop; add short evidence-redaction guidance. |
| `investigating-incidents` | Preserve cohort, clock, actor, denominator, and correction requirements. Keep the hypothesis count conditional on uncertainty. |
| `reviewing-code` | Keep fixed provenance; add scoped follow-up review and fix the package helper. |
| `handling-review-feedback` | Separate valid concern from chosen remedy; verify resolution of the original concern. |
| `verifying-work` | Clarify evidence reuse and disposable controls; retain direct verification. |
| `handing-off-work` | Qualify regeneration to generated outputs; keep durable references and verified state. |
| `strict-mode` | Remove duplicate hook prose; preserve explicit checkpoints for applicable work. |
| `curating-skills` | Keep three-way decisions and exact pins; improve mapping diagnostics and report size. |
| `data-spelunking` | Keep locate/project/window discipline; correct the destructive preview example. |
| `humanizer` | Make examples conditional and adapt upstream structural priorities. |
| `personal-writing-style` | Largely retain. Its draft/extract/profile/install branches are already conditional. |
| `zellij-agent-herder` | Preserve addressing, focus, identity, and fixed-base safeguards. Move peer identity internals and the four-level taxonomy out of routine dispatch guidance. |
| `subagent-artifact-discipline` | Largely retain. Executable hooks already carry the operational behavior. |
| `mk-skills-setup` | Shorten repeated safety explanations and reduce the injected asset; keep idempotent merge, preview, and backup behavior. |

Two concrete defects are worth fixing alongside the first instruction changes:

- [The review-package helper](../../skills/reviewing-code/scripts/review-package) uses `mktemp` with `review-package.XXXXXX.md`. On this macOS host, the suffix prevents substitution: the first isolated call creates that literal filename and the second fails with `File exists`. A template ending in `XXXXXX` generated distinct names on both calls. Use a portable temporary path and test repeated/concurrent invocations. Upstream's helper uses a different artifact scheme, so its current change isn't a direct portability patch for the local helper.
- [The structural-search reference](../../skills/data-spelunking/references/finding-code-and-text.md) labels a rewrite example as preview while including `-U`. Installed `ast-grep run --help` says that flag applies all rewrites without confirmation. Running the example against a disposable JavaScript fixture changed `value == null` to `value === null`. Separate preview and apply commands.

Verification performed under `verifying-work`: the standard `node scripts/validate.js` command failed in its first stage with 71 of 72 tests passing and the review-package collision above. I then ran the remaining repository suites separately: curation (8 tests), pane identity (16), Hunk placement (8), and all five remaining shell suites passed. Plugin-schema validation passed. These are static/helper results; no clean-session cross-host behavioral comparison was run. The baseline log is at `/tmp/mk-skills-validation-2026-09-09.log`; the generated curation bundle is at `/tmp/mk-skills-upstream-review-2026-09-09.md`.

I'd sequence the work as: repair the two concrete defects; establish representative behavioral evaluations; remove mandatory catalog loading and duplicate policy; then adapt question batching, scoped re-review, and short test-quality guidance. Change one behavior at a time so a regression can be attributed to the instruction that changed.
