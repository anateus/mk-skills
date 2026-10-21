# Approved Cursor adoption, October 21, 2026

Mike approved all six proposed folds and the optional verification-harness skill at `2026-10-21T00:32:50Z`. This work resumes the earlier uncommitted nuclear-review draft. It does not authorize pushes, PR publication, live customer-system access, or importing unrelated Cursor workflows.

## Delivered scope

| Local skill | Change |
|---|---|
| `reviewing-code` | Normal reviews now include design and maintainability independently of runtime correctness. References cover structural simplification, canonical ownership, meaningful abstractions, contracts, cohesion, dependency/atomicity reasoning, and cross-boundary safety assumptions. Keep deleted consumers, feature gates, developer startup compatibility, and consequential intentional-risk findings in scope. |
| `planning-work` | For consequential ownership/type/module decisions, start with real caller usage, compare distinct shapes, preserve error/mutation/order contracts, and reconsider models that repeatedly need workarounds. |
| `specifying-work` | Conditional automation-friendly CLI contracts: non-TTY missing inputs, help/examples, input/output and exit behavior, observable previews, compatibility, and operation-specific retry safety. |
| `verifying-work` | Normal changed-CLI requests exercise the executable non-TTY contract; PR-check requests load provider-inclusive triage; requests to build reusable capability route to the new harness skill. |
| `diagnosing-bugs` | PR-CI recipe covers all attached providers and the current head, actionable evidence and refreshed status, without equating green checks with merge eligibility or authorizing pushes. |
| `implementing-work` | Explicit prepare/tidy-PR mode drafts author-side review guidance, separates generated/mechanical changes from logic, and preserves publication/history-rewrite authorization boundaries. |
| `handing-off-work` | Author-side PR handoffs route to the preparation mode without conflating it with reviewer capture or claiming correctness. |
| `analyzing-codebase` | Explicitly requested agent-readiness mode tests documented startup, scoped feedback loops and documentation reliability. No default audit, numerical score, scanner installation, or automatic setup repair. |
| `building-verification-harnesses` | New opt-in skill with construction and maintenance modes: real user journeys, launch/readiness/doctor, ownership and isolation, action/result/side-effect evidence, retained proof, and drift classification. No mandatory host path, cloud account, automatic PR, or product fixes to hide failures. |

All skill entries remain within the existing 500-word body budget. Supporting detail lives in reachable references. Implementation commit: `cbd1562cf2383a9c79f63eadb5ce0c7a35330894`. Separate CLI-specification fixture coverage was committed as `c1c4c8acf5f156a931b933656c8346094949946e`.

## Source and attribution

The starting Cursor pin was `111cf6a16b11cc822782c1585859af4a580a2490`; the exact reviewed target is `190d28736eff128ec94f502a22c7fe0c4b56cd37`. The adopted Team Kit, Thermos, Pstack, CLI and compatibility source content is unchanged across that interval. This is an approved reconsideration and expanded scope, not a claim that these ideas arrived in the four intervening commits. The changed repository inventory concerns the third-party X plugin and root listing, outside the adopted scopes.

The original 53 decision records are retained, with nine accept/reject records appended. Cursor mapping coverage expands from seven to twelve local skills and sixteen to twenty-eight unique watched source paths. Across all seven configured upstreams, the exact-object audit checks all eighty-eight source-relative paths with a missing-path control. New mapping assertions protect each adopted procedure against being dropped from future reviews. Other upstream pins are unchanged.

`THIRD_PARTY_NOTICES.md` retains Cursor's scoped MIT notice and a separate Pstack MIT notice, copyright 2026 Lauren Tan. The new individually installable harness skill includes Pstack's exact license text. No upstream implementation or vendor runtime is copied into a local driver.

## Real-host behavioral checks

The real `scripts/evaluate-skills.py` public CLI launched Codex CLI `0.163.0` with requested model `gpt-6-sol`, isolated configuration and frozen skill catalogs. Raw prompts did not contain grading rubrics; rubrics were materialized after host completion. Baseline skill content is committed `666e935`; candidate skill content is `cbd1562`. Synthetic runnable workspaces establish bounded instruction behavior, not hosted CI or general model reliability. Process exit 0 is recorded separately from manual grading.

