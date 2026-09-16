import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import { validateResult } from '../dist/inventory.js';

const pkg = fileURLToPath(new URL('../', import.meta.url));
function setup(t) {
  const root = fs.mkdtempSync(path.join(tmpdir(), 'contract-integration-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const ts = path.join(root, 'typescript');
  const py = path.join(root, 'python');
  fs.cpSync(path.join(pkg, 'fixtures/typescript'), ts, { recursive: true });
  fs.cpSync(path.join(pkg, 'fixtures/python'), py, { recursive: true });
  const out = path.join(root, 'output');
  const run = (extra = []) => spawnSync(process.execPath, [path.join(pkg, 'dist/cli.js'), 'scan', '--root', `legacy=${ts}`, '--root', `worker=${py}`, '--out', out, ...extra], { encoding: 'utf8' });
  return { root, ts, py, out, run };
}
const read = filename => JSON.parse(fs.readFileSync(filename, 'utf8'));

test('CLI joins Python and TypeScript, preserves coverage, schemas, and OpenAPI operations', t => {
  const { out, run } = setup(t);
  const result = run();
  assert.equal(result.status, 0, result.stderr + result.stdout);
  const inventory = read(path.join(out, 'inventory.json'));
  const coverage = read(path.join(out, 'coverage.json'));
  assert.equal(inventory.repositories.length, 2);
  assert.ok(inventory.declarations.some(d => d.language === 'python'));
  assert.ok(inventory.declarations.some(d => d.language === 'typescript' && !d.exported));
  assert.equal(coverage.complete, false);
  assert.equal(coverage.scanStatus, 'partial');
  assert.ok(coverage.exports.operations.some(o => o.status === 'skipped' && /Response status/.test(o.reason)));
  assert.ok(inventory.operations.some(o => o.kind === 'tool'));
  assert.ok(inventory.operations.some(o => o.direction === 'outbound' && !o.path));
  const schemas = fs.readdirSync(path.join(out, 'schemas')).map(p => read(path.join(out, 'schemas', p)));
  const ajv = new Ajv2020({ strict: false, validateFormats: false, logger: false });
  for (const schema of schemas) ajv.addSchema(schema);
  for (const schema of schemas) assert.ok(ajv.getSchema(schema.$id), schema.$id);
  const paths = [];
  let sawComponentGap = false;
  for (const filename of fs.readdirSync(path.join(out, 'openapi'))) {
    const full = path.join(out, 'openapi', filename);
    const spec = read(full);
    const specUri = `https://contracts.invalid/openapi/${filename}`;
    const componentValidator = new Ajv2020({ strict: false, validateFormats: false, logger: false });
    componentValidator.addSchema({ ...spec, $id: specUri });
    for (const [name, schema] of Object.entries(spec.components.schemas)) {
      assert.equal(schema.$id, undefined, 'Embedded component must not change the document reference base');
      assert.ok(componentValidator.getSchema(`${specUri}#/components/schemas/${name}`));
      assert.ok(schema['x-contract-id']);
      if (schema['x-contract-gaps']?.some(g => /validator|refine/.test(g))) sawComponentGap = true;
    }
    for (const [url, item] of Object.entries(spec.paths)) for (const [method, operation] of Object.entries(item)) paths.push({ url, method, responses: operation.responses });
    const lint = spawnSync(path.join(pkg, 'node_modules/.bin/redocly'), ['lint', full, '--extends', 'spec'], { encoding: 'utf8', timeout: 60000, env: { ...process.env, REDOCLY_TELEMETRY: 'off' } });
    assert.equal(lint.status, 0, lint.stderr + lint.stdout);
  }
  assert.equal(sawComponentGap, true, 'Standalone OpenAPI must retain native validation gaps');
  assert.ok(paths.some(p => p.responses['201']));
  assert.ok(paths.some(p => p.responses['204']));
  assert.ok(paths.some(p => p.url === '/v1/widgets/{id}'));
  assert.ok(!paths.some(p => p.url.includes('/:id')));
  assert.ok(paths.some(p => p.responses['202']));
  assert.ok(paths.some(p => p.responses['400']));
  assert.ok(paths.some(a => paths.some(b => a.url === b.url && a.method !== b.method)));
  const original = fs.readFileSync(path.join(out, 'inventory.json'), 'utf8');
  assert.equal(run().status, 0);
  assert.equal(fs.readFileSync(path.join(out, 'inventory.json'), 'utf8'), original);
});

test('CLI keeps failed adapter attempts separate and refuses unrelated output', t => {
  const { out, run } = setup(t);
  assert.equal(run().status, 0);
  const original = fs.readFileSync(path.join(out, 'inventory.json'), 'utf8');
  const failed = run(['--python', '/nonexistent/contract-python']);
  assert.equal(failed.status, 2);
  const attempted = JSON.parse(failed.stdout).output;
  assert.ok(attempted.startsWith(path.join(out, 'attempts') + path.sep));
  assert.equal(read(path.join(attempted, 'coverage.json')).scanStatus, 'failed');
  assert.equal(fs.readFileSync(path.join(out, 'inventory.json'), 'utf8'), original);
  fs.writeFileSync(path.join(out, 'notes.md'), 'reviewed annotation');
  const refused = run();
  assert.equal(refused.status, 1);
  assert.match(refused.stderr, /unmanaged files/);
  assert.equal(fs.readFileSync(path.join(out, 'notes.md'), 'utf8'), 'reviewed annotation');
});

test('scan scope detects selected unsupported source, excludes fixtures and symlinks', t => {
  const { ts, out, run } = setup(t);
  fs.writeFileSync(path.join(ts, 'future.go'), 'package future\n');
  fs.mkdirSync(path.join(ts, 'fixtures'));
  fs.writeFileSync(path.join(ts, 'fixtures', 'private.ts'), 'export type HiddenFixture = string;');
  fs.symlinkSync(path.join(ts, 'contracts.ts'), path.join(ts, 'linked.ts'));
  assert.equal(run().status, 0);
  const coverage = read(path.join(out, 'coverage.json'));
  const root = coverage.roots.find(r => r.repository.id === 'legacy');
  assert.equal(root.files.find(f => f.path === 'future.go').status, 'unsupported');
  assert.ok(root.excluded.some(f => f.path === 'fixtures' && f.reason === 'default-exclusion'));
  assert.ok(root.excluded.some(f => f.path === 'linked.ts' && f.reason === 'symlink'));
  assert.ok(!read(path.join(out, 'inventory.json')).declarations.some(d => d.name === 'HiddenFixture'));
  const unknown = run(['--include', 'missing:src']);
  assert.equal(unknown.status, 1);
  assert.match(unknown.stderr, /unknown repository/);
});

test('failed attempts cannot follow a symlink outside the owned output', t => {
  const { root, out, run } = setup(t);
  assert.equal(run().status, 0);
  const external = path.join(root, 'external');
  fs.mkdirSync(external);
  fs.symlinkSync(external, path.join(out, 'attempts'));
  const result = run(['--python', '/nonexistent/contract-python']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Attempts must be a real directory/);
  assert.deepEqual(fs.readdirSync(external), []);
});

test('protocol boundary rejects omitted file coverage and unscoped evidence', () => {
  const request = { protocolVersion: 1, repository: { id: 'repo', root: '/synthetic', revision: 'test' }, files: ['one.py'] };
  const result = { protocolVersion: 1, adapter: { name: 'test', version: '1', capabilities: [], limitations: [] }, declarations: [], schemas: [], operations: [], relationships: [], files: [{ path: 'one.py', status: 'examined' }], diagnostics: [] };
  assert.equal(validateResult(result, request), result);
  assert.throws(() => validateResult({ ...result, files: [] }, request), /omitted/);
  assert.throws(() => validateResult({ ...result, declarations: [{ id: 'repo:decl', status: 'partial', gaps: [], evidence: [{ file: 'outside.py', line: 1 }] }] }, request), /outside/);
});

test('native OpenAPI survives import/export with multiple request and response media', t => {
  const root = fs.mkdtempSync(path.join(tmpdir(), 'contract-native-cli-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const spec = { openapi: '3.1.0', info: { title: 'Synthetic native API', version: '1' }, paths: { '/widgets': { post: {
    requestBody: { required: true, content: { 'application/json': { schema: { $ref: '#/components/schemas/Widget' } }, 'application/vnd.widget+json': { schema: { $ref: '#/components/schemas/Widget' } } } },
    responses: { '201': { description: 'Created', content: { 'application/json': { schema: { $ref: '#/components/schemas/Widget' } }, 'text/plain': { schema: { type: 'string' } } } }, '204': { description: 'No content' } },
  } } }, components: { schemas: { Widget: { type: 'object', required: ['name'], properties: { name: { type: 'string', minLength: 1 } }, additionalProperties: false } } } };
  fs.writeFileSync(path.join(root, 'spec.json'), JSON.stringify(spec));
  const out = path.join(root, 'out');
  const scan = spawnSync(process.execPath, [path.join(pkg, 'dist/cli.js'), 'scan', '--root', `native=${root}`, '--artifact', 'native:spec.json', '--out', out], { encoding: 'utf8' });
  assert.equal(scan.status, 0, scan.stderr + scan.stdout);
  const inventory = read(path.join(out, 'inventory.json'));
  assert.deepEqual(inventory.repositories[0].artifactFiles, ['spec.json']);
  assert.match(inventory.repositories[0].sourceFiles[0].sha256, /^[a-f0-9]{64}$/);
  const filenames = fs.readdirSync(path.join(out, 'openapi'));
  assert.equal(filenames.length, 1);
  const exported = read(path.join(out, 'openapi', filenames[0]));
  const post = exported.paths['/widgets'].post;
  assert.deepEqual(Object.keys(post.requestBody.content).sort(), ['application/json', 'application/vnd.widget+json']);
  assert.equal(post.requestBody.required, true);
  assert.deepEqual(Object.keys(post.responses['201'].content).sort(), ['application/json', 'text/plain']);
  assert.equal(post.responses['204'].content, undefined);
  const lint = spawnSync(path.join(pkg, 'node_modules/.bin/redocly'), ['lint', path.join(out, 'openapi', filenames[0]), '--extends', 'spec'], { encoding: 'utf8', env: { ...process.env, REDOCLY_TELEMETRY: 'off' } });
  assert.equal(lint.status, 0, lint.stderr + lint.stdout);
});

