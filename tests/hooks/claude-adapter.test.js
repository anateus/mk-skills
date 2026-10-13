const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
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

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), 'utf8'));
}

function runDeclaredCommand(command, rootVariable, payload, extraEnv = {}) {
  const pluginRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'mk skills plugin '));
  try {
    for (const directory of ['hooks', 'lib', 'config', 'skills/subagent-artifact-discipline']) {
      fs.cpSync(path.join(root, directory), path.join(pluginRoot, directory), { recursive: true });
    }
    const env = { PATH: process.env.PATH, ...extraEnv };
    env[rootVariable] = pluginRoot;
    const result = spawnSync(command, {
      cwd: os.tmpdir(), env, input: payload, encoding: 'utf8', shell: true,
      timeout: 3000,
    });
    assert.equal(result.error, undefined);
    assert.equal(result.status, 0, result.stderr);
    return result.stdout;
  } finally {
    fs.rmSync(pluginRoot, { recursive: true, force: true });
  }
}

test('Claude marketplace package metadata and default hook discovery are valid', () => {
  const plugin = readJson('.claude-plugin/plugin.json');
  const marketplace = readJson('.claude-plugin/marketplace.json');
  assert.equal(plugin.name, 'mk-skills');
  assert.equal(plugin.version, readJson('.codex-plugin/plugin.json').version);
  assert.equal(plugin.author.name, 'Michael Katsevman');
  assert.equal(plugin.repository, 'https://github.com/anateus/mk-skills');
  assert.equal(plugin.license, 'MIT');
  assert.equal(Object.hasOwn(plugin, 'interface'), false);
  assert.equal(marketplace.name, 'mk-skills');
  assert.deepEqual(marketplace.owner, { name: 'Michael Katsevman' });
  assert.deepEqual(marketplace.plugins.map(({ name, source }) => ({ name, source })), [
    { name: 'mk-skills', source: './' },
  ]);
  assert.equal(Object.hasOwn(plugin, 'hooks'), false);
  assert.equal(Object.hasOwn(plugin, 'skills'), false);

  const defaults = readJson('hooks/hooks.json');
  const adapter = readJson('adapters/claude/hooks.json');
  assert.deepEqual(defaults, adapter);
  assert.equal(defaults.hooks.SessionStart[0].hooks[0].command,
    'node "${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/hooks/run-hook.js"');
  for (const event of ['SubagentStart', 'SubagentStop']) {
    assert.equal(defaults.hooks[event][0].hooks[0].command,
      'node "${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/hooks/artifact-discipline.js"');
  }
});

test('declared default hook commands run with either root variable and paths containing spaces', () => {
  const declaration = readJson('hooks/hooks.json');
  const runCommand = declaration.hooks.SessionStart[0].hooks[0].command;
  const artifactStartCommand = declaration.hooks.SubagentStart[0].hooks[0].command;
  const artifactStopCommand = declaration.hooks.SubagentStop[0].hooks[0].command;
  const payload = fixture('claude-session-start.json');
  for (const [variable] of [
    ['CLAUDE_PLUGIN_ROOT', 'PLUGIN_ROOT'],
    ['PLUGIN_ROOT', 'CLAUDE_PLUGIN_ROOT'],
  ]) {
    const output = runDeclaredCommand(runCommand, variable, payload);
    assert.equal(contextOf(JSON.parse(output)), contextOf(runHost('claude', payload)));
    const artifactRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'mk skills artifacts '));
    try {
      const event = {
        hook_event_name: 'SubagentStart',
        session_id: 'package-test-session',
        agent_id: 'package-test-agent',
        agent_type: 'general-purpose',
        cwd: root,
      };
      const artifactOutput = JSON.parse(runDeclaredCommand(
        artifactStartCommand, variable, JSON.stringify(event), { MK_SKILLS_ARTIFACT_DIR: artifactRoot },
      ));
      assert.equal(artifactOutput.hookSpecificOutput.hookEventName, 'SubagentStart');
      assert.match(artifactOutput.hookSpecificOutput.additionalContext, /writing tool/i);
      const stopOutput = runDeclaredCommand(artifactStopCommand, variable, JSON.stringify({
        ...event,
        hook_event_name: 'SubagentStop',
        last_assistant_message: 'package test artifact content',
      }), { MK_SKILLS_ARTIFACT_DIR: artifactRoot });
      assert.deepEqual(JSON.parse(stopOutput), {});
      const files = fs.readdirSync(path.join(artifactRoot, event.session_id, event.agent_id));
      assert.equal(files.length, 1);
      assert.match(fs.readFileSync(path.join(artifactRoot, event.session_id, event.agent_id, files[0]), 'utf8'),
        /package test artifact content/);
    } finally {
      fs.rmSync(artifactRoot, { recursive: true, force: true });
    }
  }
});

