# Working with Greptile reviews

Greptile posts two things on a PR: inline comments, each with a priority badge (`P1`, `P2`), and one summary comment with a `Confidence Score: N/5` that it edits in place as the PR changes. When it has reviewed the PR, use its work as an input and put your own effort where it is weak.

## What a measurement showed

One sample: three private repositories, comments posted over fifteen days in November 2026, 253 top-level inline Greptile findings on 452 reviewed PRs. Outcomes were classified from the human replies in each thread, not by re-checking the code, so "accepted" measures an author agreeing or reporting a fix, not a verified defect. Three people wrote about half of those replies.

| Greptile inline findings | Count |
|---|---|
| Human accepted or fixed | 166 |
| True but declined (by design, out of scope, accepted risk) | 14 |
| Wrong | 5 |
| Acknowledged, deferred | 1 |
| No human reply, lines changed afterwards | 24 |
| No human reply, lines unchanged (22 on PRs still open) | 43 |

Where a human answered, about nine in ten findings held. The five wrong ones each rested on something outside the commented file: how a library scopes temporary tables, how long a job really runs, what callers pass, code another commit had already removed. Declined findings clustered in test-coverage requests (4 of 28 answered) and maintainability notes (3 of 4).

On 43 of those PRs humans also raised 88 comments labeled P0 to P2. Of the 71 that described a defect, none was a bug checkable from the changed file alone. They were about consumers and contracts in other files (14), behavior that was wrong for the business rule or for how the system is operated (13), platform and deployment behavior (12), concurrency (10), and data and migrations (10). About half needed knowledge that is not in the repository. This does not prove Greptile catches every local bug; reviewers may skip what a bot has already covered.

The summary score did not separate anything: 432 of 450 PRs ended at 5/5, and on 5 of them humans raised 6 of those defect findings after that final 5/5.

## Using its review

1. **Check what it reviewed.** Fetch its inline threads, including outdated ones, and the summary. Each inline comment records the commit it was made against. Findings on an older commit may already be fixed, and commits after its last pass have not been reviewed by it.
2. **Take its local findings as strong leads.** Confirm each against the current head, which is usually quick, then adopt it with attribution. Do not rebuild the same line-by-line pass over files it covered at the current head. Read those files for what the change means, not to re-derive null checks and wrong conditions.
3. **Verify the premise when a finding depends on something outside the file.** Claims about library or platform behavior, callers, timing, or production state are where it was wrong. Read the caller, the documentation, or run the code before repeating the claim.
4. **Do not escalate its test and maintainability requests on its word.** Raise one only if you would have raised it yourself.
5. **Spend your own review on what it misses.** Whether the change does the right thing for the requirement and for operations, consumers and contracts outside the diff, deployment and platform behavior, concurrency, and data migrations. Absence of a Greptile comment on these is not evidence.
6. **Ignore the score and thread state as evidence.** A 5/5 summary, a resolved thread, or an outdated marker does not show that the change is safe or that a finding was fixed.

In the report, say which findings came from Greptile, which of its findings you confirmed, and which checks you left to it.

## Re-measure before relying on this

These numbers describe one team's repositories over one short window, and the tool changes. Collect a fresh window with the [PR comment collector](../../learning-from-mistakes/references/pr-reviews.md) (`--any-author --repo ...`), then compare three things: human replies to its inline threads, the human-labeled findings on the same PRs, and human findings that arrived after its final summary. Other review bots need their own measurement; do not carry these conclusions over to them.
