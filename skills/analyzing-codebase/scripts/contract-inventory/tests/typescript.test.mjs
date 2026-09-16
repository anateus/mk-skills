import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { scanTypeScript } from '../dist/typescript.js';
const root = fileURLToPath(new URL('../fixtures/typescript/', import.meta.url));
const scan = () => scanTypeScript({ protocolVersion: 1, repository: { id: 'fixture', root, revision: 'synthetic' }, files: ['contracts.ts', 'shared.ts'] });
const result = scan();
test('TypeScript declarations preserve internal visibility, aliases, recursion, and references', () => {
  const internal = result.declarations.find(d => d.name === 'Internal');
  assert.equal(internal.exported, false);
  const schema = result.schemas.find(s => s.id === internal.schemaId).schema;
  assert.equal(schema.properties.next.$ref, internal.schemaId);
  const shared = result.declarations.find(d => d.name === 'Shared');
  assert.equal(schema.properties.shared.$ref, shared.schemaId);
  assert.ok(result.relationships.some(r => r.source === internal.id && r.target === shared.id));
});
test('Zod static schema keeps constraints and reports lost custom rules', () => {
  const input = result.schemas.find(s => s.name === 'Input');
  assert.equal(input.schema.properties.name.minLength, 2);
  assert.deepEqual(input.schema.required, ['name']);
  assert.deepEqual(input.schema.properties.state.enum, ['ready', 'done']);
  assert.equal(input.status, 'partial');
  assert.ok(input.gaps.some(g => g.includes('refine')));
});
test('ts-rest preserves same-path methods, statuses, prefix and static mount evidence', () => {
  const operations = result.operations.filter(o => o.direction === 'inbound');
  assert.equal(operations.length, 5);
  const list = operations.find(o => o.name === 'contract.list');
  const create = operations.find(o => o.name === 'contract.create');
  assert.equal(list.path, '/v1/widgets'); assert.equal(create.path, list.path);
  assert.equal(list.method, 'GET'); assert.equal(create.method, 'POST');
  assert.deepEqual(create.responses.map(r => r.status), ['201', '422']);
  assert.equal(list.mounted, true);
  assert.ok(list.evidence.some(e => e.basis === 'registration'));
  assert.equal(operations.find(o => o.name === 'contract.remove').responses[0].schemaId, undefined);
  assert.equal(operations.find(o => o.name === 'unmounted.waiting').mounted, undefined);
});
test('outbound transport and one-hop wrapper candidates omit secrets and retain unresolved URL', () => {
  const calls = result.operations.filter(o => o.direction === 'outbound');
  assert.ok(calls.some(o => o.method === 'POST' && o.server === 'https://provider.invalid' && o.path === '/widgets'));
  assert.ok(calls.some(o => o.method === 'DELETE' && o.path === '/widgets/42'));
  assert.ok(calls.some(o => o.details.wrapper === 'getWidget' && o.path === '/widgets'));
  assert.ok(calls.some(o => !o.path && o.gaps.some(g => g.includes('URL is dynamic'))));
  assert.ok(calls.every(o => o.responses.length === 0 && o.status === 'partial'));
  const serialized = JSON.stringify(result);
  for (const sentinel of ['DO_NOT_EMIT', 'SECRET_HEADER_SENTINEL', 'SECRET_BODY_SENTINEL']) assert.equal(serialized.includes(sentinel), false);
});
test('provider tool registries remain individually traceable without guessed ownership', () => {
  const tools = result.operations.filter(o => o.kind === 'tool');
  assert.equal(tools.length, 3);
  assert.ok(tools.every(o => o.owner === undefined));
  assert.equal(tools.filter(o => o.details.registry === 'VAPI_TOOLS_MAP').length, 2);
  assert.equal(tools.find(o => o.details.registry === 'TELNYX_TOOLS_BY_NAME').details.handler, 'resolveTarget');
});
test('inventory is deterministic, uniquely identified, and reports all selected source files', () => {
  assert.deepEqual(scan(), result);
  const ids = [...result.declarations, ...result.schemas, ...result.operations].map(v => v.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(result.files.every(f => f.status === 'examined'));
  assert.deepEqual(result.files.map(f => f.path), ['contracts.ts', 'shared.ts']);
});

test('unresolved import and dynamic method are explicit candidates', () => {
  assert.ok(result.diagnostics.some(d => d.code === 'unresolved-import' && d.file === 'contracts.ts'));
  const candidate = result.operations.find(o => o.name === 'dynamicContract.candidate');
  assert.equal(candidate.method, undefined);
  assert.equal(candidate.path, '/dynamic');
  assert.ok(candidate.gaps.some(g => g.includes('HTTP method is dynamic')));
});

test('nested registry entries retain explicit registration coverage gaps', () => {
  const diagnostic = result.diagnostics.find(d => d.code === 'unresolved-registration' && d.symbol === 'toolsMap');
  assert.ok(diagnostic);
  assert.equal(diagnostic.file, 'contracts.ts');
  assert.ok(diagnostic.message.includes('Nested'));
  assert.ok(diagnostic.line > 0);
});
