# PR check triage

Use this when a PR's CI is failing or someone asks whether its checks are green. This is an evidence workflow, not permission to push, merge, rerun jobs, or access restricted logs.

1. Resolve the actual PR and current head commit. If no PR is attached, report that boundary instead of treating branch runs as PR checks.
2. Inspect all checks attached to that PR/head, including external providers. `gh pr checks --json name,bucket,state,workflow,link` can list the attached set; `gh run list` only covers GitHub Actions and cannot establish completeness. Capture each relevant check's state and link.
3. Investigate the first actionable failure using its relevant logs or external link where access is authorized. For GitHub Actions, inspect the linked run's failed logs. Distinguish a real failure from pending, skipped, cancelled, or unavailable evidence; apply the normal competing-hypothesis investigation before changing code.
4. After an authorized change, refresh both PR head and the full attached check set. Attribute results to the current head, not a previous commit or stale snapshot. Bound retries and waiting; report unresolved checks rather than looping indefinitely.
5. Report separately: attached check status, required-check status under branch protection, and actual mergeability. Green attached checks alone do not prove that the required set is satisfied or that the PR can merge. Do not push or merge without authorization.
