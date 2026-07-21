# Skill activation forward tests

Static contract tests prove that descriptions, routes, and references are well formed. They do not prove that a host will activate the right skill in a clean session. Run this evaluation before release and after activation-sensitive changes.

## Prepare the exact build

1. Run `node scripts/validate.js` in the branch under test.
2. Install or link that exact checkout for both available hosts. Record the branch, commit or working-tree identity, host versions, profile, and date.
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
