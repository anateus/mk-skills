# Skill activation forward tests

Static checks validate packaging, references, budgets, and executable helpers. Wording snapshots cannot establish agent behavior. Run forward evaluations after changing activation or process instructions.

## Run the catalog harness

```bash
python3 scripts/evaluate-skills.py --list
python3 scripts/evaluate-skills.py --host codex --case humanizer-preserves-claims --output /tmp/skills-candidate-codex
python3 scripts/evaluate-skills.py --host claude --case humanizer-preserves-claims --output /tmp/skills-candidate-claude
python3 scripts/evaluate-skills.py --source /path/to/baseline-checkout --host codex --case humanizer-preserves-claims --output /tmp/skills-baseline-codex
```

Repeat `--case` to select cases; `--profile strict` tests strict injection. Use `--model` to pin the model and `--repetitions` for fresh runs of each case. Output must be a new directory. The runner snapshots skills, shared guidance, policy, case definitions, workspace inputs, candidate instructions, execution options, and its own code before starting a host. It hashes the snapshot, creates a fresh Git workspace for every run, passes only the raw fixture prompt as the user message, and records the exact context and command, traces, elapsed time, host version, requested model, before/after file hashes, changed files, and pending grading. Rubrics stay outside the agent workspace and are copied into each run's assessment directory after the host exits. A timeout terminates only that run's process group. Exit 0 reports successful processes, not passing behavior.

This is an explicit-catalog harness. Both hosts receive the shipped shared guidance, selected profile, and available-skill descriptions and paths, then choose what to read. Claude uses safe mode; Codex disables known installed skill paths, user configuration, project guidance, hooks, plugins, and apps for that invocation. Authentication and administrator policy remain host-owned. Neither adapter changes installed configuration. Fixture-local stubs keep ordinary Zellij and AgentPlan commands from reaching real coordination state. Inspect traces for contamination; the harness does not establish native plugin discovery or sandbox isolation. Keep fixtures synthetic and local.

Fifteen cases have workspace fixtures in `tests/fixtures/evaluation-workspaces.json`. Others require a suitable `--fixtures` file keyed by case ID. Each entry supports `commits` (ordered file-content maps), `staged`, `unstaged`, and `untracked`. Provide real scenario inputs rather than asking an agent to imagine missing code. The Zellij case exercises reference routing and reports the unavailable server; it never spawns a real pane. To test another host, `--host custom --command-json adapter.json` accepts an argv array with `{workspace}` and `{context}` placeholders and sends the raw prompt on stdin.

Six additional evidence cases live in `tests/fixtures/evidence/`. They distinguish unsupported assertions from useful conditional reasoning, exact calculations, creative designs, and faithful prose. Their rubrics grade factual support and progress toward the requested decision separately. Candidate guidance is experimental and does not change installed skills:

```bash
python3 scripts/evaluate-skills.py --host claude --model claude-fable-5-1 \
  --cases tests/fixtures/evidence/cases.json \
  --fixtures tests/fixtures/evidence/workspaces.json \
  --case queue-unknown --case compute-threshold --repetitions 2 \
  --instructions tests/fixtures/evidence/rule.md \
  --instructions tests/fixtures/evidence/audit.md \
  --output /tmp/evidence-rule-audit
```

Omit `--instructions` for current guidance. Use `rule.md` alone for the compact evidence rule; add `audit.md` for a claim check or `scaffold.md` for conditional method selection inspired by Pearl. Multiple instruction files are combined in the supplied order and frozen before the first run. The scaffold requires no Pearl package, service, plugin, or CLI. Repeated runs use `<case>/repeat-001/` directories; a single repetition keeps the original `<case>/` layout. Keep model, profile, cases, and runtime settings fixed across conditions, retain failed runs, and inspect the actual model identifier in host traces where available.

To evaluate an installed plugin, pass `--plugin /path/to/plugin-root`. The runner snapshots its files, adds namespaced skill descriptions to the explicit catalog, and preserves relative paths to scripts and references. It does not install the plugin, enable native hooks or apps, or install its dependencies. Required CLIs must already be available. Keep databases and other task artifacts inside the disposable workspace, and inspect actual CLI results before attributing a result to tool use. Run the same cases without `--plugin` for a matched control. The optional Pearl inputs are `pearl-cases.json`, `pearl-workspaces.json`, and `pearl-record.md` in `tests/fixtures/evidence/`; combine their cases and workspaces with the main evidence fixtures when comparing both sets.

Grade the response and actual artifacts against the withheld rubric. Record false activations, unnecessary questions, reference reads, semantic preservation, elapsed time, and token usage when the trace exposes it. Read commands and their results before counting a reference as loaded; a path merely mentioned in an answer is insufficient. Missing traces leave activation unknown. Repeat variable or failed cases in fresh sessions. Compare the same inputs, host, profile, and model before generalizing instruction removal results.

Give graders relevant tool receipts before asking them to judge completed actions. Compute mechanical quantities such as word counts directly. Include planted failures and valid conditional answers to check the grader, score support separately from usefulness, and preserve original grades alongside review corrections. The [evidence discipline study](../reviews/2026-09-10-evidence-discipline-results.md) records why these checks matter.

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
