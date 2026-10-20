# Upstream curation, October 20, 2026

This review adds Cursor Team Kit, repairs Spec Kitty's cross-repository mappings, and adapts selected ideas into existing skills. It does not import another workflow suite or authorize upstream writes, pushes, pull requests, or live-system access.

## Revisions and scope

The starting local revision was `ca82eedbb69c3f5947dbdb45ec640c1e6321568b`. The original five-source bundle is retained locally at `/Users/mike/.jcode/scratch/upstream-review-2026-10-20.md`. A supplemental bundle uses the actual report API at frozen old and target revisions, without refetching, at `/Users/mike/.jcode/scratch/upstream-review-2026-10-20-supplement.md`. Reviews used exact Git objects, not files from the no-checkout caches' working trees. Heads below are fixed review targets, not a claim that upstream branches will remain there.

| Source | Prior reviewed revision | Reviewed target |
|---|---|---|
| matt-pocock-skills | `3cca18b368ae95cdbdebbff572ccafa662551015` | `5beb35b040e3de97e54fa9e386d7e42d15c295c2` |
| spec-kitty | `ab4636831945d20ac06d7e9b61d832ffd9a0359b` | `137dec7df8d083be5e233a59f6ee92a925c9ef34` |
| superpowers | `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` | `b739a8af570e10a95898f2bdf6cec97467fa6c12` |
| humanizer | `9862685f575c65a8247f90369951df1b3416e3d6` | `8c307f367c91bd974002f10f2be2965d642c13df` |
| antithesis-skills | `75bba77a1412e4eec65519a6d681b46bd532b3c7` | `527c182d17aac476fdf9c9ca5e290e03caa4b62a` |
| spec-kitty-open-packs | Initial snapshot | `500e3a77a6c427e35bb460757210d9525ac3d7b5` |
| cursor-plugins | Initial snapshot | `111cf6a16b11cc822782c1585859af4a580a2490` |

New sources use equal `fromCommit` and `toCommit` values, explicitly labeled as initial snapshot reviews. The empty delta after setting a first pin is not evidence of baseline review. Earlier decision records remain historical records.

## Decisions by source

| Source and reviewed paths | Adaptation | Kept or rejected |
|---|---|---|
| Matt Pocock: all configured engineering and productivity mappings, plugin exports, and changed skill inventory | Standards-file discovery, proof that a forced mutation landed, consequential test-seam blind spots, and checking whether a deterministic rule already exists but is unwired | Keep local temporary handoffs and proportional phases. Reject mandatory agent pairs, host-specific Skill calls, tracker operations in the planning layer, yes-biased questions, automatic research pushes, compulsory retros, and unrelated workflow imports. `to-spec` is unchanged. |
| Superpowers: all ten mapped paths and changed skill inventory, including new session-diagnosis assets | A proportional omitted-input and boundary-failure check in consequential plans | Keep direct verification and scoped re-review. Reject blanket approval, a fixed questioning cadence, mandatory whole suites for each task, fixed retry limits, a separate SDD ledger, and the product-specific session-export workflow. Preserve the local helper's intentional valid empty-comparison contract. |
| Humanizer: root `SKILL.md`, actual package loaders, and all eleven changed inventory paths | Refresh the verbatim 3.1.0 catalog, correct grammar and cross-references, add decision-first ordering without claim deletion, and stop flagging `fostering` as a standalone stock word | Local preservation rules override catalog examples. Reject dropping factual details merely because the reader knows the background, invented reactions, upstream packaging, and marketing claims as validation. |
| Antithesis: research mapping and changed skill inventory | Conditional generated-workload coverage analysis and property-oracle falsification that distinguishes reach, mutation quality, and oracle quality | Research mapping changes themselves need no behavioral edit. Keep feature-scoped analysis. Reject mandatory randomization, paid campaigns, product SDK/CLI procedures, and another workload entrypoint. |
| Spec Kitty core: live installed phase skills, mission loaders, and pack pin metadata | Repair dead mappings while retaining the original repository's provenance | Keep local phase separation and evidence rules. Reject runtime states, mandatory artifacts, command families, and a new diagram trigger without demonstrated need. |
| Spec Kitty Open Packs: software-dev mission steps, templates, action indexes, expected artifacts, and non-vacuity tactic | New-behavior acceptance criteria should fail for a no-op; label preservation criteria separately | Existing public-seam, valid/invalid consumer, and positive-control checks remain. Do not impose framework IDs, matrices, worktree topology, or file-existence gates on every task. Other candidate refinements were not implemented in this pass. |
| Cursor Team Kit: all eighteen scoped skills and the review-canvas renderer | Comparative claims need matched baseline and changed-state evidence, a threshold, and an inconclusive result for confounds | Keep risk-based diagnosis, review, and feedback handling. Reject automatic push/PR/CI loops, filtered canvas output as complete coverage, arbitrary file-size blockers, and a private-chat ingestion default. No Cursor runtime or new local skill is imported. |