test('CLI records alias configuration hashes and keeps resolution within selected sources', t => {
  const root = fs.mkdtempSync(path.join(tmpdir(), 'contract-alias-integration-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.mkdirSync(path.join(root, 'src'));
  fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ name: 'test-alias' }));
  fs.writeFileSync(path.join(root, 'tsconfig.json'), JSON.stringify({ compilerOptions: { baseUrl: '.', paths: { '@/*': ['src/*'] } } }));
  fs.writeFileSync(path.join(root, 'src/model.ts'), 'export interface Model { name: string }');
  fs.writeFileSync(path.join(root, 'src/use.ts'), "import type { Model } from '@/model'; export interface Use { model: Model }");
  const out = path.join(root, 'out');
  const run = include => spawnSync(process.execPath, [path.join(pkg, 'dist/cli.js'), 'scan', '--root', `alias=${root}`, '--include', include, '--out', out], { encoding: 'utf8' });
  let result = run('src');
  assert.equal(result.status, 0, result.stderr);
  const inventory = read(path.join(out, 'inventory.json'));
  assert.deepEqual(inventory.repositories[0].configurationFiles.map(f => f.path), ['package.json', 'tsconfig.json']);
  assert.ok(inventory.repositories[0].configurationFiles.every(f => /^[a-f0-9]{64}$/.test(f.sha256)));
  assert.ok(inventory.relationships.some(r => r.kind === 'references'));
  result = run('src/use.ts');
  assert.equal(result.status, 0, result.stderr);
  assert.ok(read(path.join(out, 'inventory.json')).repositories[0].results[0].diagnostics.some(d => /import/.test(d.code)));
});

