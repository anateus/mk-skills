const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.join(__dirname, '..', '..');
const runner = path.join(root, 'hooks', 'artifact-discipline.js');
const skillRoot = path.join(root, 'skills', 'subagent-artifact-discipline');
const config = require(path.join(skillRoot, 'config', 'artifact-discipline.json'));
const { artifactLocation } = require(path.join(skillRoot, 'lib', 'artifact-discipline'));
const temporaryRoots = [];

function tempDir() {
  const created = fs.mkdtempSync(path.join(os.tmpdir(), 'mk-artifact-test-'));
  temporaryRoots.push(created);
  return created;
}

test.after(() => {
  for (const target of temporaryRoots) fs.rmSync(target, { recursive: true, force: true });
});

function event(name, overrides = {}) {
  return {
    hook_event_name: name,
    session_id: 'session-123',
    agent_id: 'agent-456',
    agent_type: 'general-purpose',
    cwd: '/tmp/project',
    ...overrides,
  };
}

function runHook(input, artifactRoot, extraEnv = {}) {
  const env = {
    PATH: process.env.PATH,
    PLUGIN_ROOT: root,
    MK_SKILLS_ARTIFACT_DIR: artifactRoot,
    ...extraEnv,
  };
  const result = spawnSync(process.execPath, [runner], {
    cwd: '/tmp',
    env,
    input: typeof input === 'string' ? input : JSON.stringify(input),
    encoding: 'utf8',
    timeout: 3000,
  });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  return { ...result, output: JSON.parse(result.stdout) };
}

function expectedArtifact(artifactRoot, overrides = {}) {
  const value = event('SubagentStart', overrides);
  return path.join(artifactRoot, value.session_id, value.agent_id, config.artifactFilename);
}

test('SubagentStart injects one shared host envelope and creates only the parent directory', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts-$&');
  const result = runHook(event('SubagentStart'), artifactRoot);
  const artifact = expectedArtifact(artifactRoot);

  assert.deepEqual(Object.keys(result.output), ['hookSpecificOutput']);
  assert.equal(result.output.hookSpecificOutput.hookEventName, 'SubagentStart');
  assert.match(result.output.hookSpecificOutput.additionalContext, new RegExp(artifact.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(result.output.hookSpecificOutput.additionalContext, /writing tool/i);
  assert.match(result.output.hookSpecificOutput.additionalContext, /final response/i);
  assert.equal(fs.statSync(path.dirname(artifact)).isDirectory(), true);
  assert.equal(fs.existsSync(artifact), false);
});

test('artifact paths are stable per lifecycle and distinct between agents', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  const first = runHook(event('SubagentStart'), artifactRoot).output;
  const again = runHook(event('SubagentStart'), artifactRoot).output;
  const second = runHook(event('SubagentStart', { agent_id: 'agent-789' }), artifactRoot).output;

  assert.equal(first.hookSpecificOutput.additionalContext, again.hookSpecificOutput.additionalContext);
  assert.notEqual(first.hookSpecificOutput.additionalContext, second.hookSpecificOutput.additionalContext);
  assert.equal(fs.existsSync(path.dirname(expectedArtifact(artifactRoot, { agent_id: 'agent-789' }))), true);
});

test('default root uses the configured subdirectory under the host temp directory', () => {
  const location = artifactLocation(event('SubagentStart'), {
    config,
    env: {},
    tmpdir: '/host-temp',
  });
  assert.equal(location.artifactPath, path.join(
    '/host-temp',
    ...config.defaultSubdirectory,
    'session-123',
    'agent-456',
    config.artifactFilename,
  ));
});

test('filesystem root cannot be selected as the artifact root', () => {
  assert.throws(() => artifactLocation(event('SubagentStart'), {
    config,
    env: { MK_SKILLS_ARTIFACT_DIR: path.parse(process.cwd()).root },
  }), /artifact root/i);
});

test('relative roots, unsafe identifiers, malformed input, and unsupported events fail open', () => {
  const scratch = tempDir();
  const cases = [
    runHook(event('SubagentStart'), 'relative/path'),
    runHook(event('SubagentStart', { agent_id: '../escape' }), path.join(scratch, 'artifacts')),
    runHook('{broken', path.join(scratch, 'artifacts')),
    runHook(event('SessionStart'), path.join(scratch, 'artifacts')),
  ];

  for (const result of cases) assert.equal(Object.hasOwn(result.output, 'decision'), false);
  assert.equal(fs.existsSync(path.join(scratch, 'escape')), false);
});