The machine-readable decisions are in `config/curation-decisions.json`. The current mappings and exact pins are in `config/sources.yaml`. Tests check decision coverage for every mapped local skill at each current pin, including sources with no prior decisions. Negative fixtures prove missing-source, missing-mapping, and stale-pin decisions fail. This is not a semantic proof that a record fully discusses every upstream file.

## Spec Kitty migration

All fourteen old mapped paths disappear in core. The override mirror was removed at `19af971b1`; tracked built-in content moved out at `3f6ef61fc`. The report also warns that exhaustive rename detection was skipped. Deletion diffs alone would have missed the live content.

The loader was traced from `src/specify_cli/template/manager.py` through `MissionTemplateRepository.default_missions_root()` in `src/charter/offering/missions/repository.py`, `built_in_missions_root()` in `src/charter/offering/pack_paths.py`, and `get_built_in_pack_root()` in `src/kernel/paths.py`. `packs/built-in.source.yaml` pins the external runtime dependency to `af1c370f34601f2aa00d45a7a9597ab8d6a46ea1`. Command templates and guidelines resolve through mission-step fallbacks; content templates and expected artifacts resolve through the same mission repository. Configured overrides can change a consumer project's effective content.

The external reviewed `main` target `500e3a77a6c427e35bb460757210d9525ac3d7b5` has the same `packs/built-in` Git tree as runtime pin `af1c370f34601f2aa00d45a7a9597ab8d6a46ea1`. Runtime dependency provenance and external branch review are separate facts. The original core source URL is retained rather than retroactively assigning core history to another repository.

For the table below, old paths are relative to `.kittify/overrides/missions/software-dev/`, and new paths are relative to `packs/built-in/missions/` in Open Packs. The final row is already a complete relative path in both repositories.

| Old mapped path | Live successor |
|---|---|
| `actions/specify` | `mission-steps/software-dev/specify` and `software-dev/actions/specify/index.yaml` |
| `command-templates/specify.md` | `mission-steps/software-dev/specify/prompt.md` |
| `templates/spec-template.md` | `software-dev/templates/spec-template.md` |
| `actions/plan` | `mission-steps/software-dev/plan` and `software-dev/actions/plan/index.yaml` |
| `command-templates/plan.md` | `mission-steps/software-dev/plan/prompt.md` |
| `command-templates/tasks.md` | `mission-steps/software-dev/tasks` and staged `tasks-outline`, `tasks-packages`, `tasks-finalize` steps |
| `templates/plan-template.md` | `software-dev/templates/plan-template.md` |
| `templates/tasks-template.md` | `software-dev/templates/tasks-template.md`, plus individual `task-prompt-template.md` |
| `actions/implement` | `mission-steps/software-dev/implement` and `software-dev/actions/implement/index.yaml` |
| `command-templates/implement.md` | `mission-steps/software-dev/implement/prompt.md` |
| `actions/review` | `mission-steps/software-dev/review` and `software-dev/actions/review/index.yaml` |
| `command-templates/review.md` | `mission-steps/software-dev/review/prompt.md` |
| `command-templates/accept.md` | `mission-steps/software-dev/accept` |
| `packs/built-in/missions/software-dev/expected-artifacts.yaml` | Same path in Open Packs |

A separate canonical-prompt review covered twenty-three scoped files: fifteen differ from the earlier core pin, fourteen of those match the pre-move core tree, and the remaining review-prompt edit makes an ADR example path era-neutral. The broader curator checked all forty-five software-dev assets and the testing tactics. Later external changes affect internal-pack and release tooling, not the built-in tree. Those tools are not adopted.

## Cursor initial snapshot

The clone URL is `https://github.com/cursor/plugins`; the requested scope is `cursor-team-kit/skills`. Its plugin declares `./skills/`. The applicable notice is `cursor-team-kit/LICENSE`, MIT, copyright 2026 Cursor, not an inferred repository-root license.

