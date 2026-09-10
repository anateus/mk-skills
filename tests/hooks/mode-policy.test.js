const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  loadPolicy,
  selectMode,
  renderContext,
} = require('../../lib/mode-policy');

const fixture = (name) => path.join(__dirname, '..', 'fixtures', 'policies', name);

test('explicit valid overrides win over model rules', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  for (const mode of ['strict', 'selective', 'off']) {
    const result = selectMode({ model: 'gpt-mini', override: mode, policy });
    assert.equal(result.mode, mode);
    assert.equal(result.reason, 'override');
  }
});

test('smaller model rule selects strict', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  assert.equal(selectMode({ model: 'gpt-mini', policy }).mode, 'strict');
});

test('shipped policy selects strict for conservative small and older model families', () => {
  const { policy } = loadPolicy(path.join(__dirname, '..', '..', 'config', 'mode-policy.json'));
  for (const model of [
    'gpt-5-mini', 'gpt-4.1-nano', 'o4-mini', 'claude-3-5-haiku', 'gpt-3.5-turbo',
  ]) {
    assert.equal(selectMode({ model, policy }).mode, 'strict', model);
  }
  for (const model of ['gpt-5.6-codex', 'claude-opus-4-1']) {
    assert.equal(selectMode({ model, policy }).mode, 'selective', model);
  }
});

test('capable model rule selects selective', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  assert.equal(selectMode({ model: 'gpt-5.6', policy }).mode, 'selective');
});

test('unknown model selects configured default', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  const result = selectMode({ model: 'future-model', policy });
  assert.equal(result.mode, 'selective');
  assert.equal(result.reason, 'default');
});

test('invalid override fails open with one diagnostic', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  const result = selectMode({ model: 'gpt-mini', override: 'maximum', policy });
  assert.equal(result.mode, 'selective');
  assert.equal(result.diagnostics.length, 1);
});

test('missing and malformed policies use the built-in fallback', () => {
  for (const target of [
    fixture('missing.json'),
    fixture('malformed.json'),
    fixture('invalid-rules.json'),
  ]) {
    const result = loadPolicy(target);
    assert.equal(result.policy.defaultMode, 'selective');
    assert.ok(result.diagnostics.length > 0);
    assert.match(renderContext({ mode: 'selective', policy: result.policy }), /clear/i);
  }
});

test('off renders no context', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  assert.equal(renderContext({ mode: 'off', policy }), '');
});

test('strict context routes to the installed policy skill without duplicating its body', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  const context = renderContext({ mode: 'strict', policy });
  const words = context.trim().split(/\s+/).length;
  assert.ok(words > 0 && words <= 40, `strict context has ${words} words`);
  assert.match(context, /^The strict operating profile is active\. Read and apply the `strict-mode` skill before acting\./);
  assert.equal(context, policy.contexts.strict);
});

test('selective context stays below 100 words and uses clear triggers', () => {
  const { policy } = loadPolicy(fixture('valid.json'));
  const context = renderContext({ mode: 'selective', policy });
  assert.ok(context.trim().split(/\s+/).length < 100);
  assert.match(context, /trigger clearly matches/i);
});