test('Claude declaration invokes the shared runner for supported session sources', () => {
  const declaration = JSON.parse(fs.readFileSync(
    path.join(root, 'adapters', 'claude', 'hooks.json'),
  ));
  const groups = declaration.hooks.SessionStart;
  assert.equal(groups.length, 1);
  assert.equal(groups[0].matcher, 'startup|resume|clear|compact');
  assert.deepEqual(groups[0].hooks, [{
    type: 'command',
    command: 'node "${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/hooks/run-hook.js"',
    timeout: 10,
  }]);
});

test('Codex and Claude register identical subagent lifecycle handlers', () => {
  const codex = readJson('hooks/hooks.json');
  const claude = readJson('adapters/claude/hooks.json');
  for (const eventName of ['SubagentStart', 'SubagentStop']) {
    assert.equal(codex.hooks[eventName].length, 1);
    assert.equal(claude.hooks[eventName].length, 1);
    assert.equal(Object.hasOwn(codex.hooks[eventName][0], 'matcher'), false);
    assert.equal(Object.hasOwn(claude.hooks[eventName][0], 'matcher'), false);
    assert.deepEqual(codex.hooks[eventName][0].hooks, [{
      type: 'command',
      command: 'node "${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/hooks/artifact-discipline.js"',
      timeout: 10,
    }]);
    assert.deepEqual(claude.hooks[eventName][0].hooks, codex.hooks[eventName][0].hooks);
  }
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
    ['strict', /Read and apply the `strict-mode` skill/i],
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
    'test-pane-identity.py', 'test-hunk-placement.py', 'test-hunk-stream.sh', 'test-hunk-lifecycle.py',
    'test-install-hooks.sh', 'test-shared-agent-config.sh',
  ].map((name) => source.indexOf(name));
  const artifactInstaller = source.indexOf('skills/subagent-artifact-discipline/tests/test-install-hooks.sh');
  const plugin = source.indexOf('PLUGIN_VALIDATOR');
  const native = source.indexOf("['plugin', 'validate', '.', '--strict']");
  const explicitManifest = source.indexOf("['plugin', 'validate', '.claude-plugin/plugin.json', '--strict']");
  const diff = source.indexOf("'git', ['diff', '--check']");
  assert.ok(hooks >= 0 && skills >= hooks);
  assert.ok(curation > skills);
  assert.ok(zellijCommands.every((position) => position > curation));
  assert.ok(artifactInstaller > curation);
  assert.ok(zellijCommands.every((position) => position < plugin));
  assert.ok(plugin > curation);
  assert.ok(native > plugin && explicitManifest > native && diff > explicitManifest);
  assert.match(source, /CLAUDE_CLI/);
  assert.match(source, /Claude CLI absent.*skip|skip.*Claude CLI absent/is);
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
    /subagent-artifact-discipline\/scripts\/install-hooks\.sh/,
    /pnpx skills update -g/,
    /node scripts\/validate\.js/,
  ]) assert.match(readme, requirement);
});
