const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..', '..');
const runner = path.join(root, 'hooks', 'run-hook.js');
const fixture = (name) => fs.readFileSync(
  path.join(root, 'tests', 'fixtures', 'hooks', name),
  'utf8',
);

function runHost(host, input, override) {
  const env = { PATH: process.env.PATH };
  env[host === 'codex' ? 'PLUGIN_ROOT' : 'CLAUDE_PLUGIN_ROOT'] = root;
  if (override !== undefined) env.MK_SKILLS_MODE = override;
  const result = spawnSync(process.execPath, [runner], {
    cwd: '/tmp', env, input, encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function contextOf(output) {
  assert.deepEqual(Object.keys(output).sort(), ['hookSpecificOutput']);
  assert.deepEqual(Object.keys(output.hookSpecificOutput).sort(), [
    'additionalContext', 'hookEventName',
  ]);
  assert.equal(output.hookSpecificOutput.hookEventName, 'SessionStart');
  return output.hookSpecificOutput.additionalContext;
}

function countContextFields(value) {
  if (!value || typeof value !== 'object') return 0;
  return Object.entries(value).reduce(
    (count, [key, child]) => count
      + (key === 'additionalContext' ? 1 : countContextFields(child)),
    0,
  );
}

test('Claude declaration invokes the shared runner for supported session sources', () => {
  const declaration = JSON.parse(fs.readFileSync(
    path.join(root, 'adapters', 'claude', 'hooks.json'),
  ));
  const groups = declaration.hooks.SessionStart;
  assert.equal(groups.length, 1);
  assert.equal(groups[0].matcher, 'startup|resume|clear|compact');
  assert.deepEqual(groups[0].hooks, [{
    type: 'command',
    command: 'node "${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.js"',
    timeout: 10,
  }]);
});

test('Codex and Claude emit host-correct envelopes with identical policy context', () => {
  const codexInput = fixture('codex-session-start.json');
  const claudeInput = fixture('claude-session-start.json');
  for (const mode of ['strict', 'selective', 'off']) {
    const codex = runHost('codex', codexInput, mode);
    const claude = runHost('claude', claudeInput, mode);
    assert.equal(contextOf(claude), contextOf(codex));
    if (mode === 'strict') assert.match(contextOf(codex), /strict operating profile is active.*`strict-mode`/i);
    assert.equal(countContextFields(claude), 1);
  }
});

test('Codex and Claude make the same default decision for an unknown model', () => {
  const codex = runHost('codex', fixture('unknown-model.json'));
  const claudeEvent = JSON.parse(fixture('claude-session-start.json'));
  claudeEvent.model = JSON.parse(fixture('unknown-model.json')).model;
  const claude = runHost('claude', JSON.stringify(claudeEvent));
  assert.equal(contextOf(claude), contextOf(codex));
  assert.match(contextOf(claude), /trigger clearly matches/i);
});

test('Claude accepts a missing optional model and preserves explicit overrides', () => {
  const event = JSON.parse(fixture('claude-session-start.json'));
  delete event.model;
  for (const [mode, expected] of [
    ['strict', /steps in order/i],
    ['selective', /trigger clearly matches/i],
    ['off', /^$/],
  ]) {
    const output = runHost('claude', JSON.stringify(event), mode);
    assert.match(contextOf(output), expected);
    assert.equal(Object.hasOwn(output, 'systemMessage'), false);
  }
});

test('unified validator runs repository checks and supports optional plugin validation', () => {
  const source = fs.readFileSync(path.join(root, 'scripts', 'validate.js'), 'utf8');
  const hooks = source.indexOf('tests/hooks/*.test.js');
  const skills = source.indexOf('tests/skills/*.test.js');
  const curation = source.indexOf('tests.curation.test_review_upstreams');
  const zellijCommands = [
    'test-pane-identity.py', 'test-hunk-focus-guard.py', 'test-hunk-stream.sh',
    'test-install-hooks.sh', 'test-shared-agent-config.sh',
  ].map((name) => source.indexOf(name));
  const plugin = source.indexOf('PLUGIN_VALIDATOR');
  const diff = source.indexOf("'git', ['diff', '--check']");
  assert.ok(hooks >= 0 && skills >= hooks);
  assert.ok(curation > skills);
  assert.ok(zellijCommands.every((position) => position > curation));
  assert.ok(zellijCommands.every((position) => position < plugin));
  assert.ok(plugin > curation);
  assert.ok(diff > plugin);
  assert.match(source, /skip.*plugin-schema|plugin-schema.*skip/is);
  assert.match(source, /import yaml/);
  assert.match(source, /\['-B', '-m', 'unittest'/);
  assert.match(source, /validator file absent/i);
  assert.match(source, /PyYAML unavailable/i);
});

test('README documents every Task 9 operating and installation contract', () => {
  const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
  for (const requirement of [
    /selective invocation/i,
    /Codex plugin/i,
    /review.*hook|hook.*review/is,
    /MK_SKILLS_MODE=strict\|selective\|off/,
    /low.reasoning.*strict|strict.*low.reasoning/is,
    /Claude.*adapter|adapter.*Claude/is,
    /offline/i,
    /upstream.*curat|curat.*upstream/is,
    /bidirectional.*independent|independent.*both directions/is,
    /zellij-agent-herder/i,
    /node scripts\/validate\.js/,
  ]) assert.match(readme, requirement);
});
