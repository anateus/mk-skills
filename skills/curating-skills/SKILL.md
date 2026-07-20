---
name: curating-skills
description: Use when deliberately reviewing configured upstream skill repositories for ideas or regressions since their recorded revisions.
---

# Curating Skills

Treat upstreams as read-only inputs to a conceptual merge. Installed skills remain self-contained and offline; network access belongs only to a deliberate review.

## Produce the review bundle

Run:

```bash
python3 skills/curating-skills/scripts/review-upstreams.py \
  --manifest config/sources.yaml --output /tmp/upstream-review.md
```

Use `--cache-dir PATH` to retain fetched repositories between reviews. The report lists commits, inventory changes, mapped diffs, and affected local skills. A fetch or manifest failure stops without changing provenance.

## Make a three-way decision

For each mapped change, compare:

1. current local behavior;
2. behavior at the recorded upstream commit;
3. current upstream behavior.

Identify the underlying idea, its benefit, and conflicts with local principles. Record an **accept** or **reject** decision and rationale. An accepted idea is adapted to local interfaces; never automatically copy upstream files. A rejected idea is still recorded so it is not reconsidered on every run.

Validate affected local skills and their contract tests after adaptations. Confirm attribution remains accurate. Advance `reviewedCommit` only after every relevant change has a recorded decision and validation is complete. Pin the exact reviewed head from the bundle.

## Safety boundary

The tool writes only the requested report and optional cache. It does not edit skills or pins. Never auto-push, open pull requests, or alter an upstream repository. Any local skill edit, provenance update, or external action requires the authority and review appropriate to that separate change.
