import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const adapter = resolve(root, 'python/adapter.py');
const fixtureRoot = resolve(root, 'fixtures/python');
const files = ['app.py', 'client.py', 'models.py', 'routes.py', 'session.py'];
function scan(overrides = {}) {
  const request = { protocolVersion: 1, repository: { id: 'synthetic-python', root: fixtureRoot, revision: 'test' }, files, ...overrides };
  const result = spawnSync('python3', [adapter], { input: JSON.stringify(request), encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

test('Python parses source without importing side effects and tracks required versus nullable', () => {
  const result = scan();
  assert.equal(result.files.length, files.length);
  assert.ok(result.files.every(file => file.status === 'examined'));
  const model = result.schemas.find(schema => schema.name === 'StartRequest');
  assert.ok(model.schema.required.includes('required_nullable'));
  assert.ok(!model.schema.required.includes('optional_nullable'));
  assert.deepEqual(model.schema.properties.required_nullable.anyOf, [{ type: 'string' }, { type: 'null' }]);
  assert.equal(model.schema.properties.call_id['x-python-alias'], 'callId');
  assert.equal(model.schema.properties.retries.minimum, 0);
  assert.ok(model.gaps.includes('custom-model_validator-not-exported'));
  assert.ok(model.gaps.includes('unresolved-or-unsupported-annotation'));
  const headers = result.schemas.find(schema => schema.name === 'Headers');
  assert.deepEqual(headers.schema.required, ['correlation_id']);
  assert.equal(result.declarations.find(item => item.name === 'UnsupportedContainer').status, 'unsupported');
  assert.equal(result.declarations.find(item => item.name === 'UnsupportedAlias').status, 'unsupported');
});

test('Python links cross-file FastAPI mounts and keeps unresolved/unmounted declarations explicit', () => {
  const result = scan();
  const operation = result.operations.find(item => item.name === 'start');
  assert.equal(operation.path, '/v1/calls/start');
  assert.equal(operation.mounted, true);
  assert.equal(operation.responses[0].status, '202');
  assert.ok(operation.requestSchemaId);
  assert.ok(operation.gaps.includes('response-serialization-or-route-options-not-exported'));
  assert.equal(result.operations.find(item => item.name === 'unused').mounted, false);
  const dynamic = result.operations.find(item => item.name === 'dynamic');
  assert.equal(dynamic.path, undefined);
  assert.ok(dynamic.gaps.includes('dynamic-route-path-or-prefix'));
  assert.ok(result.diagnostics.some(item => item.code === 'unresolved-router-registration'));
  const conditional = result.operations.find(item => item.name === 'conditional_candidate');
  assert.equal(conditional.mounted, undefined);
  assert.ok(conditional.gaps.includes('conditional-registration-not-evaluated'));
  const dual = result.operations.filter(item => item.name === 'dual');
  assert.equal(dual.length, 2);
  assert.notEqual(dual[0].responses[0].schemaId, dual[1].responses[0].schemaId);
  const schema = id => result.schemas.find(item => item.id === id).schema;
  assert.notEqual(schema(dual[0].responses[0].schemaId).$ref, schema(dual[1].responses[0].schemaId).$ref);
});

test('Python follows shared aiohttp factories, records serialization gaps, excludes credentials', () => {
  const result = scan();
  const outbound = result.operations.filter(item => item.direction === 'outbound');
  assert.equal(outbound.length, 3);
  const send = outbound.find(item => item.name === 'send');
  assert.equal(send.method, 'POST');
  assert.equal(send.path, undefined);
  assert.ok(send.gaps.includes('dynamic-url-unresolved'));
  assert.deepEqual(send.responses, []);
  assert.deepEqual(send.details.nearbySerialization[0].options, { by_alias: true, exclude_none: true });
  const direct = outbound.find(item => item.name === 'direct');
  assert.equal(direct.server, 'https://example.invalid');
  assert.equal(direct.path, '/widgets');
  assert.ok(!JSON.stringify(result).includes('SYNTHETIC_'));
});

test('Python emits deterministic unique IDs and resolvable schema references', () => {
  const result = scan();
  assert.deepEqual(result, scan({ files: files.toReversed ? files.toReversed() : [...files].reverse() }));
  const records = [...result.declarations, ...result.schemas, ...result.operations];
  assert.equal(new Set(records.map(item => item.id)).size, records.length);
  const ids = new Set(result.schemas.map(item => item.id));
  function check(value) {
    if (value && typeof value === 'object') {
      if (value.$ref) assert.ok(ids.has(value.$ref), value.$ref);
      for (const child of Object.values(value)) check(child);
    }
  }
  check(result);
  for (const record of records) for (const evidence of record.evidence) assert.ok(files.includes(evidence.file));
});

test('Python fails closed on protocol errors and reports individual unreadable/invalid files', () => {
  const invalid = spawnSync('python3', [adapter], { input: '{}', encoding: 'utf8' });
  assert.notEqual(invalid.status, 0);
  assert.equal(invalid.stdout, '');
  const dir = mkdtempSync(resolve(tmpdir(), 'contract-python-test-'));
  try {
    writeFileSync(resolve(dir, 'broken.py'), 'class invalid syntax secret:\n');
    writeFileSync(resolve(dir, 'notes.txt'), 'unsupported');
    const result = scan({ repository: { id: 'test', root: dir, revision: 'test' }, files: ['broken.py', 'notes.txt', '../escape.py', 'missing.py'] });
    assert.deepEqual(result.files.map(item => [item.path, item.status]), [['../escape.py', 'failed'], ['broken.py', 'failed'], ['missing.py', 'failed'], ['notes.txt', 'unsupported']]);
    assert.ok(!JSON.stringify(result).includes('invalid syntax secret'));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
