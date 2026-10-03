# Prepare GitHub PRs for review

`scripts/prepare-pr-review` collects review inputs without calling a model, changing a checkout, posting comments, or running repository test commands. Use it to do mechanical preparation once, then give a reviewer the small indexes and let them open source chunks as needed.

## Capture

Requirements: Python 3.9+, Git, authenticated GitHub CLI, and existing local clones. `--repos-root` accepts either `ROOT/OWNER/REPO` or `ROOT/REPO`; the helper verifies each clone's GitHub origin before using it.

```sh
/path/to/reviewing-code/scripts/prepare-pr-review \
  https://github.com/OWNER/REPO/pull/123 \
  https://github.com/OWNER/REPO/pull/124 \
  --repos-root /path/to/clones \
  --output /path/to/new-review-bundle
```

Add `--requirements-dir /path/to/safe-exports` to attach caller-supplied Markdown or JSON requirements. The helper extracts `DOM-*` references from PR titles and bodies, but it doesn't fetch Linear or prove that an imported file covers every referenced ticket. No supplied requirements means an explicit context gap.

The top-level `README.md` and `index.json` link each PR and record supplied stack relationships. Each PR has pinned base/head/merge-base provenance, raw PR metadata and discussions, a complete Git file inventory, per-file diffs and before/after text, numbered source chunks of at most 150 lines, nearby guidance, and test-command excerpts. Capture doesn't mark any path reviewed. Binary, submodule, symlink and sensitive-path handling is recorded rather than hidden.

Sensitive paths are omitted from blob and per-file diff output. When sensitive paths change, the combined diff is withheld with an explanation; other per-file diffs remain available. This path filter isn't a secret scanner or a customer-data sanitizer. Raw discussions and imported requirements can still contain confidential or protected material, so a local bundle does not grant permission to send it to a model.

## Optional OCR

Add `--ocr` to save local `ocr delegate preview` and `ocr delegate rule` JSON plus the installed OCR version. These commands don't call a model. The helper never invokes `ocr review`, `scan`, or `llm`.

Git's complete inventory remains authoritative. OCR's preview can exclude tests, deleted files or other paths; its selection is supplementary, not proof that the excluded files were reviewed. Its rules provide another review checklist, not a correctness verdict.

## Offline replay

Repeat the original URLs and output directory with `--reuse`. Replay verifies capture hashes and requires the pinned Git objects locally. It makes a separate replay directory, retains the original guidance, imported requirements and OCR outputs, and needs no GitHub or OCR invocation.

```sh
/path/to/reviewing-code/scripts/prepare-pr-review \
  https://github.com/OWNER/REPO/pull/123 \
  --repos-root /path/to/clones \
  --output /path/to/existing-review-bundle \
  --reuse
```

Original captures aren't overwritten. The helper's own top-level indexes can refresh, but unrelated files are not replaceable. Annotate a separate coverage-manifest copy during review because changing the original capture invalidates its replay hashes. A changed PR needs a new online capture in a new output directory, followed by renewed review of affected files.

API, fetch, pagination and provenance failures return nonzero and leave an explicit incomplete-capture record. A zero exit means preparation succeeded, not that the PR passed review, its tests passed, or its live workflow was validated. Discussions are retained as fetched, not as an atomic GitHub-wide snapshot.