| Case | Observed result |
|---|---|
| Design-only overbuilt implementation, baseline and candidate | Both runs found the same low-severity unnecessary pipeline burden while confirming matching public behavior. Candidate loaded the design reference. This demonstrates activation and retention, not incremental effectiveness over baseline. |
| Justified-complexity control, baseline and candidate | Both reported no findings after executing validation, dependent ordering, and deterministic generation. Neither rejected the generated file merely for exceeding 1,000 lines. |
| Ordinary CLI review | Executed closed-stdin, piped input, help, retry, preview and persisted-state checks; found prompt contamination, duplicate retry writes and changed output shape. It selected reviewing/verifying, not the original expected specifying skill. The behavior rubric succeeds, but that literal selection expectation remains unmet. |
| Separate CLI specification | A new independent task loaded `specifying-work` and wrote a concrete non-TTY/help/output/preview/identity-specific retry contract without implementation. It does not retroactively change the earlier selection result. |
| Author-side PR preparation | Loaded the authoring reference and produced only a draft with actual serializer/consumer evidence, generated-file separation, migration order, and downstream limits. No history rewrite, push or publication. |
| PR-CI snapshot | Loaded the triage recipe, distinguished a failed external provider on the old head from pending checks on the new head, and did not claim live provider or merge eligibility proof. The provider data is explicitly synthetic. |
| Requested readiness audit | Loaded the readiness reference, observed the documented missing entrypoint, ran the actual local alternative and scoped test, and reported in-place environment limits without a score. |
| Miniapp harness construction | Loaded the new skill and journey reference, executed public create/list plus persisted-state observations, removed only owned temporary data, and retained its evidence. This fixture is not the real-project acceptance below. |
| Caller-facing architecture plan | Loaded the planning entry and architecture reference, inspected actual fixture serializer/consumer behavior, compared codec/class/registry shapes, and preserved compatibility uncertainty. Only the plan was written. |

There are two matched baseline runs and nine candidate runs in this table. They are one-shot examples, not a statistical effectiveness study. Traces include recovered lookups for unavailable coordination or writing helpers; the substantive outputs and executed receipts were inspected directly. Catalog injection exercises real host execution but is not a native plugin-installation/discovery test.

## Real-project harness construction and maintenance

A separate fresh Codex task used the new skill to author a reusable harness for the actual mk-skills checkout, not a copied product or a command stub. The generated `verification/run.py`, runbook and two-journey map live under `/Users/mike/.jcode/scratch/approved-real-harness-workspace/verification/`.

Construction at `cbd1562` ran the real shipped `review-package`, `review-coverage`, and `prose-check` interfaces. The package's twenty-three changed paths matched an independent Git inventory. Coverage correctly exited 1 with twenty-three unreviewed gaps; nobody declared substantive review complete to manufacture exit 0. The real Vale-backed prose command detected four planted cues, and the input hash did not change. Owned temporary state was removed and evidence remained. The product checkout's head and status were unchanged.

Before maintenance, the generated procedure and evidence were preserved under `/Users/mike/.jcode/scratch/approved-real-harness-pre-maintenance/`. The product legitimately advanced to the test-only `c1c4c8a` commit. The stale pinned-build doctor rejected that head with exit 1 before driving. A controlled edit changed only the generated prose journey's rule name to `RetiredStockWords`; the exact diff is retained in scratch.

A second fresh Codex maintenance task inspected the intervening test-only change, deliberately updated its pin, corrected the stale rule name, and redrove both actual journeys. The expected unreviewed-coverage result, four detected prose cues, normal cleanup and unchanged product state were observed again. All fifty-nine preserved construction evidence files remained byte-identical. Two stale-head rejections and four successful construction/maintenance drives are retained; mapped-but-unexercised paths remain listed rather than inferred from an alternative route.

Maintenance also moved its post-drive status check into a failure `finally` block. That branch was inspected, not executed by the successful reruns. Cancellation, mid-drive failure cleanup, hosted providers, native UI/PTY operation, other prose modes and full feature coverage are not established by this acceptance. The generated harness is deliberately pinned to its tested revisions, not a claim that it automatically accepts every later checkout.

## Validation and independent review

Before provenance advancement, the affected fixture tests passed (six maintainability fixture tests and seven adoption fixture tests), schema/structure/reference checks passed, all ten curation tests passed against prospective metadata, and the exact-object audit found all eighty-eight watched paths live. Decisions were written before the corresponding Cursor pin advanced.

Astra independently reviewed the actual implementation and behavioral outputs, confirmed the architecture/specification routes and real construction/maintenance observations, and required the selection mismatch and baseline parity to remain explicit. No blocking functional, metadata, or evidence finding remained in its reviewed scope.

The full `node scripts/validate.js` command ran against committed code and metadata at `ac946d005ee990da32eca351cc7169b5f10c031d` and exited 0. The coordinator read the complete result: 64 hook/skill tests, 43 contract-inventory tests, 10 curation tests, 12 Humanizer tests, 23 evaluation-runner/fixture tests, the remaining Python/shell helper suites, and Claude package/manifest validation passed. Astra independently ran the same full entrypoint with exit 0. The optional Codex plugin-schema validator was absent, and native Zellij PTY submission remained opt-in and skipped; neither is called passing.

A separate real expanded upstream-review CLI run fetched all seven configured remotes and emitted eighty-eight mapping rows with no missing current paths. Before/after hashes confirmed both provenance files unchanged. It also detected a later Antithesis head, `4ce26aa6f0021bd99d401918b79c7bb906180858`, beyond the retained `527c182d17aac476fdf9c9ca5e290e03caa4b62a` pin. That later delta was not reviewed or adopted in this Cursor work; the report exposes it for a subsequent deliberate review rather than advancing the unrelated pin.

Machine-readable run identifiers, grading, snapshots and retained evidence are in `docs/reviews/2026-10-21-cursor-adoption-evidence.json`. Raw host receipts remain under `/Users/mike/.jcode/scratch/approved-*`; their synthetic and real-project scopes are separate.
