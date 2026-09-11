# Installed Pearl evaluation, 2026-09-11 UTC

Pearl produced inspectable investigation records and working calculations, but this sample did not establish fewer unsupported claims. I would keep it available for quantitative investigations that benefit from persistence. These results do not support making it a general requirement for factual accuracy or prose editing.

The [retained results](2026-09-11-pearl-evaluation.json) include all 45 final responses, saved files and database exports, relevant tool receipts, original grades, review corrections, input fixtures, plugin hashes, and independent CLI and hook probes. Full traces and frozen snapshots remain under `/tmp/mk-skills-pearl-study-20260911-jf6f871v/`, which is temporary storage. An author email supplied by a model without fixture support is redacted in the retained export.

## Comparison

The three conditions used the same frozen mk-skills catalog and shipped shared guidance: current guidance; Pearl 0.1.1 available through the catalog; and Pearl plus an instruction to use its reasoning skill, save evidence separately from assumptions, check calculations, and inspect the record before answering. The last condition combines several interventions, so it cannot isolate an effect of the CLI alone.

Claude Code 2.1.267 ran resolved model `claude-fable-5-1` twice on each of six synthetic cases per condition, 36 runs total. Cases covered missing queue measurements, three architecture designs, a confounded latency change, a faithful prose rewrite, a compute threshold, and a hypothetical Bayesian update. Codex CLI 0.154.0 ran requested model `gpt-6-astra` once per condition on the causal, threshold, and Bayesian cases, nine checks. Its traces do not expose a separate resolved model identifier.

All 45 processes completed without timeouts or execution failures. Two setup pilots are excluded. New controls were necessary because the branch and harness had changed since the [earlier study](2026-09-10-evidence-discipline-results.md).

Reviewed Fable answer counts follow. Support includes incidental claims in the answer and saved deliverables; borderline judgments remain separate from clear failures. Times are median elapsed host-process seconds for these matched cases, including reading, reasoning, and tool use.

| Condition | Supported | Borderline | Unsupported | Median seconds |
|---|---:|---:|---:|---:|
| Current, 12 runs | 1 | 2 | 9 | 35.1 |
| Pearl available, 12 runs | 0 | 2 | 10 | 43.0 |
| Explicit Pearl record, 12 runs | 2 | 2 | 8 | 62.0 |

The central conclusion was supported in 10, 10, and 11 of those 12 runs respectively. All threshold and Bayesian answers got the headline arithmetic right. The single additional compliant architecture answer in the record condition did not read Pearl or create a record. The sample is too small to establish an improvement, equivalence, or worsening; repetitions add a variability check, not new task coverage.

All nine Codex responses passed the support and usefulness checks, including its three current-guidance controls. That smaller subset provides no evidence of an accuracy gain or a general model ranking.

## What Pearl changed

In each Pearl condition, Fable received the routing skill's text in six of twelve runs: the causal, threshold, and Bayesian tasks. It did not activate Pearl for the queue critique, architecture designs, or prose rewrite, even with the conditional record instruction. The available condition created Pearl investigations in two runs; the explicit condition created them in six. Codex received the routing text in all three cases per Pearl condition and created records in one and three respectively.

The records helped inspection. In one causal answer, the saved record correctly limited a 0 to 80 ms bound to additive, nonnegative effects and no drift. The final answer omitted nonnegativity and also claimed a sequential toggle eliminated time drift. The record made the missing premise visible without ensuring the answer retained it.

Records can contain unsupported claims too. One Bayesian record attributed an exclusive causal structure to a README that supplied only hypothetical likelihoods. Other answers calculated the correct posterior and then asserted an unsupported sensitivity ranking. Queue critiques still invented typical millisecond latencies from an arrival rate, and compute recommendations still promised that a short measurement period would settle an unknown future workload.

Pearl stayed inactive on all six prose rewrites. Each retained that the cache was implemented, tests had not run, the read reduction was unmeasured, and production rollout had not happened. Minor scope or scheduling ambiguities are recorded separately. One answer misstated how many source sentences it merged. Adding Pearl did not address that editing-summary failure.

## Two concrete improvements

First, reject unknown engine-input keys and expose a working payload or schema through the CLI. Several Fable Bayesian runs inferred the payload shape from validation errors or read package code. More seriously, an independently reproduced typo changed the question while returning success:

| Request using the same network | Exit | Returned fault probability |
|---|---:|---:|
| `evidence: {A: positive}` | 0 | 0.6667 |
| `observations: {A: positive}` | 0 | 0.20 |

Pearl ignored `observations`, used no evidence, and returned the prior. The output's evidence probability changed from 0.24 to 1.0. This is a specific input-validation issue in installed CLI 0.1.1, independent of the model grades. A record of a successful calculation is insufficient if the engine silently solved a different problem.

Second, test a focused comparison between final material claims and their recorded inputs and assumptions. The existing record workflow made that comparison possible but did not perform it reliably. That is a candidate for another experiment, not a demonstrated fix. Routine prose does not need a durable probabilistic investigation.

## Scope and grading

This was an explicit-catalog comparison of the installed skills, resources, and CLI. Native plugin discovery, hook delivery, and other integrations were not exercised. I separately ran Pearl's actual prompt dispatcher on all six prompts. It emitted an advisory only for the Bayesian prompt, which both Pearl conditions already routed to the skills; it emitted nothing for the original queue critique or the other four prompts. That deterministic probe does not establish native host behavior.

Fresh Codex grading sessions received fixtures, final answers, saved artifacts, computed word counts, and relevant tool receipts. Condition and host labels were withheld, although artifacts could reveal Pearl use. I reviewed all final answers and checked material findings against the inputs and receipts. Five support controls and all six usefulness controls matched in each batch; the refusal control was correctly unhelpful but classified as incomplete rather than supported. That taxonomy disagreement remains recorded.

Review corrections distinguish a failed search from a true claim about file contents, conditional queue-loss reasoning from measured loss, and successful resume operations from literal command reproduction. Usefulness was normalized to the explicit request for three designs preserving the guarantee; graders inconsistently credited partial compliance. None of these scores is a calibrated estimate of general reliability.

The harness now accepts optional `--plugin` snapshots without introducing a Pearl dependency or changing installed configuration. Seven evaluator tests cover the new support and earlier fixes. The repository validator passed, including the Codex delegation checks. Production skill instructions remain unchanged.
