const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { loadPolicy, renderContext } = require('../../lib/mode-policy');

const root = path.join(__dirname, '..', '..');
const read = (...parts) => fs.readFileSync(path.join(root, ...parts), 'utf8');
const policy = loadPolicy(path.join(root, 'config', 'mode-policy.json')).policy;
const context = (mode) => renderContext({ mode, policy });
const scenario = (name) => read('tests', 'fixtures', 'scenarios', name);

test('selective profile scales down for a trivial edit', () => {
  const selective = context('selective');
  const trivial = scenario('trivial-edit.md');
  assert.match(trivial, /trivial|single/i);
  assert.match(selective, /trigger clearly matches/i);
  assert.doesNotMatch(selective, /(?:must|required to|always) (?:design|specif)/i);
});

test('strict profile sequences work without adding external side effects', () => {
  const strict = context('strict');
  assert.match(strict, /identify.*skills/is);
  assert.match(strict, /steps in order/i);
  assert.match(strict, /checkpoints/i);
  assert.match(strict, /fresh commands/i);
  for (const optional of [
    'commits', 'pull requests', 'issue trackers', 'worktrees', 'zellij', 'subagents',
  ]) assert.match(strict, new RegExp(`${optional}.*optional`, 'is'));
});

test('integration-heavy work routes through clarification and planning', () => {
  const strictMode = read('skills', 'strict-mode', 'SKILL.md');
  const integration = scenario('integration-change.md');
  assert.match(integration, /consumers/i);
  assert.match(integration, /failure modes/i);
  assert.match(integration, /dependencies/i);
  assert.match(strictMode, /clarifying-work/i);
  assert.match(strictMode, /planning-work/i);
  assert.match(strictMode, /integration/i);
});

test('peer-ready plan is executable inline or through optional zellij orchestration', () => {
  const plan = scenario('peer-ready-plan.md');
  for (const field of ['scope', 'dependencies', 'expected output', 'verification']) {
    assert.match(plan, new RegExp(field, 'i'));
  }
  assert.match(plan, /inline/i);
  assert.match(plan, /zellij-agent-herder/i);
  assert.match(plan, /optional/i);
  assert.match(plan, /independent/i);
});

test('strict mode and zellij remain independent but composable', () => {
  const strictMode = read('skills', 'strict-mode', 'SKILL.md');
  const strict = context('strict');
  for (const text of [strictMode, strict]) {
    assert.match(text, /zellij/i);
    assert.match(text, /optional/i);
    assert.doesNotMatch(text, /(?:must|required to|always) (?:use|run|invoke) (?:zellij|zellij-agent-herder)/i);
    assert.doesNotMatch(text, /(?:never|forbid|do not) (?:use|run|invoke) (?:zellij|zellij-agent-herder)/i);
  }
  assert.match(strictMode, /available.*requested.*independent/is);
  assert.match(strictMode, /otherwise.*sequential/is);
});

test('peer output is evidence to verify rather than completion proof', () => {
  for (const text of [
    context('strict'),
    read('skills', 'strict-mode', 'SKILL.md'),
    scenario('peer-ready-plan.md'),
  ]) {
    assert.match(text, /peer.*(?:evidence|report)/is);
    assert.match(text, /(?:primary|responsible).*verif|verify.*(?:primary|responsible)/is);
    assert.match(text, /not (?:proof|evidence).*completion|not.*completion proof/is);
  }
});
