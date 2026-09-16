import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';
import Ajv2020 from 'ajv/dist/2020.js';
import { generateBundle } from '../dist/generate.js';
import { scanTypeScript } from '../dist/typescript.js';

const packageRoot = fileURLToPath(new URL('../', import.meta.url));
const fixtures = path.join(packageRoot, 'fixtures/conversion');
const python = path.join(packageRoot, '.venv-generation/bin/python');
const dialect = 'https://json-schema.org/draft/2020-12/schema';
function temp() { return fs.mkdtempSync(path.join(os.tmpdir(), 'contract-conversion-test-')); }
function source(schema, index = 0, gaps = []) {
  return { ...schema, $schema: dialect, $id: `https://contracts.invalid/test/${index}`, 'x-contract-id': `test:schema:${index}`, 'x-contract-status': gaps.length ? 'partial' : 'resolved', 'x-contract-gaps': gaps };
}
function inputBundle(directory, schemas) {
  fs.mkdirSync(path.join(directory, 'schemas'), { recursive: true });
  const files = schemas.map((schema, index) => {
    const name = `schemas/schema_${index}.json`;
    fs.writeFileSync(path.join(directory, name), JSON.stringify(schema));
    return name;
  });
  fs.writeFileSync(path.join(directory, 'manifest.json'), JSON.stringify({ generator: '@mk-skills/contract-inventory', version: '0.1.0', files }));
}
function writeOutput(directory, bundle) {
  for (const [name, content] of bundle.files) {
    const filename = path.join(directory, name);
    fs.mkdirSync(path.dirname(filename), { recursive: true });
    fs.writeFileSync(filename, content);
  }
}
function nativeSchema() {
  const result = spawnSync(python, ['-I', path.join(fixtures, 'python_models.py')], { encoding: 'utf8' });
  assert.equal(result.status, 0, 'Install generation-requirements.txt in .venv-generation first. ' + result.stderr);
  return JSON.parse(result.stdout);
}
function validatePython(directory, record, valid, invalid) {
  const result = spawnSync(python, ['-I', path.join(fixtures, 'validate_generated.py')], {
    input: JSON.stringify({ root: directory, file: record.artifacts.python, typeName: record.typeName, valid, invalid }), encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}
function validateTypescript(directory, record, valid, invalid) {
  const script = path.join(directory, 'conformance.ts');
  const declaration = './' + record.artifacts.typescript.replace(/\.d\.ts$/, '.js');
  fs.writeFileSync(script, `import type { ${record.typeName} as Model } from ${JSON.stringify(declaration)};\n` +
    valid.map((value, i) => `const valid${i}: Model = ${JSON.stringify(value)};`).join('\n') + '\n' +
    invalid.map((value, i) => `// @ts-expect-error Synthetic invalid payload must fail structural type checking.\nconst invalid${i}: Model = ${JSON.stringify(value)};`).join('\n'));
  const program = ts.createProgram([script], { noEmit: true, strict: true, exactOptionalPropertyTypes: true, target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.NodeNext, moduleResolution: ts.ModuleResolutionKind.NodeNext, types: [] });
  const diagnostics = ts.getPreEmitDiagnostics(program);
  assert.deepEqual(diagnostics.map(item => ts.flattenDiagnosticMessageText(item.messageText, '\n')), []);
}

test('Python native schema generates TypeScript declarations with compile-time positive and negative fixtures', async () => {
  const directory = temp();
  try {
    const schema = source(nativeSchema(), 0, ['native-field-validator-not-represented']);
    inputBundle(directory, [schema]);
    const bundle = await generateBundle({ inputDir: directory, python });
    const manifest = JSON.parse(bundle.files.get('generation.json'));
    const [record] = manifest.records;
    assert.equal(record.status, 'generated', JSON.stringify(record));
    assert.deepEqual(record.sourceGaps, ['native-field-validator-not-represented']);
    assert.equal(manifest.equivalence, 'not-established');
    assert.equal(manifest.generators.typescript.runtimeValidation, false);
    assert.equal(manifest.generators.typescript.version, '16.0.0');
    writeOutput(directory, bundle);
    const valid = { name: 'ok', required_nullable: null, action: 'keep', child: { name: 'child', enabled: true }, children: [] };
    const missing = { ...valid }; delete missing.required_nullable;
    validateTypescript(directory, record, [valid, { ...valid, optional_nullable: null }], [{ ...valid, name: 42 }, missing, { ...valid, action: 'unknown' }]);
    const validate = new Ajv2020({ strict: false }).compile(schema);
    assert.equal(validate(valid), true);
    assert.equal(validate(missing), false);
    // The native custom validator is absent from JSON Schema and remains a source gap.
    assert.equal(validate({ ...valid, name: 'reserved' }), true);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('TypeScript source schemas generate strict Pydantic models with omission/nullability and serialization conformance', async () => {
  const directory = temp();
  try {
    const scanned = scanTypeScript({ protocolVersion: 1, repository: { id: 'conversion', root: fixtures, revision: 'synthetic' }, files: ['typescript_models.ts'] });
    const schemas = scanned.schemas.map((record, index) => ({ ...source(record.schema, index, record.gaps), 'x-contract-id': record.id }));
    inputBundle(directory, schemas);
    const bundle = await generateBundle({ inputDir: directory, python });
    const manifest = JSON.parse(bundle.files.get('generation.json'));
    assert.ok(manifest.records.every(record => record.status === 'generated'), JSON.stringify(manifest.records));
    const target = scanned.schemas.find(record => record.name === 'TypescriptPayload');
    const record = manifest.records.find(record => record.sourceId === target.id);
    assert.equal(record.dependencies.length, 1);
    assert.equal(manifest.generators.python.version, '0.81.0');
    assert.equal(manifest.generators.python.pydantic, '2.13.5');
    writeOutput(directory, bundle);
    const valid = { name: 'ok', required_nullable: null, action: 'keep', child: { name: 'child', enabled: true }, children: [], count: 4.5 };
    const missing = { ...valid }; delete missing.required_nullable;
    const invalid = [{ ...valid, name: 42 }, { ...valid, optional_name: null }, missing, { ...valid, action: 'unknown' }, { ...valid, child: { name: 'child', enabled: 'true' } }];
    const result = validatePython(directory, record, [valid, { ...valid, optional_name: 'present', children: [valid.child] }], invalid);
    assert.equal(result.rejected, invalid.length);
    validateTypescript(directory, record, [valid], invalid.slice(0, 3));
    const ajv = new Ajv2020({ strict: false });
    for (const schema of schemas) ajv.addSchema(schema, schema['x-contract-id']);
    const validate = ajv.getSchema(target.id);
    assert.equal(validate(valid), true);
    for (const value of invalid) assert.equal(validate(value), false);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('generation rejects external references and injection extensions without fetching or executing them', async () => {
  const directory = temp();
  let requests = 0;
  const server = http.createServer((request, response) => { requests++; response.end('{}'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const url = `http://127.0.0.1:${server.address().port}/must-not-fetch`;
    await fetch(url); // Prove the request counter detects a known positive before the no-fetch assertion.
    assert.equal(requests, 1);
    requests = 0;
    inputBundle(directory, [
      source({ $ref: url }, 0), source({ $ref: 'file:///must-not-read.json' }, 1),
      source({ type: 'string', tsType: 'unknown; process.exit(1)' }, 2),
      source({ type: 'object', customBasePath: 'untrusted.module.Class' }, 3),
      source({ type: 'object', properties: { 'bad\nname': { type: 'string' } } }, 4),
      source({ type: 'string', minLength: 2 }, 5),
      source({ type: 'integer', anyOf: [{ const: 'keep' }, { const: 'drop' }] }, 6),
      source({ type: 'object', properties: {}, additionalProperties: false }, 7),
    ]);
    const bundle = await generateBundle({ inputDir: directory, python });
    const manifest = JSON.parse(bundle.files.get('generation.json'));
    assert.equal(manifest.coverage.skipped, 8);
    assert.equal(manifest.coverage.generated, 0);
    assert.equal(requests, 0);
    assert.ok(manifest.records[0].issues.includes('reference-outside-selected-bundle'));
    assert.ok(manifest.records[2].issues.includes('unsupported-schema-keyword:tsType'));
    assert.ok(manifest.records[5].issues.includes('unsupported-schema-keyword:minLength'));
    assert.ok(manifest.records[7].issues.includes('closed-empty-object-typescript-shape-unsupported'));
    assert.ok(![...bundle.files.values()].join('').includes('process.exit'));
  } finally { server.close(); fs.rmSync(directory, { recursive: true, force: true }); }
});

test('generation follows only manifest-owned refs, preserves dependency gaps, and is deterministic', async () => {
  const directory = temp();
  try {
    const dependency = source({ type: 'object', properties: { name: { type: 'string' } }, required: ['name'], additionalProperties: false }, 0, ['source-validator-not-exported']);
    const parent = source({ type: 'object', properties: { child: { $ref: dependency.$id } }, required: ['child'], additionalProperties: false }, 1);
    inputBundle(directory, [dependency, parent]);
    fs.writeFileSync(path.join(directory, 'schemas', 'unowned.json'), 'not JSON');
    const first = await generateBundle({ inputDir: directory, python });
    const second = await generateBundle({ inputDir: directory, python });
    assert.deepEqual([...first.files], [...second.files]);
    const records = JSON.parse(first.files.get('generation.json')).records;
    assert.equal(records.length, 2);
    assert.deepEqual(records[1].dependencies[0].sourceGaps, ['source-validator-not-exported']);
    fs.unlinkSync(path.join(directory, 'schemas', 'schema_0.json'));
    fs.symlinkSync(path.join(directory, 'schemas', 'schema_1.json'), path.join(directory, 'schemas', 'schema_0.json'));
    await assert.rejects(generateBundle({ inputDir: directory, python }), /symlinks/);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('generation fails explicitly when required Python dependencies are unavailable', async () => {
  const directory = temp();
  try {
    inputBundle(directory, [source({ type: 'string' })]);
    await assert.rejects(generateBundle({ inputDir: directory, python: path.join(directory, 'missing-python') }), /dedicated Python environment/);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});

test('local recursive references and root arrays remain valid generated models', async () => {
  const directory = temp();
  try {
    inputBundle(directory, [
      source({ type: 'object', properties: { name: { type: 'string' }, child: { anyOf: [{ $ref: '#' }, { type: 'null' }] } }, required: ['name'], additionalProperties: false }, 0),
      source({ type: 'array', items: { type: 'string' } }, 1),
      source({ $ref: 'https://contracts.invalid/test/0' }, 2),
    ]);
    const bundle = await generateBundle({ inputDir: directory, python });
    const records = JSON.parse(bundle.files.get('generation.json')).records;
    assert.ok(records.every(record => record.status === 'generated'), JSON.stringify(records));
    writeOutput(directory, bundle);
    const tree = { name: 'root', child: { name: 'leaf', child: null } };
    validatePython(directory, records[0], [tree, { name: 'root' }], [{ name: 'root', child: { name: 1 } }]);
    validateTypescript(directory, records[0], [tree], [{ name: 1 }]);
    validatePython(directory, records[1], [['one', 'two'], []], [[1], 'not-an-array']);
    validateTypescript(directory, records[1], [['one', 'two']], [[1]]);
    validatePython(directory, records[2], [tree], [{ name: 1 }]);
    validateTypescript(directory, records[2], [tree], [{ name: 1 }]);
  } finally { fs.rmSync(directory, { recursive: true, force: true }); }
});
