# Evidence discipline evaluation, 2026-09-10

The harness now injects the shipped shared guidance into both hosts. It previously copied that file without putting its contents in the session context. After fixing that omission, I ran 48 evaluations of current guidance and three candidate additions. This sample does not justify adopting the additions: unsupported claims remained common in the Fable runs, including with a reasoning scaffold inspired by Pearl. Production instructions are unchanged.

The [saved results](2026-09-10-evidence-discipline-results.json) contain all 48 final responses, original grades, review corrections, relevant tool receipts, computed counts, input fixtures, and source hashes. Full local traces and frozen snapshots are under `/tmp/mk-skills-evidence-study-20260910-g05t7ra3/`; that temporary directory is not a durable archive.

## What was tested

All conditions used the same skill catalog, shipped shared guidance, and selective profile. The additions were:

| Condition | Additional instructions | Added words |
|---|---|---:|
| Current | None | 0 |
| Rule | Ground claims, preserve assumptions, inspect or omit missing premises | 69 |
| Rule + audit | Rule, then check claims that carry the conclusion | 116 |
| Rule + scaffold | Rule, then choose a reasoning method suited to the available evidence | 147 |

The [candidate text and cases](../../tests/fixtures/evidence/) stay separate from installed skills. Six synthetic cases cover a queue with missing quantities, exact queue losses, creative architecture options, a confounded performance change, faithful prose, and a compute-cost threshold. Rubrics score factual support and usefulness separately, allowing conditional designs and calculations while penalizing unsupported assertions and unnecessary refusal.

Claude Code 2.1.267 ran `claude-fable-5-1`: all six cases once per condition, with a second run of the missing-quantity, causal, and threshold cases. That gives nine runs per condition, 36 total. Codex CLI 0.154.0 ran 12 checks using requested model `gpt-6-astra`, covering the missing-quantity, creative-design, and threshold cases once per condition. Claude's traces confirm its model identifier; the Codex traces do not expose a separate resolved identifier.

Runs used fresh disposable workspaces, frozen inputs, and a shuffled schedule. Two preliminary pilot runs are excluded. All 48 recorded processes exited successfully without timing out; process success does not establish answer quality. The Claude child processes removed an inherited, refusing localhost `ANTHROPIC_BASE_URL` override. No saved host configuration changed.

## Results

These are reviewed answer counts for Fable. A response can be useful while containing an unsupported claim. Borderline cases separate debatable incidental assertions from clear failures.

| Condition | Supported | Borderline | Unsupported | Useful | Runs |
|---|---:|---:|---:|---:|---:|
| Current | 2 | 2 | 5 | 8 | 9 |
| Rule | 2 | 0 | 7 | 7 | 9 |
| Rule + audit | 1 | 0 | 8 | 8 | 9 |
| Rule + scaffold | 1 | 1 | 7 | 5 | 9 |

All 12 Codex responses were supported and useful under their case rubrics. That smaller, three-case subset cannot establish general reliability or a model ranking. Repeating a case adds a variability check, not new task coverage. This study supports neither an equivalence claim nor a statistically established difference between conditions.

The clearest failures occurred after correct initial reasoning. Every Fable exact-count answer got 40 lost and 40 remaining tasks right. Threshold answers calculated the 8,000-task break-even point, then sometimes added unsupported claims about expected cost, sufficient measurement periods, or switching costs. Both scaffold threshold runs recommended using the median workload where average compute depends on the mean. A constructed counterexample, six days at 7,000 tasks and four at 10,000, has median 7,000 but mean 8,200: Plan A uses 2,000 CPU-minutes over those days; Plan B uses 2,040.

Causal answers often rejected the initial cache attribution correctly, then treated cache-hit and cache-miss cohorts as identifying an effect without establishing comparable populations. The creative-design answers offered useful ideas, but none of the four Fable responses supplied three designs preserving the stated eventual-execution guarantee; unsupported relative latency claims also appeared. These are failures on one architecture prompt, not evidence that the additions generally suppress creativity.

All four Fable prose files preserved the supplied implementation, measurement, test, and rollout status. Some accompanying commentary invented counts or described checks inaccurately. One answer claimed 47 source words and 33 rewritten words; the saved files contain 36 and 31 whitespace-delimited words.

## The grader needed correction too

A fresh Codex session graded each batch with generating host and condition hidden. It saw fixtures, rubrics, final answers, and saved prose, but not tool receipts. I then read all 48 answers and checked the prose receipts and mechanical quantities. The original grades remain alongside corrections. The grader differs from Fable, but uses the same model family as the Codex generation sample.

Both grading batches detected two planted fabrications and accepted two valid conditional or mathematical answers. A fifth control was an unhelpful refusal. Both rejected its usefulness, but disagreed on support because its claim that nothing could be concluded was itself false. That control has an ambiguous support expectation; it is not evidence of clean calibration.

The grader falsely questioned Vale completion claims: all four prose runs did execute Vale and report zero strong and weak cues. It also supplied another wrong word count, 46 to 35. Separately, three prose runs masked an unsupported `grep -P` invocation with a success-looking fallback. Their files happened to contain no prohibited dashes, but one answer explicitly claimed the failed search had passed. The fourth run recovered with a successful Python check. A correct artifact and a successful verification command are separate claims.

## What to take from Pearl

Pearl's reasoning skill routes work toward exact calculation, bounds, a discriminating observation, or more involved modeling according to the question and available inputs. Its evidence guidance separates observations from assumptions and generated outputs. The local implementation also stores assumptions, evidence, and analyses separately; its generic record payloads do not enforce factual truth.

The 78-word scaffold borrowed that method-selection idea without importing a package, invoking Pearl, or requiring a fixed response format. This test does not establish that Pearl's engines or written investigation records would fail: neither was used. A useful next experiment would make the material claim and its supporting input inspectable, with calculations checked by tools where possible. That is a different intervention from adding another generic reminder. Keep it conditional on consequential uncertainty so routine prose and creative exploration stay lightweight.

## Harness changes and validation

The runner now supports explicit model selection, composable candidate instructions, and fresh repetitions. Snapshots include the runner, inputs, guidance, and execution settings. Each run records the exact context and command. Fixture-local AgentPlan and Zellij stubs keep ordinary coordination commands from touching real sessions; this is not a security boundary.

The shared-guidance regression failed before the fix and passed afterward. The evaluator suite covers both host adapters, frozen inputs across repetitions, hidden rubrics, coordination stubs, invalid case IDs, and recorded failures/timeouts. See the [forward-test guide](../validation/skill-activation-forward-tests.md) for commands and grading requirements.
