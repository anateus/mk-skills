---
name: building-verification-harnesses
description: Build or maintain a reusable project-local harness that drives real user journeys and preserves evidence. Use when a repository needs repeatable UI, CLI, or service verification, or its existing harness and journey map have drifted. For a single completion claim, use verifying-work instead.
---

# Building Verification Harnesses

Build a reusable capability, not a one-off proof. Opt in and follow the repository's conventions, not a prescribed agent host or directory. Use [the journey-map contract](references/journey-map.md) for feature coverage and `verifying-work` for the final evidence gate.

## Construct

1. **Inspect.** Identify real user surfaces, entrypoints, existing runners, build and launch commands, auth, fixtures, data stores, and external effects. Reuse existing browser, PTY, CLI, or HTTP tools before adding helpers or dependencies. If the checkout cannot launch, diagnose that first; do not invent working instructions.
2. **Isolate.** Allocate per-run ports, data directories, profiles, and fixture identities where possible. Identify owned resources and refuse to drive unowned or shared instances without coordination. Prefer local disposable prerequisites, not mandatory cloud accounts.
3. **Document execution.** Give exact build, launch, migrations, seed, auth, and usable-readiness steps. Provide a read-only doctor checking instance identity, build, ownership, and auth before driving. Short-lived CLIs need a prepared binary and isolated drives, not a server. Use stable selectors or commands, reset steps, and explicit invocations of any executable helper.
4. **Specify proof.** Capture action plus result, and independently observe side effects. Drive real user paths, not internal setters or test-only endpoints. Verify what a dry-run actually skips. Store evidence outside disposable state; retain it after failures and teardown. Stop only started processes and remove only owned resources, never by process name or broad directory deletion.
5. **Map journeys.** Index features and entry points with prerequisites, exact drives, expected observations, and gotchas. Separate mapped from exercised paths. For an inaccessible route, record attempted action and unmet prerequisite; never replace it with a convenient passing path.
6. **Prove the instructions.** Execute the written launch, doctor, one mapped journey, side-effect observation, teardown, and post-teardown evidence inspection on the real local target. Clean owned residue after failed attempts. Correct and rerun affected steps. Until successful, label the harness a draft with its blocker; a stand-in proves only its environment.

## Maintain

Find the existing harness and map; resolve ambiguity before editing. Reconcile index and feature files. Inspect source entrypoints and recent changes for each feature and likely omissions, then drive every mapped feature at least once. Doctor before first drive and after surprises, including fresh sessions when applicable. Reset wedged state rather than trusting a healthy process. Preserve evidence and clean owned residue after failed drives. Report source-reviewed, exercised, inaccessible, and mapped-but-unexercised paths separately.

Classify differences: inaccurate descriptions are **documentation drift**; working behavior the runner cannot drive is a **harness gap**; broken user behavior is a **product regression** to report, not conceal. Edit only harness-owned files, never product code to force a pass. Redrive corrected procedures. Report clean, changed, or blocked with coverage and evidence location. Do not automatically create a branch or PR.
