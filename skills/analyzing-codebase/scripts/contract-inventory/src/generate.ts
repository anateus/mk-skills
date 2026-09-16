import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { compile } from 'json-schema-to-typescript';
import { hash, stringify } from './inventory.js';
import type { Bundle } from './export.js';

const VERSION = { typescript: '16.0.0', python: '0.81.0', pydantic: '2.13.5' } as const;
const DIALECT = 'https://json-schema.org/draft/2020-12/schema';
const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const PRIMITIVES = new Set(['string', 'number', 'integer', 'boolean', 'null']);
const NAME = /^[A-Za-z][A-Za-z0-9_]{0,127}$/;
const ANNOTATIONS = new Set(['title', 'description', '$comment', 'default', 'examples', 'example']);
const METADATA = new Set(['$schema', '$id', '$defs', 'definitions']);
const KEYWORDS = new Set(['type', 'properties', 'required', 'additionalProperties', 'items', 'enum', 'const', 'anyOf', '$ref']);
const modelSuffix = (id: string) => [...hash(id).slice(0, 20)].map(digit => String.fromCharCode(97 + Number.parseInt(digit, 16))).join('');
const simpleEnum = (value: unknown): value is string => typeof value === 'string' && /^[A-Za-z0-9_.:/-]{1,128}$/.test(value);

type Schema = Record<string, unknown>;
interface Source {
  file: string; schema: Schema; id: string; uri: string; digest: string;
  status: string; gaps: string[];
}
interface ConversionRecord {
  sourceId: string; sourceUri: string; sourceFile: string; sourceHash: string;
  sourceStatus: string; sourceGaps: string[];
  status: 'generated' | 'skipped' | 'failed';
  typeName: string; dependencies: Array<{ sourceId: string; sourceHash: string; sourceStatus: string; sourceGaps: string[] }>;
  artifacts?: { typescript: string; python: string };
  conversionGaps: string[]; issues: string[];
}
export interface GenerationOptions { inputDir: string; python?: string; }

