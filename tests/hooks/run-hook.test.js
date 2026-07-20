const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..', '..');
const runner = path.join(root, 'hooks', 'run-hook.js');
const fixture = (name) => fs.readFileSync(
  path.join(__dirname, '..', 'fixtures', 'hooks', name),
  'utf8',
);

function runHook(input, override, extraEnv = {}) {
  const env = {
    PATH: process.env.PATH,
    PLUGIN_ROOT: root,
    ...extraEnv,
  };
  if (override !== undefined) env.MK_SKILLS_MODE = override;

  const result = spawnSync(process.execPath, [runner], {
    cwd: '/tmp',
    env,
    input,
    encoding: 'utf8',
  });
  const output = JSON.parse(result.stdout);
  return { ...result, output };
}

function contextOf(output) {
  assert.equal(output.hookSpecificOutput.hookEventName, 'SessionStart');
  return output.hookSpecificOutput.additionalContext;
}

test('startup with strict override returns strict context', () => {
  const result = runHook(fixture('codex-session-start.json'), 'strict');
  assert.equal(result.status, 0);
  assert.match(contextOf(result.output), /steps in order/i);
});

test('off override returns no injected context', () => {
  const result = runHook(fixture('codex-session-start.json'), 'off');
  assert.equal(result.status, 0);
  assert.equal(contextOf(result.output), '');
});

test('unknown model returns selective context', () => {
  const result = runHook(fixture('unknown-model.json'));
  assert.equal(result.status, 0);
  assert.match(contextOf(result.output), /trigger clearly matches/i);
});

test('malformed stdin exits zero with selective context and a concise diagnostic', () => {
  const result = runHook('{not json', 'strict');
  assert.equal(result.status, 0);
  assert.match(contextOf(result.output), /trigger clearly matches/i);
  assert.match(result.output.systemMessage, /malformed hook input/i);
  assert.ok(result.output.systemMessage.length < 160);
});

test('all session lifecycle sources use the same selector', () => {
  for (const source of ['startup', 'resume', 'clear', 'compact']) {
    const input = JSON.stringify({
      hook_event_name: 'SessionStart',
      source,
      model: 'gpt-5.6-codex',
      cwd: '/tmp/example-project',
    });
    assert.match(contextOf(runHook(input, 'strict').output), /steps in order/i);
  }
});

test('output is JSON and does not expose the absolute checkout path', () => {
  const result = runHook(fixture('codex-session-start.json'));
  assert.doesNotThrow(() => JSON.parse(result.stdout));
  assert.equal(result.stdout.includes(root), false);
});

test('plugin manifest and discovered hook declaration use the supported schemas', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, '.codex-plugin', 'plugin.json')));
  assert.equal(manifest.name, 'mk-skills');
  assert.equal(manifest.version, '0.1.0');
  assert.equal(manifest.skills, './skills/');
  assert.equal(Object.hasOwn(manifest, 'hooks'), false);
  assert.deepEqual(manifest.interface.defaultPrompt, [
    'Use the appropriate engineering skills for this task.',
  ]);

  const declaration = JSON.parse(fs.readFileSync(path.join(root, 'hooks', 'hooks.json')));
  const groups = declaration.hooks.SessionStart;
  assert.equal(groups.length, 1);
  assert.equal(groups[0].matcher, 'startup|resume|clear|compact');
  assert.deepEqual(groups[0].hooks, [{
    type: 'command',
    command: 'node "${PLUGIN_ROOT}/hooks/run-hook.js"',
    timeout: 10,
  }]);
});
