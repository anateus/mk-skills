# Diff provenance

## Fixed committed ranges

Record `BASE` before implementation or peer dispatch and keep the resolved base and head SHAs with the review. Use the full `BASE..HEAD` range. `HEAD~1` covers only the final commit and silently truncates multi-commit work. Before reporting, verify the comparison point and head have not moved.

Generate a stable package with `scripts/review-package BASE HEAD`. Declare excluded or generated content explicitly.

## Working-tree state

A committed package does not include later working-tree changes. Inspect and identify each layer separately:

```bash
git diff --cached --no-ext-diff --find-renames --unified=10
git diff --no-ext-diff --find-renames --unified=10
git ls-files --others --exclude-standard
```

State which staged, unstaged, and untracked files were reviewed. Inspect untracked files directly; an inventory is not their content. Re-run status and the relevant comparison immediately before the report so provenance matches the findings.
