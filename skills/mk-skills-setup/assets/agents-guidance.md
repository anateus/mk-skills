<important if="you are about to state or rely on how a project works">
Verify claims against imports, entrypoints, symbols, paths, and runtime wiring. Manifests, docs, prior conclusions, and peer reports are leads. Re-derive a peer finding's key premise before relaying it. Distinguish current, legacy, and target behavior; attribute what cannot be verified directly.
</important>

<important if="you are about to report a sampled or derived number">
Establish the observed window, population, coverage, and representativeness before extrapolating. Prefer an available direct measurement. If independent measurements disagree by more than about 2x, reconcile them before quoting either. Scope conclusions to the measured cohort; a caveat cannot rescue an unsupported verdict. Use `investigating-incidents` for cross-system cohorts, clocks, actors, and denominators.
</important>

<important if="you are about to claim work is verified, passing, complete, or a search found nothing">
Inspect direct evidence for the claim. Reuse your evidence only while relevant code, inputs, configuration, and environment remain unchanged and current instructions permit it. Read full results, errors, warnings, and scope; peer reports are not proof. Validate a custom negative search with a disposable known positive through the same boundary, without changing the real corpus. Run an available end-to-end check. Use `verifying-work` for the full gate, including during `reviewing-code`.
</important>

<important if="you are writing or editing a prose deliverable">
Apply `humanizer` and, when installed, `eng-simplify-prose` before delivery. Combine short edits into one pass. Match the writer's voice, preserve every claim, and simplify complexity that carries no information. Facts, numbers, paths, identifiers, references, quoted errors, code, confidence-bearing hedges, normative language, and contract wording stay unchanged. Revert a rewrite that loses meaning. Re-read the written artifact and check for U+2014 and U+2013 last; use neither in final prose. Conversational replies need no skill invocation.
</important>

<important if="you are about to delegate work">
Use built-in subagents for ordinary dispatch-and-wait work when they are adequate. Use peer panes for independent work streams, long-lived peers, or cross-harness coordination. In Codex, prefer peer panes while its subagent inspection remains limited. Give each worker bounded scope, dependencies, outputs, and verification; inspect the resulting work before accepting it.
</important>

<important if="you are dispatching an agent to search or extract from files, logs, transcripts, datasets, or trackers">
Include read discipline in the dispatch: locate first, project needed fields, then read narrow windows. Never read whole large files or transcripts. Prefer list/summary APIs over repeated heavy fetches; pass already-fetched content needed for an edit. Save large output to a scratch artifact and return concise findings with references. Use `data-spelunking` for tool choice and bounded extraction.
</important>

<important if="you are starting, claiming, dispatching, or handing off agent work">
When `agentplan` is installed, record every unit on its shared board, including one-ticket projects. Create the project when work starts. Trackers remain the issue source of truth; the board holds local assignment and slices. Name tracker projects after the issue key and link with `agentplan attach <project> <label> <url>`. Claim with `agentplan claim <project> --agent <harness-and-pane> --timeout <seconds>` so ownership is visible and stale claims expire. Read the board during work; update tracker status once when the project closes. Consult `agentplan` for commands when available.
</important>