test('CLI generates models from native schema inventory and protects inventory ownership', t => {
  const root = fs.mkdtempSync(path.join(tmpdir(), 'contract-generation-cli-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, 'payload.json'), JSON.stringify({ $schema: 'https://json-schema.org/draft/2020-12/schema', type: 'object', properties: { name: { type: 'string' } }, required: ['name'], additionalProperties: false }));
  const input = path.join(root, 'inventory'), out = path.join(root, 'models');
  const scan = spawnSync(process.execPath, [path.join(pkg, 'dist/cli.js'), 'scan', '--root', `native=${root}`, '--artifact', 'native:payload.json', '--out', input], { encoding: 'utf8' });
  assert.equal(scan.status, 0, scan.stderr);
  const run = output => spawnSync(process.execPath, [path.join(pkg, 'dist/cli.js'), 'generate', '--input', input, '--out', output], { encoding: 'utf8' });
  const result = run(out);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(read(path.join(out, 'manifest.json')).kind, 'models');
  assert.ok(fs.readdirSync(path.join(out, 'models/python')).some(file => file.endsWith('.py')));
  assert.ok(fs.readdirSync(path.join(out, 'models/typescript')).some(file => file.endsWith('.d.ts')));
  const before = fs.readFileSync(path.join(input, 'manifest.json'), 'utf8');
  assert.equal(run(input).status, 1);
  assert.equal(fs.readFileSync(path.join(input, 'manifest.json'), 'utf8'), before);
});
