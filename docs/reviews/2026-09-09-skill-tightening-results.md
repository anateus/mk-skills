Humanizer now uses Vale for deterministic pattern checks and the LLM for judgment and rewriting. The catalog is conditional. The other approved workflow changes and upstream adaptations are implemented in this checkout.

Use the scanner from the source repository:

```bash
python3 skills/humanizer/scripts/prose-check.py draft.md
python3 skills/humanizer/scripts/prose-check.py draft.md --details StockWords
python3 skills/humanizer/scripts/prose-check.py --explain Contrasts
```

Strong cues show locations and matched text. Weak cues show counts, with optional drill-down. The wrapper never changes files or calls an LLM. Markdown parsing excludes frontmatter, code, link destinations, and blockquotes. Voice, claim preservation, repetitive structure, and whether a match needs an edit still require judgment. Vale is optional for installed skills; this machine has Vale 3.20.0. See [configuration and custom rules](../../skills/humanizer/references/prose-checks.md).

In five local runs over one synthetic 1,700-word, 9,500-byte document, wrapper-plus-Vale latency ranged from 34 to 84 ms, with a 34 ms median. It detected the 100 planted strong and 100 planted weak cues. This measures a small repeated-pattern workload, not detection quality or end-to-end editing speed.

The instruction changes preserve the concrete boundaries while removing repeated process:

- Clarification groups independent questions and sequences dependent ones. Reversible feasibility probes can resolve empirical uncertainty within existing authority.
- Feedback assesses a concern separately from its proposed remedy. Re-review follows the fix and nearby effects, broadening when contracts change.
- Plans link their specification, specify the next slice precisely, and defer uncertain detail. Wide migrations can use expand, migrate, then contract stages.
- Verification can reuse directly inspected evidence while relevant inputs remain unchanged and current instructions permit it. Negative search controls use disposable fixtures, never planted data in the real corpus.
- Reporting fields are conditional; only generated handoff artifacts need a regeneration command. Incident-specific clocks, cohorts, actors, denominators, and correction history remain intact.
- Strict injection points to its skill. Shared guidance is shorter, and peer identity details load separately. Ordinary skills still work without the shared block.

Whitespace-separated word counts compare baseline commit `954fb58fa40e345402a72784bd422f461e2efb3e` with this implementation. These are file measurements, not model token usage or session savings:

| Surface | Baseline | Candidate |
|---|---:|---:|
| All 20 entry files, including descriptions | 6,890 | 6,647 |
| Shipped shared guidance | 1,128 | 516 |
| Strict injection | 238 | 14 |
| Mandatory full catalog read for ordinary Humanizer edits | 4,694 | 0 |

The optional catalog still exists and now vendors upstream 3.0.0. The installed host guidance files were not rewritten by this task.

Behavioral evaluation now has a [runner](../../scripts/evaluate-skills.py), 31 activation cases, and 15 synthetic workspace fixtures. It snapshots and hashes skills, creates fresh Git workspaces, keeps rubrics out of prompts, and records traces, artifacts, timing, and pending grading. Exact-description snapshots and prose-presence tests were removed. Structural, link, budget, policy-selection, hook, and executable-helper checks remain.

I assessed 32 fixture runs, including the baseline/candidate sample, strict routing, new capabilities, and two critique follow-ups. [The data file](2026-09-09-skill-tightening-results.json) records individual snapshots, host versions, reads, raw token counters, results, and artifact locations. This is an explicit-catalog harness, not a native plugin-discovery test. Codex also displayed account-level writing guidance; its source was not isolated by the filesystem configuration flags. Do not infer cross-host parity or instruction-only causality from these runs.

| Case | Codex baseline/candidate | Claude baseline/candidate |
|---|---|---|
| Clear implementation | Both implemented JSON output and preserved text output | Both implemented JSON output and preserved text output |
| Trivial typo | Both changed only the typo | Both changed only the typo |
| Mixed-state review | Both covered committed, staged, unstaged, untracked, and generated content | Both covered those layers |
| Short prose preservation | Both preserved the claims; candidate avoided the catalog | Both preserved the claims; candidate avoided the catalog |
| Interactive critique | Both used the skill and asked a material question | Both used the skill, but introduced unsupported quantitative claims |
| Zellij routing | Unavailable-server fixture only | Unavailable-server fixture only |

The prose fixture includes a ranking, simultaneous work, an unmeasured production gain, MUST wording, an identifier, a quoted error, a link, and a code block. Both baseline hosts read the catalog. Both candidates used the scanner without reading the catalog. Observed run times were 36.4 to 30.6 seconds on Codex and 33.5 to 31.1 seconds on Claude; single runs and shared caches cannot establish a general speed improvement.

Both hosts loaded `strict-mode` from the 14-word injection before completing a typo edit. These used host defaults; the smaller model families that automatically select strict mode were not exercised. Four additional Codex cases correctly grouped independent choices, deferred a dependent cloud-region question, kept required caching while fixing expiration, and caught a caller broken by a return-type change during re-review. I reran the implementation outputs and cache-boundary checks directly.

The critique runs show a remaining quality limit. Claude inferred queue capacity from request rate without task size or dwell time. A follow-up warning did not prevent it; replacing the prescribed steelman with a check of the stated benefit also failed to prevent a later calculation from mixing aggregate and per-worker rates. The final skill keeps the shorter evidence check. These failures remain recorded, including the baseline failure; no claim of unchanged quality across tasks is warranted.

The first Claude evaluation batch is excluded. Safe mode alone retained local style/plugin metadata, and its Zellij case inspected the real host. I interrupted that probe and reran with explicit setting and tool restrictions plus a fixture Zellij command. The corrected initialization reported default style and no plugins. The unavailable-server fixture does not prove pane creation or waiting, and does not consistently exercise the peer reference. Native discovery and live pane-control validation remain release checks.

All four upstream sources have recorded accept/reject decisions and exact reviewed pins in [the ledger](../../config/curation-decisions.json). The curation helper reports path liveness, retains Git warnings, and links each unique mapped file diff once. Spec Kitty now maps to the built-in manifest used by its current loader; the final refresh's additional Windows binary-write fix required no local adaptation. The review covers mapped skill changes and selected new ideas, not every implementation change across Spec Kitty.

The review-package helper now generates distinct portable temporary paths. The ast-grep example separates preview from apply. Repeated review-package calls passed, the preview left its fixture unchanged, and guidance merge preview, backup, surrounding-content preservation, and repeat application were checked on a disposable target.

Repository validation is recorded at `/tmp/mk-skills-validation-final-20260909.log`. All 20 skills also passed the skill-creator validator. The Vale integration has eleven checks; the evaluation runner has four. These deterministic checks establish the helper and packaging behavior, not universal LLM compliance.
