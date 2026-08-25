---
name: investigating-incidents
description: Investigate live or historical production incidents across services, queues, databases, providers, and protocol boundaries using an evidence ledger, comparable cohorts, bounded parallel probes, and explicit correction history. Use when an outage, throughput collapse, provider regression, degraded metric, or cross-system failure needs cause-level diagnosis without repeated rediscovery or premature root-cause claims.
---

# Investigating Incidents

Find the causal mechanism while preserving an auditable path from symptom to conclusion. Use `diagnosing-bugs` for the underlying hypothesis loop; add this workflow for distributed evidence, live-system boundaries, parallel research, and incident communication.

## Establish the incident contract

Record the symptom, impact, expected baseline, first known bad and last known good windows, timezone, affected cohort, environment, and allowed actions. Separate read-only investigation from mutations such as config changes, restarts, ticket updates, or deploys.

Trace the current runtime path from imports, entrypoints, deployed configuration, and observed identifiers. Label legacy, current, and target paths explicitly. Treat manifests, READMEs, dashboards, and design docs as leads until runtime wiring corroborates them.

## Create the evidence model

Open a ledger before interpreting data. Record observations, hypotheses, disconfirmers, decisions, and corrections without overwriting earlier conclusions. Attach source, timestamp/window, scope, layer, actor, identifier, and confidence to each material claim.

Read [distributed evidence](references/distributed-evidence.md) when the incident crosses service/provider boundaries, uses multiple clocks or call/request legs, compares cohorts, or depends on status-code semantics. Read [the evidence ledger](references/evidence-ledger.md) when creating or reconciling the working artifact.

## Run discriminating probes

Maintain at least two plausible hypotheses until a discriminating observation separates them. Prefer the cheapest reversible observation that should differ between hypotheses.

Use comparable cohorts: identical windows and timezones, explicit denominators, null rates, instrumentation coverage, and deployment/config boundaries. Trace representative entities end to end using stable correlation IDs. Pair volume with dwell time, concurrency, retry, or queue depth so a rate change has a mechanism.

A hypothesis is tested by the observations it does not explain. If it covers K of N failures, the remaining N-K are the test: count both, and treat "the rest are noise" as a claim needing its own evidence.

When independent surfaces justify parallel work and agent execution is available, read [parallel investigations](references/parallel-investigations.md). Bound the first wave, give each probe a distinct discriminator, and reconcile all returns before dispatching more work.

## Reconcile and communicate

Do not silently replace a diagnosis. Add a correction stating what changed, which evidence forced it, and which downstream claims or tickets need revision. Distinguish primary cause, throughput amplifier, latent bug, and unrelated co-occurring failure.

Claim root cause only when evidence identifies the mechanism and rules out the strongest alternatives. Otherwise report the leading hypothesis and the smallest missing discriminator. Stop when new probes repeat existing evidence or cannot change the decision.

Report: current verdict and confidence; impact; causal chain; decisive evidence; corrections; ruled-out alternatives; remaining unknowns; recovery indicators; and next actions with owners or required authority.

For retrospective mining of Claude Code JSONL sessions, read [session retrospectives](references/session-retrospectives.md) and run the bundled summarizer before inspecting the raw transcript selectively.
