---
name: curating-skills
description: Compare configured upstream skill changes against recorded revisions and local behavior, record accept or reject decisions, and update provenance only after validation. Use only when maintaining the mk-skills source repository and deliberately reviewing its configured upstream skill repositories.
---

# Curating Skills

Treat upstreams as read-only inputs to a conceptual merge. This is an mk-skills maintainer workflow: it requires a checked-out mk-skills source repository and deliberate network access. Ordinary installed skills remain self-contained and offline.

## Produce the review bundle

Discover and verify the target repository first. `git rev-parse --show-toplevel` must succeed, and `$REPO_ROOT/.codex-plugin/plugin.json` must have `name` equal to `mk-skills`; otherwise stop clearly. Then run the bundled script from its skill base, not relative to the current directory:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
python3 "<skill-base-dir>/scripts/review-upstreams.py" \
  --manifest "$REPO_ROOT/config/sources.yaml" \
  --output /tmp/upstream-review.md
```

Use `--cache-dir PATH` to retain fetched repositories. The report lists commits, inventory, mapping liveness at both revisions, affected skills, unique diffs, and Git warnings. Trace moved or deprecated sources to their current loader before treating a quiet mapping as unchanged. Fetch or manifest failures leave provenance untouched.

## Make a three-way decision

For each mapped change, compare:

1. current local behavior;
2. behavior at the recorded upstream commit;
3. current upstream behavior.

Read `$REPO_ROOT/config/curation-decisions.json` before deciding. Identify the underlying idea, its benefit, and conflicts with local principles. Append an **accept** or **reject** record spanning the prior pin to the exact reviewed head. An accepted idea is adapted to local interfaces; never automatically copy upstream files. A rejected idea is still recorded so it is not reconsidered on every run.

Validate affected local skills and their contract tests after adaptations. Confirm attribution remains accurate. Advance `reviewedCommit` only after every relevant change has a recorded decision and validation is complete. Pin the exact reviewed head from the bundle.

Prefer distinct triggers and conditional references over repeated instructions. Test proposed removals on realistic requests in fresh sessions, withholding the intended answer and rubric. Static wording checks do not establish equivalent behavior.

## Safety boundary

The tool writes only the requested report and optional cache. It does not edit skills or pins. Never auto-push, open pull requests, or alter an upstream repository. Any local skill edit, provenance update, or external action requires the authority and review appropriate to that separate change.
