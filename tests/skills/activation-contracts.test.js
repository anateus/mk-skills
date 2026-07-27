const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { root, readSkill, skillDirectories, markdownReferences } = require('../helpers/skills');

const descriptions = {
  'clarifying-work': 'Reduce consequential uncertainty by inspecting facts, separating assumptions from decisions, and mapping integration risks. Use when a request is ambiguous, integration-heavy, cross-boundary, or likely to hide decisions that could cause substantial rework.',
  'adversarial-refinement': 'Stress-test and improve proposals, decisions, specifications, plans, architectures, and diagnoses using adversarial questions, counterexamples, alternative approaches, and tradeoff analysis. Use when the user asks to grill, challenge, red-team, stress-test, or poke holes in an idea, or when another workflow explicitly requests a pressure test before commitment.',
  'specifying-work': 'Turn agreed intent and repository evidence into a concise behavior contract with acceptance criteria, testing seams, constraints, and non-goals. Use when the user asks for a specification, design contract, requirements, or acceptance criteria before planning or implementation.',
  'planning-work': 'Create a codebase-grounded, executable implementation sequence using narrow vertical slices, dependencies, owned files, expected outputs, and verification. Use when the user asks for an implementation plan or when a reviewed request or specification has multi-step dependencies.',
  'test-driven-development': 'Implement observable behavior changes through narrow red-green cycles at public seams, with proportional alternatives when a test adds little value. Use when the user asks for test-first or TDD work, or when implementing a behavior change or defect fix that has a useful observable seam.',
  'diagnosing-bugs': 'Diagnose failures by reproducing, minimizing, and testing competing hypotheses before changing behavior. Use when behavior is failing, inconsistent, flaky, regressed, or unexplained and the cause is not established by evidence.',
  'investigating-incidents': 'Investigate live or historical production incidents across services, queues, databases, providers, and protocol boundaries using an evidence ledger, comparable cohorts, bounded parallel probes, and explicit correction history. Use when an outage, throughput collapse, provider regression, degraded metric, or cross-system failure needs cause-level diagnosis without repeated rediscovery or premature root-cause claims.',
  'implementing-work': 'Route and implement approved or sufficiently clear changes in an existing codebase as coherent, verified slices. Use when the user asks to add, build, change, fix, or implement behavior from a request, specification, plan, or review feedback.',
  'reviewing-code': 'Review a fixed code change or diff for correctness, risk, specification compliance, repository standards, and test adequacy. Use when the user asks to review, audit, or assess a diff, patch, pull request, commit range, or completed implementation before acceptance or release.',
  'handling-review-feedback': 'Evaluate review comments as technical claims, classify them, and apply accepted changes with verification. Use when review feedback, inline comments, or requested changes need assessment, implementation, or response.',
  'verifying-work': 'Map completion and readiness claims to fresh direct evidence, run the relevant checks, and report limitations precisely. Use when asked to verify, check, test, confirm, or prove that work is correct, complete, passing, buildable, or ready.',
  'handing-off-work': 'Create a concise, redacted, resumable transfer that references durable artifacts and distinguishes verified facts from remaining work. Use when work must move to another session, agent, or collaborator, whether unfinished or complete.',
  'strict-mode': 'Apply the active strict operating profile through explicit skill selection, ordered execution, checkpoints, and fresh verification without expanding authority. Use when injected context says strict mode is active or the user explicitly requests strict execution.',
  'curating-skills': 'Compare configured upstream skill changes against recorded revisions and local behavior, record accept or reject decisions, and update provenance only after validation. Use only when maintaining the mk-skills source repository and deliberately reviewing its configured upstream skill repositories.',
  'zellij-agent-herder': 'Control Zellij panes, sessions, peer agents, waits, and live Hunk review streams using the bundled helpers. Use when running inside Zellij (`ZELLIJ` is set, including `0`) and the task requires pane orchestration, peer coordination, status waiting, or live diff watching. Requires a recent Zellij build with `new-pane --no-focus` (zellij-org/zellij#5346).',
};

test('skill descriptions match approved capability and trigger contracts', () => {
  for (const [name, expected] of Object.entries(descriptions)) assert.equal(readSkill(name).fields.description, expected, name);
});
test('front-end workflows route conditionally to adversarial-refinement', () => {
  for (const name of ['clarifying-work', 'specifying-work', 'planning-work']) assert.match(readSkill(name).body, /`adversarial-refinement`/i, name);
});
test('implementation router names exact downstream skills selectively', () => {
  const body = readSkill('implementing-work').body;
  for (const name of ['clarifying-work', 'specifying-work', 'planning-work', 'adversarial-refinement', 'test-driven-development', 'diagnosing-bugs', 'verifying-work', 'reviewing-code']) assert.ok(body.includes(`\`${name}\``), name);
  assert.match(body, /smallest applicable set/i);
});
test('accepted feedback routes through diagnosis, TDD, and verification', () => {
  const body = readSkill('handling-review-feedback').body;
  for (const name of ['diagnosing-bugs', 'test-driven-development', 'verifying-work']) assert.ok(body.includes(`\`${name}\``), name);
});

test('activation fixtures use real skills and references with a stable schema', () => {
  const fixture = JSON.parse(fs.readFileSync(path.join(root, 'tests', 'fixtures', 'activation-cases.json'), 'utf8'));
  assert.ok(Array.isArray(fixture) && fixture.length >= 17);
  const ids = new Set();
  const skills = new Set(skillDirectories());
  const references = new Set([...skills].flatMap((name) => markdownReferences(name).map((file) => path.relative(root, file).split(path.sep).join('/'))));
  for (const item of fixture) {
    assert.deepEqual(Object.keys(item).sort(), ['expectedReferences', 'expectedSkills', 'forbiddenSkills', 'id', 'prompt', 'rubric']);
    assert.match(item.id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/); assert.equal(ids.has(item.id), false); ids.add(item.id);
    assert.ok(item.prompt.trim()); assert.ok(Array.isArray(item.rubric) && item.rubric.length && item.rubric.every(Boolean));
    for (const name of [...item.expectedSkills, ...item.forbiddenSkills]) assert.ok(skills.has(name), `${item.id}: ${name}`);
    for (const reference of item.expectedReferences) assert.ok(references.has(reference), `${item.id}: ${reference}`);
  }
});

module.exports = { descriptions };
