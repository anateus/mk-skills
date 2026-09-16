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
