# PR review retrospectives

## Collect a defined window

For “comments from the last two weeks,” use comment posting time on any authored PR, including older, closed, and merged PRs. Resolve ambiguity about authorship, repositories, dates, or priorities when it would materially change the analysis. Freeze an explicit start and end with time zones.

The collector requires Python 3.9+ and authenticated `gh`. Run it from this skill's directory with an output directory outside the repository that doesn't already exist:

```sh
python3 scripts/collect_pr_comments.py \
  --start 2026-01-01T00:00:00Z \
  --end 2026-01-15T00:00:00Z \
  --out /tmp/pr-comments-2026-01-15
```

The author defaults to `gh api user`. Override with `--author LOGIN`; repeat `--repo OWNER/NAME` to restrict repository scope. Without a repository filter, the search covers repositories visible to that GitHub account.

The candidate search is `is:pr author:LOGIN updated:>=UTC_START_DATE`. It deliberately has no PR creation-date or state filter. It then paginates:

```text
GET /repos/{owner}/{repo}/issues/{number}/comments
GET /repos/{owner}/{repo}/pulls/{number}/comments
GET /repos/{owner}/{repo}/pulls/{number}/reviews
```

Conversation and inline comments use `created_at`; review bodies use `submitted_at`. The interval includes the start and excludes the end. Blank bodies and unpublished reviews are omitted from the comment corpus. The collector fails on API errors, incomplete searches, changing search totals, duplicate records, or results beyond the 1,000-result search cap. Narrow by repository if the candidate set is too large. Larger audits need an extension that partitions candidate PRs by creation date; this helper doesn't automate that partitioning. Splitting only the comment window may still select the same older PRs.

## Inspect the artifacts

| File | Meaning |
|---|---|
| `manifest.json` | Query, window, fetch time, counts, exclusions, and artifact hashes; written last as the completion marker. |
| `prs.json` | Candidate PR metadata, without PR description bodies. |
| `coverage.json` | Total fetched and in-window nonempty counts for each PR and comment surface. |
| `comments.json` | Collected comment bodies, identities, timestamps, file locations, reply relationships, and source URLs. |
| `priority-candidates.json` | Comments containing explicit P0/P1/P2/P3 tokens, including HTML badges; candidates for inspection, not established findings. |

Raw bodies can contain confidential data or credentials. The collector doesn't redact or certify them. Restrict local access and apply the host's data policy before exposing excerpts to a model or publishing summaries. The manifest contains no raw bodies. A failed run can leave a partial directory; without its completion marker it isn't a completed snapshot. Use a new output directory for a retry.

Report coverage from the actual result. GitHub search is indexed rather than a transactional snapshot. Deleted comments, unpublished reviews, inaccessible repositories, and index delays remain outside the guarantee. Bodies reflect their fetched versions, including edits; editing an old comment doesn't move it into the posting-time window. Don't infer thread resolution from REST inline comments.

For a stronger completeness claim, compare the recorded totals with an independent query. GraphQL `comments.totalCount` and `reviews.totalCount` check the corresponding REST surfaces; summing `reviewThreads.nodes.comments.totalCount` checks inline comments when every thread page is fetched. Investigate discrepancies, allowing for activity between requests. A matching total doesn't recover inaccessible or deleted records.

## Identify findings without inflating counts

Inspect explicit labels in plain text, Markdown, and badge alt text. Preserve the reviewer's label and interpretation; don't silently standardize inconsistent priority systems. If the user requests P2 and above, retain explicit P0, P1, and P2 findings without assigning priorities to unrated criticism.

Read label-bearing records before counting them. A “P0: None” section contributes no finding. A review summary or bot index can repeat inline findings; link it to the original URLs and count the originals. A body can contain multiple distinct findings, so comment counts and finding counts may differ. Keep a deduplication ledger rather than silently dropping records.

Retain fixed or resolved feedback for a retrospective unless the user asks for open issues only. Don't count acknowledgments or fixes as new defects. Preserve repeated observations across PRs or review rounds, then distinguish that repetition from the number of independent mechanisms. Report reviewer and repository concentration before generalizing.

For each lesson, keep the source finding, mechanism, proposed intervention, relevant skill, and a small evaluation example. The PR comment establishes what was reported. Confirm against the relevant revision before presenting its diagnosis as independently verified; don't re-review ratings when the user asked to preserve them.
