# Replaying past findings

Use this to measure a change to review guidance against defects real reviewers already found, instead of against cases written for the change. It needs a checked-out mk-skills source repository for the evaluator, authenticated `gh`, and local clones of the repositories under study.

## Collect

Collect every published comment on the repositories' PRs with the [PR comment collector](../../learning-from-mistakes/references/pr-reviews.md):

```sh
python3 ../learning-from-mistakes/scripts/collect_pr_comments.py --any-author \
  --repo OWNER/NAME --repo OWNER/OTHER \
  --start 2026-01-01T00:00:00Z --end 2026-01-15T00:00:00Z --out /tmp/review-comments
```

Work from `comments.jsonl`: one short line per comment, with the reviewer, priority labels, path, line, and the commit an inline comment was made against. Filter it with `jq` and open full bodies in `comments.json` only for candidates. Comment bodies can carry confidential or customer data; apply the host's data policy before a model reads them, and keep collected output and derived cases out of the skill repository.

## Select cases

A labeled comment is a claim. Keep a finding only when all of these hold:

- It names a concrete defect in the changed code, not style or a question.
- It was confirmed: a later commit changed the flagged code in response, or the author agreed. Record which.
- The commit it was made against still exists and still contains the defect.
- The diff from the merge base to that commit is small enough to review in one session.
- A reviewer could find it from the repository alone, without production access or unwritten context.

Record the merge base, the reviewed commit, and your own restatement of each defect. Add controls: reviewed PRs of similar size with no such finding and no later fix. Report how many candidates each rule removed, and reviewer and repository concentration; a set drawn mostly from one bot measures agreement with that bot.

## Build workspaces

Give each case a `repository` fixture for `scripts/evaluate-skills.py`:

```json
{"case-id": {"repository": {"path": "/path/to/clone", "base": "MERGE_BASE_SHA", "head": "REVIEWED_SHA"}}}
```

The evaluator builds the workspace from two tree snapshots: `BASE` and `HEAD` are its only commits, and no branch, tag, or history of the source survives. A clone or worktree would not do. Its branches reach the merged fix, and guidance that says to compare against the current base tip would read the answer.

Keep the answer out of reach in the run as well. The prompt names the range and nothing about the finding. The evaluator seals every run: `gh` and the deployment, cloud, and secret CLIs resolve to stubs that fail, inherited credentials are removed, and Git may only use local transports. So a reviewer can neither fetch the PR thread nor touch a live system through them. A reviewer with a shell can still call a tool by absolute path, so confirm the seal with a probe run before trusting it on a new machine.

## Run and grade

Run the old and the new guidance on the same cases, hosts, and models, with repetitions. Grade blind to the arm, one criterion per recorded defect: the report identifies that defect at that location. For controls, the criterion is that no blocking finding is raised.

Count separately the blocking findings a report raises beyond the recorded ones. They are unverified, not false: the original reviewers may have missed them. Verify a sample against the code before calling them noise.

Score what a reviewer found separately from behavior only the new guidance defines, such as naming a review level; otherwise the new arm wins by matching its own wording. When every arm passes everything, the cases are too easy for that model: report a ceiling, not parity. Build grading packets from complete traces. A truncated or filtered command log produces false failures for criteria that require executed evidence.