function object(value: unknown): value is Schema {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

/** Read only manifest-owned, ordinary files. No input path may resolve through a symlink. */
function readOwned(root: string, relative: string, limit = 8 * 1024 * 1024): string {
  if (!relative || path.isAbsolute(relative) || relative.includes('\\') || relative.split('/').some(part => !part || part === '..' || part === '.')) throw new Error('Invalid generation input path');
  let current = root;
  for (const part of relative.split('/')) {
    current = path.join(current, part);
    if (fs.lstatSync(current).isSymbolicLink()) throw new Error('Generation input must not contain symlinks');
  }
  const stat = fs.statSync(current);
  if (!stat.isFile() || stat.size > limit) throw new Error('Generation input must be a bounded regular file');
  return fs.readFileSync(current, 'utf8');
}

function loadSources(inputDir: string): { sources: Source[]; manifestHash: string } {
  const root = path.resolve(inputDir);
  if (fs.lstatSync(root).isSymbolicLink() || !fs.statSync(root).isDirectory()) throw new Error('Generation input must be a real inventory bundle directory');
  const text = readOwned(root, 'manifest.json');
  const manifest: unknown = JSON.parse(text);
  if (!object(manifest) || manifest.generator !== '@mk-skills/contract-inventory' || !Array.isArray(manifest.files) || manifest.files.some(file => typeof file !== 'string')) throw new Error('Generation requires a contract-inventory bundle manifest');
  const files = (manifest.files as string[]).filter(file => file.startsWith('schemas/'));
  if (new Set(files).size !== files.length || files.length > 1000) throw new Error('Generation schema selection is duplicated or exceeds 1000 files');
  const ids = new Set<string>(), uris = new Set<string>();
  let bytes = 0;
  const sources = files.sort().map(file => {
    if (!/^schemas\/[A-Za-z0-9_-]+\.json$/.test(file)) throw new Error('Invalid schema artifact path in bundle manifest');
    const raw = readOwned(root, file);
    bytes += Buffer.byteLength(raw);
    if (bytes > 32 * 1024 * 1024) throw new Error('Generation input exceeds 32 MiB');
    const schema: unknown = JSON.parse(raw);
    if (!object(schema) || typeof schema['x-contract-id'] !== 'string' || !schema['x-contract-id'] || typeof schema.$id !== 'string' || !schema.$id) throw new Error('Each schema needs source ID and URI provenance');
    const id = schema['x-contract-id'], uri = schema.$id;
    if (ids.has(id) || uris.has(uri)) throw new Error('Duplicate schema identity in generation input');
    ids.add(id); uris.add(uri);
    const gaps = schema['x-contract-gaps'];
    if (!Array.isArray(gaps) || gaps.some(gap => typeof gap !== 'string')) throw new Error('Each schema needs an explicit source gaps array');
    return { file, schema, id, uri, digest: hash(raw), status: typeof schema['x-contract-status'] === 'string' ? schema['x-contract-status'] : 'unknown', gaps: [...gaps] as string[] };
  });
  return { sources, manifestHash: hash(text) };
}

/** Convert reference locations, not data types. Existing generators own language emission. */
class Projection {
  readonly issues = new Set<string>();
  readonly gaps = new Set<string>();
  readonly dependencies = new Set<Source>();
  readonly definitions: Record<string, Schema> = Object.create(null);
  private readonly locations = new Map<string, string>();
  private nodes = 0;
  constructor(readonly sources: Source[]) {}

  private reference(source: Source, ref: string): { source: Source; pointer: string; value: unknown } | undefined {
    const split = ref.indexOf('#');
    const address = split === -1 ? ref : ref.slice(0, split);
    const pointer = split === -1 ? '' : ref.slice(split + 1);
    let target = source;
    if (address) {
      const matches = this.sources.filter(item => item.uri === address || item.id === address || path.posix.normalize(path.posix.join(path.posix.dirname(source.file), address)) === item.file);
      if (matches.length !== 1) { this.issues.add('reference-outside-selected-bundle'); return; }
      target = matches[0];
    }
    if (pointer && !pointer.startsWith('/')) { this.issues.add('named-reference-anchor-unsupported'); return; }
    let value: unknown = target.schema;
    try {
      for (const encoded of pointer ? pointer.slice(1).split('/') : []) {
        const key = decodeURIComponent(encoded).replace(/~1/g, '/').replace(/~0/g, '~');
        if (!object(value) || !Object.hasOwn(value, key)) { this.issues.add('reference-pointer-unresolved'); return; }
        value = value[key];
      }
    } catch { this.issues.add('reference-pointer-invalid'); return; }
    return { source: target, pointer, value };
  }

  private ref(source: Source, value: string, depth: number): Schema {
    const target = this.reference(source, value);
    if (!target) return {};
    const location = target.source.uri + '#' + target.pointer;
    let name = this.locations.get(location);
    if (!name) {
      name = 'Schema' + modelSuffix(location);
      this.locations.set(location, name);
      this.definitions[name] = {};
      this.definitions[name] = this.project(target.source, target.value, target.pointer, depth + 1);
      this.definitions[name].title = name;
    }
    return { $ref: '#/$defs/' + name };
  }

  project(source: Source, value: unknown, pointer = '', depth = 0): Schema {
    this.dependencies.add(source);
    if (++this.nodes > 100000 || depth > 128) { this.issues.add('schema-complexity-limit'); return {}; }
    if (!object(value)) { this.issues.add('boolean-or-nonobject-schema-unsupported'); return {}; }
    if (source.schema.$schema !== DIALECT) this.issues.add('schema-dialect-unsupported');
    const keys = Object.keys(value);
    for (const key of keys) {
      if (key.startsWith('x-contract-')) continue;
      if (key.startsWith('x-python-')) { this.gaps.add('python-native-extension-not-applied-to-wire-model'); continue; }
      if (ANNOTATIONS.has(key)) { this.gaps.add('schema-annotations-and-defaults-omitted'); continue; }
      if (METADATA.has(key)) {
        if (key === '$id' && pointer) this.issues.add('nested-schema-id-unsupported');
        continue;
      }
      if (!KEYWORDS.has(key)) this.issues.add('unsupported-schema-keyword:' + key);
    }
    if (value.$ref !== undefined) {
      if (typeof value.$ref !== 'string') { this.issues.add('invalid-reference'); return {}; }
      if (keys.some(key => KEYWORDS.has(key) && key !== '$ref')) this.issues.add('reference-sibling-constraints-unsupported');
      return this.ref(source, value.$ref, depth);
    }
    if (value.anyOf !== undefined) {
      const branches = value.anyOf;
      if (keys.some(key => KEYWORDS.has(key) && key !== 'anyOf')) this.issues.add('nullable-or-enum-sibling-constraints-unsupported');
      if (Array.isArray(branches) && branches.length && branches.every(branch => object(branch) && simpleEnum(branch.const) && Object.keys(branch).every(key => key === 'const'))) {
        return { type: 'string', enum: [...new Set(branches.map(branch => branch.const))] };
      }
      if (!Array.isArray(branches) || branches.length !== 2 || branches.filter(branch => object(branch) && (branch.type === 'null' || (Object.hasOwn(branch, 'const') && branch.const === null))).length !== 1) {
        this.issues.add('only-nullable-anyof-supported'); return {};
      }
      return { anyOf: branches.map((branch, index) => this.project(source, branch, pointer + '/anyOf/' + index, depth + 1)) };
    }
    if (Array.isArray(value.type)) {
      if (value.type.length !== 2 || !value.type.includes('null') || value.type.some(type => typeof type !== 'string' || !PRIMITIVES.has(type))) { this.issues.add('type-array-unsupported'); return {}; }
      return { anyOf: value.type.map(type => this.project(source, { ...value, type }, pointer, depth + 1)) };
    }
    if (Object.hasOwn(value, 'const')) {
      if (keys.some(key => KEYWORDS.has(key) && key !== 'const')) this.issues.add('constant-sibling-constraints-unsupported');
      if (value.const === null) return { type: 'null' };
      if (simpleEnum(value.const)) return { type: 'string', enum: [value.const] };
      this.issues.add('only-null-and-simple-string-constants-supported');
      return {};
    }
    if (value.enum !== undefined) {
      if (!Array.isArray(value.enum) || !value.enum.length || value.enum.some(item => !simpleEnum(item))) { this.issues.add('only-simple-string-enums-supported'); return {}; }
      if (value.type !== undefined && value.type !== 'string') this.issues.add('enum-type-conflict');
      if (keys.some(key => KEYWORDS.has(key) && !['type', 'enum'].includes(key))) this.issues.add('enum-sibling-constraints-unsupported');
      return { type: 'string', enum: value.enum };
    }
    if (typeof value.type !== 'string') { this.issues.add('unconstrained-or-untyped-schema-unsupported'); return {}; }
    if (PRIMITIVES.has(value.type)) {
      if (keys.some(key => KEYWORDS.has(key) && key !== 'type')) this.issues.add('primitive-sibling-constraints-unsupported');
      if (value.type === 'integer') this.gaps.add('typescript-number-does-not-enforce-integer-or-safe-range;strict-python-int-rejects-integral-json-floats');
      if (value.type === 'number') this.gaps.add('numeric-range-and-cross-language-floating-point-equivalence-not-established');
      return { type: value.type };
    }
    if (value.type === 'array') {
      if (keys.some(key => KEYWORDS.has(key) && !['type', 'items'].includes(key))) this.issues.add('array-sibling-constraints-unsupported');
      if (!object(value.items)) { this.issues.add('typed-array-items-required'); return {}; }
      return { type: 'array', items: this.project(source, value.items, pointer + '/items', depth + 1) };
    }
    if (value.type === 'object') {
      if (keys.some(key => KEYWORDS.has(key) && !['type', 'properties', 'required', 'additionalProperties'].includes(key))) this.issues.add('object-sibling-constraints-unsupported');
      if (value.properties !== undefined && !object(value.properties)) { this.issues.add('invalid-object-properties'); return {}; }
      if (value.additionalProperties !== undefined && typeof value.additionalProperties !== 'boolean') this.issues.add('typed-additional-properties-unsupported');
      const properties = object(value.properties) ? value.properties : {};
      if (value.additionalProperties === false) {
        this.gaps.add('typescript-structural-types-do-not-enforce-exact-object-properties');
        if (!Object.keys(properties).length) this.issues.add('closed-empty-object-typescript-shape-unsupported');
      }
      const required = value.required ?? [];
      if (!Array.isArray(required) || required.some(key => typeof key !== 'string' || !Object.hasOwn(properties, key)) || new Set(required).size !== required.length) { this.issues.add('invalid-required-fields'); return {}; }
      const projected: Record<string, Schema> = Object.create(null);
      for (const [name, schema] of Object.entries(properties)) {
        if (!NAME.test(name) || name.startsWith('model_') || name === 'constructor' || name === 'prototype') { this.issues.add('property-name-outside-safe-subset'); continue; }
        projected[name] = this.project(source, schema, pointer + '/properties/' + name, depth + 1);
      }
      return { type: 'object', properties: projected, required, additionalProperties: value.additionalProperties ?? true };
    }
    this.issues.add('schema-type-unsupported');
    return {};
  }
}

function pythonCommand(python: string, args: string[], cwd: string, input?: string): ReturnType<typeof spawnSync> {
  return spawnSync(python, ['-I', ...args], {
    cwd, input, encoding: 'utf8', timeout: 60000, maxBuffer: 16 * 1024 * 1024,
    env: { PATH: process.env.PATH ?? '', LANG: 'C.UTF-8', PYTHONIOENCODING: 'utf-8' },
  });
}

function verifyGenerators(python: string): void {
  const require = createRequire(import.meta.url);
  if (require('json-schema-to-typescript/package.json').version !== VERSION.typescript) throw new Error('Unexpected json-schema-to-typescript version; install the pinned package dependencies');
  const check = pythonCommand(python, ['-c', 'import json,sys; from importlib.metadata import version; print(json.dumps({"generator":version("datamodel-code-generator"),"pydantic":version("pydantic"),"python":list(sys.version_info[:2])}))'], PACKAGE_ROOT);
  if (check.error || check.status !== 0) throw new Error('Generation needs the dedicated Python environment from generation-requirements.txt');
  let versions;
  try { versions = JSON.parse(String(check.stdout)); } catch { throw new Error('Could not verify pinned Python generation dependencies'); }
  if (versions.generator !== VERSION.python || versions.pydantic !== VERSION.pydantic || versions.python[0] !== 3 || versions.python[1] < 12) throw new Error('Generation requires Python >=3.12 and exact generation-requirements.txt versions');
}

/** Generate a separate derived bundle. The caller owns atomic output/overwrite policy. */
export async function generateBundle(options: GenerationOptions): Promise<Bundle> {
  const { sources, manifestHash } = loadSources(options.inputDir);
  const python = path.resolve(options.python ?? path.join(PACKAGE_ROOT, '.venv-generation/bin/python'));
  verifyGenerators(python);
  const files = new Map<string, string>();
  const records: ConversionRecord[] = [];
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'contract-model-generation-'));
  try {
    for (const source of sources) {
      const typeName = 'Model' + modelSuffix(source.id);
      const projection = new Projection(sources);
      const normalized = projection.project(source, source.schema);
      const schema = { ...normalized, $schema: DIALECT, title: typeName, ...(Object.keys(projection.definitions).length ? { $defs: projection.definitions } : {}) };
      const record: ConversionRecord = {
        sourceId: source.id, sourceUri: source.uri, sourceFile: source.file, sourceHash: source.digest,
        sourceStatus: source.status, sourceGaps: source.gaps, status: 'skipped', typeName,
        dependencies: [...projection.dependencies].filter(item => item !== source).sort((a, b) => a.id.localeCompare(b.id)).map(item => ({ sourceId: item.id, sourceHash: item.digest, sourceStatus: item.status, sourceGaps: item.gaps })),
        conversionGaps: [...projection.gaps, 'typescript-output-is-type-only;no-runtime-validation', 'source-behavior-and-cross-language-equivalence-not-established'].sort(),
        issues: [...projection.issues].sort(),
      };
      records.push(record);
      if (record.issues.length) continue;
      const basename = hash(source.id).slice(0, 24);
      const typescriptArtifact = `models/typescript/${basename}.d.ts`;
      const pythonArtifact = `models/python/model_${basename}.py`;
      const sourceFile = path.join(scratch, 'schema.json'), outputFile = path.join(scratch, 'model.py');
      try {
        const typescript = await compile(schema, typeName, {
          bannerComment: '/* Derived contract model. Read generation.json for provenance and unresolved gaps. */',
          $refOptions: { resolve: { file: false, http: false }, dereference: { circular: true } },
          enableConstEnums: false, unknownAny: true, strictIndexSignatures: true,
        });
        fs.writeFileSync(sourceFile, stringify(schema));
        if (fs.existsSync(outputFile)) fs.unlinkSync(outputFile);
        const generated = pythonCommand(python, ['-m', 'datamodel_code_generator',
          '--ignore-pyproject', '--input', sourceFile, '--input-file-type', 'jsonschema', '--output', outputFile,
          '--output-model-type', 'pydantic_v2.BaseModel', '--target-python-version', '3.12',
          '--disable-timestamp', '--formatters', 'builtin', '--no-allow-remote-refs', '--strict-refs',
          '--strict-types', 'str', 'int', 'float', 'bool', '--strict-nullable', '--use-missing-sentinel',
          '--enum-field-as-literal', 'all', '--use-standard-collections', '--no-treat-dot-as-module', '--class-name', typeName,
        ], scratch);
        if (generated.error || generated.status !== 0 || !fs.existsSync(outputFile)) throw new Error('pydantic-generation-failed');
        const code = fs.readFileSync(outputFile, 'utf8');
        const syntax = pythonCommand(python, ['-c', 'import ast,sys; ast.parse(sys.stdin.read())'], scratch, code);
        if (syntax.error || syntax.status !== 0) throw new Error('generated-python-syntax-invalid');
        files.set(typescriptArtifact, typescript);
        files.set(pythonArtifact, code);
        record.artifacts = { typescript: typescriptArtifact, python: pythonArtifact };
        record.status = 'generated';
      } catch {
        record.status = 'failed';
        record.issues.push('generator-failed;source-and-generator-error-text-withheld');
      }
    }
  } finally { fs.rmSync(scratch, { recursive: true, force: true }); }
  const coverage = { complete: false, selectedSchemas: records.length, generated: records.filter(item => item.status === 'generated').length, skipped: records.filter(item => item.status === 'skipped').length, failed: records.filter(item => item.status === 'failed').length };
  files.set('generation.json', stringify({
    version: 1, kind: 'derived-contract-models', sourceManifestHash: manifestHash,
    generators: { typescript: { name: 'json-schema-to-typescript', version: VERSION.typescript, runtimeValidation: false }, python: { name: 'datamodel-code-generator', version: VERSION.python, runtime: 'Python >=3.12', pydantic: VERSION.pydantic, missingSentinel: 'pydantic.experimental.missing_sentinel.MISSING' } },
    schemaDialect: DIALECT, equivalence: 'not-established', coverage, records,
    usage: { python: 'Validate JSON with model_validate_json(..., strict=True); serialize with model_dump(mode="json", by_alias=True, exclude_unset=True).', typescript: 'Compile-time declarations only. Validate runtime payloads independently against the preserved source JSON Schema.' },
  }));
  files.set('coverage.json', stringify(coverage));
  return { files, failed: coverage.failed > 0, coverage };
}
