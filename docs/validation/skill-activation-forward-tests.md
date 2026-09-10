# Skill activation forward tests

Static checks validate packaging, references, budgets, and executable helpers. Wording snapshots cannot establish agent behavior. Run forward evaluations after changing activation or process instructions.

## Run the catalog harness

```bash
python3 scripts/evaluate-skills.py --list
python3 scripts/evaluate-skills.py --host codex --case humanizer-preserves-claims --output /tmp/skills-candidate-codex
python3 scripts/evaluate-skills.py --host claude --case humanizer-preserves-claims --output /tmp/skills-candidate-claude
python3 scripts/evaluate-skills.py --source /path/to/baseline-checkout --host codex --case humanizer-preserves-claims --output /tmp/skills-baseline-codex
```

Repeat `--case` to select cases; `--profile strict` tests strict injection. Output must be a new directory. The runner snapshots skills and policy once, hashes their contents, creates a fresh Git workspace for every case, passes only the raw fixture prompt as the user message, and records traces, elapsed time, host version, before/after file hashes, changed files, and pending grading. Rubrics are materialized only after the host exits. A timeout terminates only that run's process group. Exit 0 reports successful processes, not passing behavior.

This is an explicit-catalog harness. Both hosts receive the same available-skill descriptions and paths, then choose what to read. Claude uses safe mode; Codex disables known installed skill paths, user configuration, project guidance, hooks, plugins, and apps for that invocation. Authentication and administrator policy remain host-owned. Neither adapter changes installed configuration. Inspect traces for contamination; the harness does not establish native plugin discovery or sandbox isolation. Keep fixtures synthetic and local.

Fifteen cases have workspace fixtures in `tests/fixtures/evaluation-workspaces.json`. Others require a suitable `--fixtures` file keyed by case ID. Each entry supports `commits` (ordered file-content maps), `staged`, `unstaged`, and `untracked`. Provide real scenario inputs rather than asking an agent to imagine missing code. The Zellij case exercises reference routing and reports the unavailable server; it never spawns a real pane. To test another host, `--host custom --command-json adapter.json` accepts an argv array with `{workspace}` and `{context}` placeholders and sends the raw prompt on stdin.

Grade the response and actual artifacts against the withheld rubric. Record false activations, unnecessary questions, reference reads, semantic preservation, elapsed time, and token usage when the trace exposes it. Read commands and their results before counting a reference as loaded; a path merely mentioned in an answer is insufficient. Missing traces leave activation unknown. Repeat variable or failed cases in fresh sessions. Compare the same inputs, host, profile, and model before generalizing instruction removal results.

## Native host discovery

The catalog harness separates instruction behavior from installation. Also test native discovery before release:

## Prepare the exact build

1. Run `node scripts/validate.js` in the branch under test.
2. Install or link that exact checkout in a disposable host setup. Record the branch, commit or working-tree identity, host versions, profile, and date. Do not replace a user's installation merely to run an evaluation.
3. Use the selective profile unless the fixture explicitly requests strict mode. Remove unrelated conversation and project context.

## Run each case

1. Start a new clean Codex or Claude session.
2. Copy only the raw `prompt` from `tests/fixtures/activation-cases.json`. Do not include expected skills, references, rubric, suspected bugs, intended fixes, or any other answer cue.
3. Inspect available trace or context output for loaded skills and references. Then compare the response behavior with the rubric.
4. Record four result classes separately: false negative (expected skill absent), false positive (forbidden or unrelated skill loaded), unnecessary reference load, and behavior failure despite correct activation.
5. After changing a description or body, repeat representative failures in another clean session; do not reuse a corrected conversation.

Use a small results table containing case ID, host/version, loaded skills, loaded references, behavior result, failure class, and notes. Treat unavailable trace data as a limitation rather than inferring what loaded.

## Minimum cross-host release sample

Run at least the interactive adversarial case, direct implementation case, trivial edit case, mixed-state review case, and Zellij reference case on both Codex and Claude. If a host is unavailable, record that limitation explicitly rather than predicting parity.
