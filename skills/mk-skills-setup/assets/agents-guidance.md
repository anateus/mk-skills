<important if="you are about to state, document, or rely on what a project uses or how it works">
Verify from the inside, not the surface. Treat manifests, dependencies, design documents, READMEs, subagent reports, and your own earlier conclusions as claims to check against actual imports, entrypoints, symbols, paths, and runtime wiring — before relaying a subagent's diagnosis or prescription, re-derive the one fact it presupposes. Distinguish current behavior from legacy and target architecture, and attribute claims that cannot be verified directly.
</important>

<important if="you are about to report a number obtained by sampling, extrapolation, or back-calculation">
Establish the sample frame before the number leaves your hands: what window and what population the instrument actually observed (a queryable table may be a short hot buffer; a grep may only see rows carrying the attribute; a chart bar may cover a partial period), and why that is representative of the claim — one extra query, before extrapolating, not after. Prefer a directly measured or published figure over a derived one, and check that one exists before deriving. If a derived figure and an independent measurement of the same quantity disagree by more than ~2×, neither is quotable — reconciling the discrepancy is the next task, never a caveat. Verdict words ("refuted", "confirmed", "the cause is") are earned only by measurements whose frame passes these checks; otherwise scope the claim to its sample and keep the hypothesis alive. A caveat that would not change the sentence after it is decoration.
</important>

<important if="you are about to claim work is verified, passing, complete, or that a sweep found nothing">
Run the check now and read its full result; confidence, stale output, and an implementer's or subagent's report are not evidence. A sweep that reports nothing counts only if it can detect a planted known positive, and a first-match read (`grep | head -1`) answers a different question than "any occurrence". When the real end-to-end command is runnable with current access, run it instead of declaring a later manual step. The `verifying-work` skill carries the full gate, and part of reviewing code is running it (`reviewing-code`).
</important>

<important if="you are writing or editing prose anyone else will read: RFCs, ADRs, design docs, PR and commit descriptions, Linear issues, Notion pages, READMEs, CONTEXT/AGENTS/CLAUDE files, review comments, handoffs">
Run the `humanizer` skill (and `eng-simplify-prose` when installed) on it by default, before delivering or publishing. Do not ask first and do not wait to be told: assume both are wanted for anything with even mildly technical content. Combine them into a single editing pass when the text is short.

`humanizer` strips AI tells. The ones that recur here: em dashes (a hard zero in final text), mechanical boldface, inline-header bullet lists (`- **Thing:** ...`), the same `X, not Y` tailing negation fired a dozen times, rule-of-three cadences, and manufactured closing lines. `eng-simplify-prose` cuts complexity that carries no information, and names a mechanism once when its full explanation recurs three or more times. Most documents need zero new coined terms, which is a normal outcome rather than a skipped step.

Neither skill may change a fact, number, file path, identifier, ticket reference, quoted error string, code block, or hedge that encodes confidence ("unmeasured", "per the design doc", "in most observed cases"). Normative language (MUST/SHOULD/MAY) and contract wording stay verbatim. If a rewrite loses a claim, revert it.

Verify by re-reading the artifact after writing or publishing it instead of trusting the edit, and scan the final text for `—` and `–` as the last check.

Conversational replies do not need the skills invoked, but the same patterns apply: write chat output as though it had already been through both.
</important>

<important if="you are dispatching a subagent to search, read, or extract from files, logs, transcripts, datasets, or trackers">
Give the subagent read discipline or it will thrash its own context and abort mid-task (a single oversized tool result refills the window faster than autocompaction can recover). Locate first, then read only narrow line-windows — never whole large files (>~500 lines) or whole session/log transcripts. Never call heavy MCP fetches (e.g. Linear `get_issue`) in a loop; prefer list/summary calls, and when the agent must edit a large record, pass its current content in the dispatch instead of having it re-fetch. Pipe large search output to a scratch file and read filtered slices rather than letting a multi-hundred-KB result land in context. Require each spelunking subagent to write findings to a file and return a short summary, not raw dumps. Use the `data-spelunking` skill for the tool decision tree (ripgrep, ast-grep, qsv, jq) and a bundled JSONL/transcript extractor.
</important>

<important if="you are starting, claiming, dispatching, or handing off a unit of agent work, or need to know which agent is working on what">
When the `agentplan` CLI is installed, it is the assignment ledger, and its SQLite board at `~/.agentplan/agentplan.db` is shared by every harness on the machine (Claude Code, Codex, peer agents in other panes). Put every unit an agent picks up on the board, including a unit that maps exactly one-to-one onto a tracker issue: a one-ticket project is not overhead, it is the only thing that can answer "which agent is on what" across harnesses. Create the project when work starts, not when it finishes.

The tracker (Linear, Jira, GitHub) stays the source of truth for the issue itself and for anything a human or another team needs to see. agentplan holds assignment and the local slices below that issue. Do not mirror issue bodies or per-slice status back to the tracker; status flows up once, when the project closes. Name the project after the tracker key and link it with `agentplan attach <project> <label> <url>`.

Claim with identity and an expiry: `agentplan claim <project> --agent <name> --timeout <seconds>`. `--agent` is what makes the board answerable, so use a name that identifies the harness and pane rather than a bare role. `--timeout` is what lets a dead agent's ticket be reaped by the next claim; without it a crashed peer wedges the project. Claims are safe to race (`BEGIN IMMEDIATE` plus an advisory lock), so peers may claim from one project concurrently without coordinating first.

Read the board rather than re-reading the tracker during a session. Tracker MCP calls are large and, where a Bash-output compressor is in use, uncompressed; CLI output is neither.
</important>
