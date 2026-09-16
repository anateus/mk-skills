import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import Ajv2020 from 'ajv/dist/2020.js';
import { importNative } from '../dist/native.js';
import { validateResult } from '../dist/inventory.js';
import { buildBundle } from '../dist/export.js';

const pkg = fileURLToPath(new URL('../', import.meta.url));
const dialect = 'https://json-schema.org/draft/2020-12/schema';
function setup(t, files) {
  const root = fs.mkdtempSync(path.join(tmpdir(), 'contract-native-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.cpSync(path.join(pkg, 'fixtures/native'), root, { recursive: true });
  const request = { protocolVersion: 1, repository: { id: 'native', root, revision: 'synthetic' }, files };
  return { root, request, run: () => importNative(request) };
}
function validator(result) {
  const ajv = new Ajv2020({ strict: false, validateFormats: false, logger: false });
  for (const record of result.schemas.filter(r => r.schema)) ajv.addSchema({ ...record.schema, $schema: dialect, $id: record.id });
  for (const record of result.schemas.filter(r => r.schema)) assert.ok(ajv.getSchema(record.id), record.id);
  return ajv;
}
function inventory(request, result) {
  return { protocolVersion: 1, analysis: 'static', complete: false, repositories: [{ repository: request.repository, scope: { includes: [], excludedDirectories: [], defaultTestExclusions: true }, sourceFiles: request.files.map(path => ({ path, sha256: 'synthetic' })), configurationFiles: [], artifactFiles: request.files, excluded: [], results: [result] }], declarations: result.declarations, schemas: result.schemas, operations: result.operations, relationships: result.relationships, operationGroups: [] };
}

test('native JSON Schema retains recursion, validation constraints, origin and exact source pointer', t => {
  const { request, run } = setup(t, ['recursive.schema.json']);
  const result = run(); validateResult(result, request);
  assert.deepEqual(result.files, [{ path: 'recursive.schema.json', status: 'examined' }]);
  assert.deepEqual(result.declarations, []);
  const schema = result.schemas.find(s => s.origin.pointer === '');
  assert.equal(schema.origin.kind, 'native-json-schema');
  assert.equal(schema.evidence[0].pointer, '');
  const validate = validator(result).getSchema(schema.id);
  assert.equal(validate({ name: 'root', children: [{ name: 'child' }] }), true);
  assert.equal(validate({ name: 'root', children: [{ name: '' }] }), false);
  assert.equal(validate({ name: 'root', unexpected: true }), false);
  assert.equal(schema.schema.$defs.Disabled, false);
  assert.equal(schema.schema.$defs.Any, true);
  assert.deepEqual(run(), result, 'Unchanged artifacts produce deterministic results');
});

test('local external refs require explicit selection and preserve transitive closure', t => {
  const { root, request, run } = setup(t, ['external.schema.json']);
  let result = run();
  assert.equal(result.schemas[0].schema, undefined, 'Unselected sibling must not be read');
  assert.ok(result.diagnostics.some(d => d.code === 'unresolved-native-reference'));
  request.files.push('shared.schema.json');
  result = run();
  const schema = result.schemas.find(s => s.origin.file === 'external.schema.json');
  const validate = validator(result).getSchema(schema.id);
  assert.equal(validate({ account: 'synthetic', amount: 1 }), true);
  assert.equal(validate({ account: 'synthetic', amount: 0 }), false);
  fs.writeFileSync(path.join(root, 'shared.schema.json'), JSON.stringify({ $schema: dialect, $ref: 'remote.schema.json' }));
  request.files.push('remote.schema.json');
  result = run();
  assert.ok(result.schemas.every(s => !s.schema), 'Failure propagates through every dependent schema');
});

test('OpenAPI import retains same-path methods, 201/204/errors, all media types and request requiredness', t => {
  const { request, run } = setup(t, ['service.openapi.json', 'shared.schema.json']);
  const result = run(); validateResult(result, request);
  assert.ok(result.files.every(f => f.status === 'examined'));
  assert.equal(result.operations.length, 3);
  const post = result.operations.find(o => o.method === 'POST');
  assert.equal(post.owner, 'native'); assert.equal(post.mounted, undefined);
  assert.equal(post.server, 'https://service.example.test/api');
  assert.deepEqual(post.requests.map(r => [r.mediaType, r.required]), [['application/json', true], ['application/vnd.payment+json', true]]);
  assert.deepEqual(post.responses.map(r => [r.status, r.mediaType]), [['201', 'application/json'], ['201', 'application/problem+json'], ['422', 'application/json']]);
  assert.deepEqual(result.operations.find(o => o.method === 'DELETE').responses, [{ status: '204' }]);
  assert.ok(result.operations.some(o => o.method === 'GET' && o.path === post.path));
  assert.ok(result.operations.find(o => o.method === 'DELETE').gaps.some(g => g.includes('Parameter')));
  validator(result);
  const never = result.schemas.find(s => s.origin.pointer === '/components/schemas/Never');
  assert.equal(validator(result).getSchema(never.id)('anything'), false);
  const bundle = buildBundle(inventory(request, result));
  const documents = [...bundle.files].filter(([name]) => name.startsWith('openapi/')).map(([, value]) => JSON.parse(value));
  assert.equal(documents.length, 1);
  const spec = path.join(request.repository.root, 'generated.openapi.json');
  fs.writeFileSync(spec, JSON.stringify(documents[0]));
  const lint = spawnSync(path.join(pkg, 'node_modules/.bin/redocly'), ['lint', spec, '--extends', 'spec'], { encoding: 'utf8', timeout: 60000, env: { ...process.env, REDOCLY_TELEMETRY: 'off' } });
  assert.equal(lint.status, 0, lint.stdout + lint.stderr);
  const operation = documents[0].paths['/payments'].post;
  assert.equal(operation.requestBody.required, true);
  assert.deepEqual(Object.keys(operation.requestBody.content).sort(), ['application/json', 'application/vnd.payment+json']);
  assert.deepEqual(Object.keys(operation.responses['201'].content).sort(), ['application/json', 'application/problem+json']);
});

test('unsupported dialect/version and malformed artifacts are explicit and leak no document values', t => {
  const { request, run } = setup(t, ['unsupported.openapi.json', 'missing-dialect.schema.json', 'malformed.json', 'invalid.schema.json']);
  const result = run(); validateResult(result, request);
  assert.equal(result.files.find(f => f.path === 'unsupported.openapi.json').status, 'unsupported');
  assert.equal(result.files.find(f => f.path === 'missing-dialect.schema.json').status, 'unsupported');
  assert.equal(result.files.find(f => f.path === 'malformed.json').status, 'failed');
  assert.equal(result.files.find(f => f.path === 'invalid.schema.json').status, 'failed');
  assert.equal(result.operations.length, 0);
  assert.ok(result.schemas.every(s => !s.schema));
  assert.ok(!JSON.stringify(result.diagnostics).includes('this-is-synthetic'));
});

test('unresolved remote refs, resource scopes and dynamic anchors never produce dangling exports', t => {
  const { root, request, run } = setup(t, ['remote.schema.json', 'missing.schema.json']);
  let fetched = false;
  const previous = globalThis.fetch; globalThis.fetch = () => { fetched = true; throw new Error('Network forbidden'); };
  t.after(() => { globalThis.fetch = previous; });
  fs.writeFileSync(path.join(root, 'dynamic.schema.json'), JSON.stringify({ $schema: dialect, $dynamicAnchor: 'node', type: 'object', properties: { child: { $dynamicRef: '#node' } } }));
  fs.writeFileSync(path.join(root, 'nested.schema.json'), JSON.stringify({ $schema: dialect, $defs: { Inner: { $id: 'inner', type: 'string' } } }));
  request.files.push('dynamic.schema.json', 'nested.schema.json');
  const result = run();
  assert.equal(fetched, false);
  assert.ok(result.schemas.every(s => s.status === 'unsupported' && !s.schema));
  const bundle = buildBundle(inventory(request, result));
  assert.equal([...bundle.files.keys()].filter(name => name.startsWith('schemas/')).length, 0);
});

test('reference payloads and schema examples are preserved as data, not followed as refs', t => {
  const { root, request, run } = setup(t, ['literal.schema.json']);
  fs.writeFileSync(path.join(root, 'literal.schema.json'), JSON.stringify({ $schema: dialect, type: 'object', const: { $ref: 'https://literal.example.test' }, examples: [{ $ref: 'literal' }], default: { $ref: 'default' } }));
  const result = run();
  assert.deepEqual(result.schemas[0].schema.const, { $ref: 'https://literal.example.test' });
  assert.equal(result.diagnostics.length, 0);
  assert.equal(validator(result).getSchema(result.schemas[0].id)({ $ref: 'https://literal.example.test' }), true);
});

test('local references cannot read an unselected or out-of-root file', t => {
  const { root, request, run } = setup(t, ['external.schema.json']);
  fs.writeFileSync(path.join(root, 'external.schema.json'), JSON.stringify({ $schema: dialect, $ref: '../outside.json' }));
  request.files.push('../outside.json');
  const result = run();
  assert.equal(result.files.find(f => f.path === '../outside.json').status, 'failed');
  assert.ok(result.schemas.every(s => !s.schema));
});


test('native const and examples stay literal when projected into OpenAPI components', t => {
  const { root, request, run } = setup(t, ['literal.openapi.json']);
  fs.writeFileSync(path.join(root, 'literal.openapi.json'), JSON.stringify({
    openapi: '3.1.0', info: { title: 'Literal reference payload', version: '1' },
    paths: { '/literal': { get: { responses: { 200: { description: 'Literal data', content: { 'application/json': { schema: { type: 'object', const: { $ref: '#/literal' }, examples: [{ $ref: '#/example' }] } } } } } } } },
  }));
  const result = run();
  const bundle = buildBundle(inventory(request, result));
  const spec = JSON.parse([...bundle.files].find(([name]) => name.startsWith('openapi/'))[1]);
  const component = Object.values(spec.components.schemas).find(schema => schema.const);
  assert.deepEqual(component.const, { $ref: '#/literal' });
  assert.deepEqual(component.examples, [{ $ref: '#/example' }]);
});


test('malformed OpenAPI component maps and response shapes fail without fabricated operations', t => {
  const { root, request, run } = setup(t, ['invalid.openapi.json']);
  fs.writeFileSync(path.join(root, 'invalid.openapi.json'), JSON.stringify({ openapi: '3.1.0', info: { title: 'Malformed', version: '1' }, components: { schemas: [] } }));
  let result = run();
  assert.equal(result.files[0].status, 'failed');
  assert.equal(result.schemas.length, 0);
  fs.writeFileSync(path.join(root, 'invalid.openapi.json'), JSON.stringify({ openapi: '3.1.0', info: { title: 'Malformed', version: '1' }, paths: { '/invalid': { get: { responses: { 200: { content: {} } } } } } }));
  result = run();
  assert.equal(result.files[0].status, 'failed');
  assert.ok(result.diagnostics.some(d => d.code === 'invalid-native-openapi'));
  assert.ok(result.operations.every(op => op.responses.length === 0));
});
