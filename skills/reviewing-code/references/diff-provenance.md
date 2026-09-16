# Diff provenance

## Fixed committed ranges

Record `BASE` before implementation or peer dispatch and keep the resolved base and head SHAs with the review. Use the full `BASE..HEAD` range. `HEAD~1` covers only the final commit and silently truncates multi-commit work. Before reporting, verify the comparison point and head have not moved.

For a committed range, run `"<skill-base-dir>/scripts/review-package" BASE HEAD`; it writes the committed diff and a Git inventory under `${TMPDIR:-/tmp}` and prints only the package path. Declare excluded or generated content explicitly.

## Coverage bookkeeping

Use Git's changed-file inventory as the coverage baseline, including deletions and renames. Record each entry as reviewed, partial, skipped, or unreviewed, with reasons for partial or skipped coverage. Reconcile tool and peer results against it; filtered, binary-classified, failed, or truncated inputs do not count as reviewed. For a small diff, keep this in the report; use the manifest across reviewers, runs, or revisions.

## Coverage manifest

The helpers require Git and Python 3.9+. `review-package` keeps its single-path stdout contract and writes a second file at `<package-path>.manifest.json`. Preserve both when moving the review out of temporary storage. The manifest records the repository root, resolved comparison revisions, and every Git change, including deletions, renames, mode changes, and binary entries. Each entry has old/new paths, Git object IDs, and modes; submodule IDs identify commits rather than blobs. The patch can omit binary content, so inspect it separately when relevant.

Edit only each file's `coverage` and `reason`, plus the top-level `review_failures` list. Coverage starts as `unreviewed`; set it to `reviewed`, `partial`, or `skipped` as appropriate. Partial and skipped entries require a reason. Record failed or truncated review work in `review_failures` even if another pass inspected the same files; remove an item only after resolving it. Findings belong in the review report, not this list.

From the same checkout, check the manifest against the intended comparison before reporting:

```bash
"<skill-base-dir>/scripts/review-coverage" /path/to/package.manifest.json BASE HEAD
```

The checker recomputes the Git inventory, rejects missing, duplicate, altered, or stale entries, and prints a JSON coverage summary. Exit `0` means every entry is declared reviewed and no review failures remain; `1` means partial, skipped, unreviewed, or failed work remains; `2` means invalid input, changed provenance, or a Git failure. A justified skip can still support a scoped review report. The checker validates recorded coverage, not review quality or absence of defects.

After a revision changes, generate a new package and revalidate affected files and dependent findings. Carry decisions forward only after checking their assumptions; do not update the old manifest's identity fields to make it pass. The checker validates the revisions supplied to it, so refreshing remote PR state remains the caller's responsibility. Working-tree changes need the separate checks below.

## Working-tree state

A committed package does not include later working-tree changes. Inspect and identify each layer separately:

```bash
git diff --cached --no-ext-diff --find-renames --unified=10
git diff --no-ext-diff --find-renames --unified=10
git ls-files --others --exclude-standard
```

State which staged, unstaged, and untracked files were reviewed. Inspect untracked files directly; an inventory is not their content. Re-run status and the relevant comparison immediately before the report so provenance matches the findings.

## GitHub comparisons

For a PR, record the base branch revision, merge base, and head revision. Pass the merge base and head to `review-package` when reviewing the PR's three-dot diff; passing the base branch tip requires it to be an ancestor and may describe a different comparison. Record a CI merge commit separately when that is what CI executed. A downloaded patch needs the same provenance captured alongside it.

Use `--base-tip BASE_TIP` on both helpers to bind coverage to the PR's base branch revision as well as its merge base and head:

```bash
"<skill-base-dir>/scripts/review-package" MERGE_BASE HEAD --base-tip BASE_TIP
"<skill-base-dir>/scripts/review-coverage" /path/to/package.manifest.json MERGE_BASE HEAD --base-tip CURRENT_BASE_TIP
```

This catches base branch movement even if the merge base and head stay unchanged. The helpers require a unique merge base matching `BASE`; investigate ambiguous ancestry explicitly. Record repository owner/name, PR number, and any CI merge revision alongside the artifacts; local Git cannot infer which remote PR a comparison represents.