All eighteen skill entries were inspected. Sixteen are mapped across seven existing local skills: `check-compiler-errors`, `control-cli`, `control-ui`, `deslop`, `fix-ci`, `fix-merge-conflicts`, `get-pr-comments`, `loop-on-ci`, `make-pr-easy-to-review`, `new-branch-and-pr`, `pr-review-canvas`, `review-and-ship`, `run-smoke-tests`, `thermo-nuclear-code-quality-review`, `verify-this`, and `workflow-from-chats`. `weekly-review` and `what-did-i-get-done` are explicitly outside the local work-summary triggers and remain unmapped.

The review canvas's renderer removes import changes and recasts matched whitespace edits as context. It may help navigation, but its presentation cannot replace Git's complete changed-file inventory. History rewriting, branch creation, pushing, and private transcript access remain separately authorized work. PR-wide provider checks and authorized history-rewrite tree comparisons remain unimplemented candidate refinements, not accepted new behavior.

## Behavioral checks

Fresh agents received realistic synthetic tasks, current candidate instructions, and no expected answer or grading rubric. The coordinator inspected their full responses against a separately recorded rubric. These are one-shot synthetic probes, not baseline-versus-candidate efficacy measurements or proof of reliable behavior across models. No application, workload, CI, or production behavior was exercised by these probes.

| Probe | Observed result |
|---|---|
| Comparative evidence and static-property control | Rejected the claimed 40% speedup because rows and warmup differed. Requested matched runs. Accepted the supplied pinned inventory as evidence of file presence without inventing a before/after requirement. |
| Forced mutation and consequential seams | Rejected an empty mutation diff and import failure as valid red evidence. Chose an integration seam for persistence while explaining the pure-policy test's blind spots. |
| Specification and planning | Replaced an already-satisfied summary criterion with malformed-JSON failure and line-number checks. Covered first/middle/last malformed lines, valid ordering/schema, and empty files without inventing CSV, repair, or atomic rollback requirements. |
| Standards discovery and lesson selection | Followed `CONTRIBUTING.md` to a non-obvious serialization policy, found the missing `schemaVersion`, and proposed wiring existing `JOB001` rather than inventing another check. Kept supplied CI metadata separate from executed proof. |
| Generated workload and oracle | Initial output identified unreachable deletion and an inconclusive mutant, but the candidate changed during that exercise. The fresh frozen-candidate repeat used matching before/after instruction hashes and again rejected broad coverage and oracle-validation claims while retaining intentional deterministic tests. |
| Humanizer | Initial output retained the count, error, query, and caveat but dropped an explicit workaround claim as shared context. That output was rejected. Guidance now requires moving background without dropping its claims and retains the original every-claim preservation contract. The fresh frozen-candidate repeat retained the workaround, separate-fix decision, 17 records, exact error and query, synthetic-staging restriction, restart finding, and unchecked-production caveat. It also preserved all unknown-reader command behavior. |

Exact prompts, responses, and instruction hashes are retained in `/Users/mike/.jcode/scratch/curation-probe-*.md`. They contain synthetic data only. Intermediate failures are not counted as passing checks. Final frozen reference hashes are `36383b36457695f2ea6f4865092e5721b48d6dc33eb3398cf3b8b441f3c10656` for property evaluation and `1cdc710bd5c95e792797fd54b06ef0080a9db2b91ac13e9f693d0ca0197f5917` for Humanizer.

## Validation and independent review

The baseline `node scripts/validate.js` completed with exit 0. After candidate adaptations, structure/link checks passed 2/2, Humanizer tests passed 12/12, and an offline exact-object audit found all seventy-six source-relative mapped paths live across seven sources. Its missing-path control was detected. Exact Humanizer upstream-body comparison passed for 31,916 bytes; attribution wrapper and upstream frontmatter are intentionally different.

During concurrent integration, curation tests temporarily failed because tests expected the two new source entries before they were installed. A reviewing-code entrypoint also exceeded the 500-word budget and was shortened; a later structure run passed. Neither intermediate failure is presented as a final green run.

Prospective metadata passed all ten curation tests before repository pins advanced. The accepted records were written before their corresponding pins. Integrated `node scripts/validate.js` completed with exit 0, including 64 hook/skill tests, 43 contract-inventory tests, 10 curation tests, 12 Humanizer tests, 10 evaluation-runner tests, the remaining helper suites, and Claude package/manifest validation. The full output was inspected. Astra's final actual-diff review is pending. The optional Codex plugin-schema validator was absent in the baseline run. The native Zellij peer-submission PTY test was opt-in and skipped. Static, synthetic, and skipped checks must remain distinct from executed end-user workflows.
