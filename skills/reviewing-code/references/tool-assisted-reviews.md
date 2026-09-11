# Tool-assisted reviews

Use the fixed comparison and Git inventory from the main skill to check any tool's inputs and outputs. Keep tool versions and relevant selection or rule settings with saved results when reuse depends on them.

## Review engines

For OCR or another review engine, reconcile selected files with Git before reviewing. Inspect omitted tests, documentation, deletions, and text classified as binary. Read deleted content from the base; use a supplemental text diff for readable source containing NUL bytes. Generated content may receive a limited check with a recorded reason.

Keep task failures, budget stops, and truncated output separate from completed review work. A successful process exit or a group marked complete does not establish complete inspection. Preserve the full output and verify actionable findings through surrounding code and executed behavior. Use additional passes when risk or an unresolved question warrants them.

## Live review UIs

Use the installed UI guidance for commands; for Hunk, discover it with `hunk skill path`. Reuse the review session associated with the work and guide it from the finding to the fix and its evidence. Notes and navigation support shared understanding; viewing a hunk alone does not establish that it was reviewed.

Save review decisions against the actual content identity and Git comparison. Reopen affected decisions after changes. Export useful notes and decisions before relying on them for a later session; some extensions keep their state only in memory. Check whether an export includes the decisions you need.

## GitHub PRs

When PR discussions are part of the work, prefer [phl28/hunk-gh-review](https://github.com/phl28/hunk-gh-review) if installed. It supports thread navigation (`T`), replies (`R`), and review submission (`S`). Use its `hpr` launcher from the intended repository, or supply explicit `GH_PR_REPO=owner/repo` and `GH_PR_NUMBER` when opening a downloaded patch. Inspect the resolved repository and PR; `hpr` derives the repository from the checkout's tracking remote or `origin`.

Read existing discussions before raising overlapping findings, and refresh them before responding. Follow `handling-review-feedback` when evaluating or applying feedback. Fetch full threads, outdated comments, and the PR conversation through `gh` or GitHub when needed: the extension's v0.1.0 pane shows clipped inline comments and omits outdated positions. Keep unresolved concerns visible after code changes; UI visibility and thread resolution do not prove a fix.

Keep the repository, PR number, base revision, merge base, and head revision with a downloaded patch. PR diffs and CI's synthetic merge commits can cover different inputs; identify which one each finding or check concerns. Refresh deliberately and compare revisions before reusing previous coverage.

A PR loader and a submission extension may resolve the PR independently. Before publishing within the user's authorization, verify that the target, reviewed commit, note locations, and selected live notes still match. Cached notes and the current checkout's branch are insufficient evidence for a separately loaded patch. Confirm the result and preserve notes whose publication did not succeed.

For `hunk-gh-review` v0.1.0, submission reads live user notes and can fall back to a cache that misses deletions. It omits agent notes from the live submission but clears both note types afterward, and it does not pin the reviewed commit in its request. Export useful notes first, inspect the exact outgoing set, and use an explicit `gh` submission with the reviewed `commit_id` when these limitations prevent a reliable submission. Recheck these details after extension updates. Posting replies or reviews requires authorization; a request to review or draft alone does not provide it.
