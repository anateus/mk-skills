# Replaying past findings

Use this to measure a change to review guidance against defects real reviewers already found, or that review missed and a later fix exposed, instead of against cases written for the change. It needs a checked-out mk-skills source repository for the evaluator and the corpus script, authenticated `gh`, and network access to the repositories under study.

## Keep a corpus

Cases are expensive to select, so keep them. `scripts/review-corpus.py` maintains a corpus outside the skill repository (`--corpus`, `MK_SKILLS_REVIEW_CORPUS`, or `~/.local/share/mk-skills/review-corpus`) and refuses a path inside the checkout, because cases restate defects in someone's private code. The corpus is its own local Git repository: one JSON file per reviewed change under `cases/`, and a bare mirror per source repository under `mirrors/`.

```sh
python3 scripts/review-corpus.py add-repo NAME https://github.com/OWNER/NAME.git
python3 scripts/review-corpus.py resolve --repo NAME --pr 123 > case.json   # merge base and head filled in
python3 scripts/review-corpus.py add case.json                              # after adding findings, or "control": true
python3 scripts/review-corpus.py build --out /tmp/review-run                # cases.json, workspaces.json, criteria/
```

`add` fetches both revisions into the mirror, rejects a base that is not the merge base, and merges new findings into an existing case without renumbering the old ones. Each finding records its `source`: `review-comment` when a reviewer raised it before merge, `escaped` when review let it through. `build --source` selects one kind, and `{title}` in `--prompt` becomes the PR title when the run should know the stated intent.

## Collect

Collect every published comment on the repositories' PRs with the [PR comment collector](../../learning-from-mistakes/references/pr-reviews.md), which lives in the sibling `learning-from-mistakes` skill:

```sh
python3 "<skill-base-dir>/../learning-from-mistakes/scripts/collect_pr_comments.py" --any-author \
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

## Find what review missed

Findings from review comments only measure whether new guidance finds what a reviewer already found. The defects that matter most for trusting a review are the ones that merged and needed a hotfix, revert, or correction.

```sh
python3 scripts/review-corpus.py fetch
python3 scripts/review-corpus.py candidates --repo NAME --since 2026-01-01 > candidates.jsonl
```

`candidates` reads the mirror only. It takes each corrective commit on the default branch (a revert, hotfix, rollback, regression, or `fix` subject), blames the lines it rewrote, and pairs it with the PR that last touched them within `--window-days`. A pair is a lead, and most are ordinary follow-up work. Keep one only when all of these hold:

- The earlier PR shipped wrong behavior and the later change corrects it, by the fix's own account. Planned follow-ups, scope extensions, tuning of a deliberate value, and product reversals are not defects.
- A reviewer could have found it from that PR's diff and the repository at the time. A defect learned from production traffic, or one whose evidence sits in another repository the workspace will not contain, cannot be scored against a single-repository review.
- The earlier PR is small enough to review in one session.

The case is the earlier PR, from its merge base to its merged head, and the finding records the fix and what reviewers said at the time. Report the rejections by rule here too. In one pass over three repositories, 8 of 149 leads qualified.

## Build workspaces

Give each case a `repository` fixture for `scripts/evaluate-skills.py`:

```json
{"case-id": {"repository": {"path": "/path/to/clone", "base": "MERGE_BASE_SHA", "head": "REVIEWED_SHA"}}}
```

The evaluator builds the workspace from two tree snapshots: `BASE` and `HEAD` are its only commits, and no branch, tag, or history of the source survives. A clone or worktree would not do. Its branches reach the merged fix, and guidance that says to compare against the current base tip would read the answer.

Keep the answer out of reach in the run as well. The prompt names the range and nothing about the finding. The evaluator seals every run: `gh` and the deployment, cloud, and secret CLIs resolve to stubs that fail, inherited credentials are removed, and Git may only use local transports. So a reviewer can neither fetch the PR thread nor touch a live system through them. A reviewer with a shell can still call a tool by absolute path, so confirm the seal with a probe run before trusting it on a new machine.

## Run and grade

Run the old and the new guidance on the same cases, hosts, and models, with repetitions. Add a third arm with `--no-skills`: without it you can show that two versions of the guidance tie and never learn whether either beats no guidance. Name the skill in the prompt when the question is whether the guidance helps once it is used; leave it out only to test whether a host selects it.

`--host omp` runs the host's own skill discovery over the frozen snapshot and keeps subagents on the model under test, so the levels that need a fresh reader can run. The `claude` and `codex` hosts get the catalog as text and have no subagent tool, so a run there cannot go past separate passes.

Before grading, read the traces for what each run did, from tool-call inputs only: whether it read `SKILL.md`, which references it opened, whether it started other readers, and what it executed. A reference nobody opens cannot have helped, and a run that failed or timed out did not review.

Grade blind to the arm, one criterion per recorded defect: the report identifies that defect at that location. This measures recall of known findings; the recorded list is not the complete set of defects in the change.

To evaluate a merge policy, fix the policy before looking at the held-out reports and apply it outside the reviewer. Report together how often it would merge a case with a recorded blocking defect and how often it lets controls through. A policy that defers everything stops every known defect but tells you nothing about which changes could merge. A severity count alone is not a safety check. Use `review-corpus.py controls` to find merged PRs with no nearby corrective commit in the same code, then check their review threads before adding them.

Compare arms on the same cases and report repeats, failures, and review time on small changes separately. Keep detection and severity separate: a reviewer can find the right defect and label it too low, or block for an unrelated reason without finding it. Where execution is unavailable, distinguish checked CI results for the exact head from missing evidence.

Count separately the blocking findings a report raises beyond the recorded ones, on controls as well. A control is a PR nobody objected to, not a PR without defects. Extra findings are unverified, not false: the original reviewers may have missed them. Count one against an arm only after checking it against the code at `BASE` and `HEAD` and finding it wrong.

Score what a reviewer found separately from behavior only the new guidance defines, such as naming a review level; otherwise the new arm wins by matching its own wording. When every arm passes everything, the cases are too easy for that model: report a ceiling, not parity. Build grading packets from complete traces. A truncated or filtered command log produces false failures for criteria that require executed evidence.