test('opt-out disables start and stop without touching the artifact root', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  const env = { MK_SKILLS_ARTIFACT_DISCIPLINE: 'off' };
  assert.deepEqual(runHook(event('SubagentStart'), artifactRoot, env).output, {});
  assert.deepEqual(runHook(event('SubagentStop', {
    stop_hook_active: false,
    last_assistant_message: 'findings',
  }), artifactRoot, env).output, {});
  assert.equal(fs.existsSync(artifactRoot), false);
});

test('oversized hook input fails open without touching the artifact root', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  const input = `${JSON.stringify(event('SubagentStart'))}${'x'.repeat(config.maxInputBytes)}`;
  const result = runHook(input, artifactRoot);
  assert.equal(Object.hasOwn(result.output, 'decision'), false);
  assert.match(result.output.systemMessage, /byte limit/i);
  assert.equal(fs.existsSync(artifactRoot), false);
});

test('SubagentStop preserves an existing non-empty regular artifact', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  runHook(event('SubagentStart'), artifactRoot);
  const artifact = expectedArtifact(artifactRoot);
  fs.writeFileSync(artifact, 'agent-authored findings');

  const result = runHook(event('SubagentStop', {
    stop_hook_active: false,
    last_assistant_message: 'fallback must not replace this',
  }), artifactRoot);
  assert.deepEqual(result.output, {});
  assert.equal(fs.readFileSync(artifact, 'utf8'), 'agent-authored findings');
});

test('SubagentStop atomically stores the final response when artifact is missing or empty', () => {
  for (const initial of [null, '']) {
    const artifactRoot = path.join(tempDir(), 'artifacts');
    runHook(event('SubagentStart'), artifactRoot);
    const artifact = expectedArtifact(artifactRoot);
    if (initial !== null) fs.writeFileSync(artifact, initial);

    const result = runHook(event('SubagentStop', {
      stop_hook_active: false,
      last_assistant_message: 'complete fallback findings',
      agent_transcript_path: '/dev/zero',
    }), artifactRoot);
    assert.deepEqual(result.output, {});
    assert.equal(fs.readFileSync(artifact, 'utf8'), 'complete fallback findings');
    assert.deepEqual(fs.readdirSync(path.dirname(artifact)), [config.artifactFilename]);
  }
});

test('fallback truncates on a UTF-8 boundary and records truncation', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  const markerBytes = Buffer.byteLength('\n\n[truncated by artifact discipline]\n');
  const message = `${'a'.repeat(config.maxFallbackBytes - markerBytes - 1)}${'🙂'.repeat(20)}`;
  const result = runHook(event('SubagentStop', {
    stop_hook_active: false,
    last_assistant_message: message,
  }), artifactRoot);
  const artifact = expectedArtifact(artifactRoot);
  const stored = fs.readFileSync(artifact);

  assert.deepEqual(result.output, {});
  assert.ok(stored.byteLength <= config.maxFallbackBytes);
  assert.doesNotThrow(() => new TextDecoder('utf-8', { fatal: true }).decode(stored));
  assert.match(stored.toString('utf8'), /truncated by artifact discipline/);
});

test('empty first response blocks once and names the exact artifact path', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  const result = runHook(event('SubagentStop', {
    stop_hook_active: false,
    last_assistant_message: '  ',
  }), artifactRoot);

  assert.equal(result.output.decision, 'block');
  assert.match(result.output.reason, new RegExp(expectedArtifact(artifactRoot).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('active stop never blocks and records a diagnostic placeholder', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  const result = runHook(event('SubagentStop', {
    stop_hook_active: true,
    last_assistant_message: null,
  }), artifactRoot);
  const artifact = expectedArtifact(artifactRoot);

  assert.equal(Object.hasOwn(result.output, 'decision'), false);
  assert.match(fs.readFileSync(artifact, 'utf8'), /no artifact or final response/i);
});

test('unexpected artifact types and storage failures allow the stop', () => {
  const artifactRoot = path.join(tempDir(), 'artifacts');
  runHook(event('SubagentStart'), artifactRoot);
  const artifact = expectedArtifact(artifactRoot);
  fs.mkdirSync(artifact);
  const unexpected = runHook(event('SubagentStop', {
    stop_hook_active: false,
    last_assistant_message: 'do not overwrite a directory',
  }), artifactRoot);
  assert.equal(Object.hasOwn(unexpected.output, 'decision'), false);
  assert.match(unexpected.output.systemMessage, /artifact/i);

  const impossibleRoot = path.join(tempDir(), 'plain-file');
  fs.writeFileSync(impossibleRoot, 'x');
  const failed = runHook(event('SubagentStop', {
    stop_hook_active: false,
    last_assistant_message: 'cannot persist here',
  }), impossibleRoot);
  assert.equal(Object.hasOwn(failed.output, 'decision'), false);
  assert.match(failed.output.systemMessage, /artifact/i);
});
