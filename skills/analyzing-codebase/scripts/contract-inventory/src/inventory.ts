import { createHash } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { AdapterResult, Operation, Repository, ScanRequest } from './types.js';
import { scanTypeScript } from './typescript.js';

const packageRoot = fileURLToPath(new URL('../', import.meta.url));
export const hash = (value: string | Buffer): string => createHash('sha256').update(value).digest('hex');
export function httpPath(operation: Operation): string | undefined {
  if (!operation.path || !operation.path.startsWith('/') || /[?#]/.test(operation.path)) return undefined;
  const normalized = operation.direction === 'inbound'
    ? operation.path.replace(/(^|\/):([A-Za-z_][A-Za-z0-9_]*)(?=\/|$)/g, '$1{$2}') : operation.path;
  if (operation.direction === 'inbound' && /(^|\/):|\*/.test(normalized)) return undefined;
  if (/[{}]/.test(normalized.replace(/\{[A-Za-z_][A-Za-z0-9_]*\}/g, ''))) return undefined;
  return normalized;
}
const json = (value: unknown): string => JSON.stringify(value, null, 2) + '\n';
const excludedDirectories = new Set(['.git', '.venv', 'venv', 'node_modules', 'vendor', 'dist', 'build', '__pycache__', '.next', '.worktrees', 'docs', 'tests', '__tests__', 'fixtures', '__fixtures__', 'test', 'coverage']);
const extensions = new Set(['.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs', '.py', '.go', '.rs', '.java', '.kt', '.rb', '.cs', '.php', '.proto', '.graphql', '.sql', '.cue']);

export interface ScanOptions { roots: Array<{ id: string; root: string }>; includes: string[]; python: string; out: string; }
interface Excluded { path: string; reason: string; }
interface SourceFile { path: string; sha256: string; }
interface RootScan {
  repository: Repository;
  scope: { includes: string[]; excludedDirectories: string[]; defaultTestExclusions: boolean };
  sourceFiles: SourceFile[];
  excluded: Excluded[];
  results: AdapterResult[];
}
export interface Inventory {
  protocolVersion: 1;
  analysis: 'static';
  complete: false;
  repositories: RootScan[];
  declarations: AdapterResult['declarations'];
  schemas: AdapterResult['schemas'];
  operations: AdapterResult['operations'];
  relationships: AdapterResult['relationships'];
  operationGroups: Array<{ id: string; owner: string; method: string; path: string; observations: string[] }>;
}

function git(root: string, args: string[]): string | undefined {
  try { return execFileSync('git', ['-C', root, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], maxBuffer: 32 * 1024 * 1024 }).trimEnd(); }
  catch { return undefined; }
}

function rootIncludes(options: ScanOptions, id: string): string[] {
  return options.includes.flatMap(value => {
    const separator = value.indexOf(':');
    if (separator < 0) return [value];
    return value.slice(0, separator) === id ? [value.slice(separator + 1)] : [];
  }).map(value => {
    const normalized = value.replaceAll('\\', '/').replace(/^\.\//, '').replace(/\/$/, '');
    if (!normalized || path.isAbsolute(normalized) || normalized.split('/').includes('..')) throw new Error(`Invalid include path: ${value}`);
    return normalized;
  });
}

function discover(root: string, includes: string[], out: string): { files: string[]; excluded: Excluded[] } {
  const files: string[] = [];
  const excluded: Excluded[] = [];
  const listed = git(root, ['ls-files', '--cached', '--others', '--exclude-standard', '-z']);
  const candidates = listed === undefined ? undefined : new Set(listed.split('\0').filter(Boolean));
  const selected = (relative: string) => includes.length === 0 || includes.some(prefix => prefix === '.' || relative === prefix || relative.startsWith(prefix + '/'));
  const reachable = (relative: string) => includes.length === 0 || includes.some(prefix => prefix === '.' || relative === prefix || relative.startsWith(prefix + '/') || prefix.startsWith(relative + '/'));
  function visit(relative: string): void {
    const absolute = path.join(root, relative);
    if (absolute === out) { excluded.push({ path: relative, reason: 'output-directory' }); return; }
    const stat = fs.lstatSync(absolute);
    if (stat.isSymbolicLink()) { excluded.push({ path: relative, reason: 'symlink' }); return; }
    if (stat.isDirectory()) {
      if (relative && excludedDirectories.has(path.basename(relative))) { excluded.push({ path: relative, reason: 'default-exclusion' }); return; }
      if (relative && !reachable(relative)) { excluded.push({ path: relative, reason: 'outside-requested-scope' }); return; }
      for (const entry of fs.readdirSync(absolute).sort()) visit(relative ? `${relative}/${entry}` : entry);
    } else if (stat.isFile() && extensions.has(path.extname(relative))) {
      if (!selected(relative)) return;
      if (candidates && !candidates.has(relative)) { excluded.push({ path: relative, reason: 'git-ignored' }); return; }
      if (/\.(test|spec)\.[^.]+$/.test(relative) || /(^|\/)test_[^/]+\.py$/.test(relative)) { excluded.push({ path: relative, reason: 'test-source' }); return; }
      if (stat.size > 2 * 1024 * 1024) { excluded.push({ path: relative, reason: 'source-over-2MiB-limit' }); return; }
      files.push(relative);
    }
  }
  visit('');
  return { files, excluded };
}

function failure(name: string, files: string[], code: string, message: string): AdapterResult {
  return { protocolVersion: 1, adapter: { name, version: '0.1.0', capabilities: [], limitations: [message] }, declarations: [], schemas: [], operations: [], relationships: [], files: files.map(p => ({ path: p, status: 'failed' })), diagnostics: [{ code, message }] };
}

/** Validate the cross-process boundary before accepting any adapter output. */
export function validateResult(value: unknown, request: ScanRequest): AdapterResult {
  if (!value || typeof value !== 'object') throw new Error('Adapter result must be an object');
  const result = value as AdapterResult;
  if (result.protocolVersion !== 1 || !result.adapter || typeof result.adapter.name !== 'string' || !Array.isArray(result.adapter.capabilities) || !Array.isArray(result.adapter.limitations)) throw new Error('Invalid adapter protocol metadata');
  for (const field of ['declarations', 'schemas', 'operations', 'relationships', 'files', 'diagnostics'] as const) {
    if (!Array.isArray(result[field])) throw new Error(`Adapter result missing ${field}`);
  }
  const requested = new Set(request.files);
  const reported = new Set<string>();
  for (const file of result.files) {
    if (!file || !requested.has(file.path) || reported.has(file.path) || !['examined', 'failed', 'unsupported'].includes(file.status)) throw new Error('Invalid adapter file coverage');
    reported.add(file.path);
  }
  if (reported.size !== requested.size) throw new Error('Adapter omitted requested file coverage');
  const ids = new Set<string>();
  for (const item of [...result.declarations, ...result.schemas, ...result.operations]) {
    if (!item || typeof item.id !== 'string' || !item.id.startsWith(request.repository.id + ':') || ids.has(item.id)) throw new Error('Invalid or duplicate adapter record identity');
    ids.add(item.id);
    if (!['resolved', 'partial', 'unsupported'].includes(item.status) || !Array.isArray(item.gaps) || !item.gaps.every(x => typeof x === 'string') || !Array.isArray(item.evidence) || item.evidence.length === 0) throw new Error('Adapter record lacks status or evidence');
    for (const e of item.evidence) {
      if (!e || !requested.has(e.file) || !Number.isInteger(e.line) || e.line < 1) throw new Error('Adapter evidence falls outside requested source files');
    }
  }
  for (const op of result.operations) {
    if (!['http', 'tool', 'message', 'storage'].includes(op.kind) || !['inbound', 'outbound', 'internal'].includes(op.direction) || !Array.isArray(op.responses)) throw new Error('Invalid operation shape');
    for (const response of op.responses) if (!response || typeof response.status !== 'string') throw new Error('Invalid response status');
  }
  for (const rel of result.relationships) {
    if (!rel || typeof rel.source !== 'string' || typeof rel.target !== 'string' || !Array.isArray(rel.evidence)) throw new Error('Invalid relationship shape');
  }
  return result;
}

function python(request: ScanRequest, executable: string): AdapterResult {
  const result = spawnSync(executable, [path.join(packageRoot, 'python/adapter.py')], {
    input: JSON.stringify(request), encoding: 'utf8', timeout: 120000, maxBuffer: 32 * 1024 * 1024,
    env: { PATH: process.env.PATH, SYSTEMROOT: process.env.SYSTEMROOT, PYTHONDONTWRITEBYTECODE: '1', PYTHONNOUSERSITE: '1' },
  });
  if (result.error || result.status !== 0) return failure('python', request.files, 'adapter-failed', 'Python adapter unavailable or failed; no target code was executed.');
  try { return validateResult(JSON.parse(result.stdout), request); }
  catch { return failure('python', request.files, 'invalid-adapter-result', 'Python adapter returned an invalid protocol result.'); }
}

function normalizeResult(result: AdapterResult): AdapterResult {
  for (const key of ['declarations', 'schemas', 'operations'] as const) result[key].sort((a, b) => a.id.localeCompare(b.id));
  result.files.sort((a, b) => a.path.localeCompare(b.path));
  result.relationships.sort((a, b) => json(a).localeCompare(json(b)));
  result.diagnostics.sort((a, b) => json(a).localeCompare(json(b)));
  return result;
}

export function scan(options: ScanOptions): Inventory {
  const seen = new Set<string>();
  const roots = new Set<string>();
  const repositories: RootScan[] = [];
  for (const target of options.roots) {
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(target.id) || seen.has(target.id)) throw new Error('Repository IDs must be unique simple names');
    seen.add(target.id);
    const root = fs.realpathSync(target.root);
    if (!fs.statSync(root).isDirectory() || roots.has(root)) throw new Error('Repository roots must be unique directories');
    roots.add(root);
    const includes = rootIncludes(options, target.id);
    if (options.includes.length && !includes.length) throw new Error(`No include scope supplied for ${target.id}`);
    const repository = { id: target.id, root, revision: git(root, ['rev-parse', 'HEAD']) || 'uncommitted' };
    const { files, excluded } = discover(root, includes, path.resolve(options.out));
    if (!files.length) throw new Error(`No source files selected for ${target.id}; check include paths and exclusions`);
    const sourceFiles = files.map(p => ({ path: p, sha256: hash(fs.readFileSync(path.join(root, p))) }));
    const results: AdapterResult[] = [];
    const tsFiles = files.filter(p => /\.(?:[cm]?ts|tsx|[cm]?js|jsx)$/.test(p));
    const pyFiles = files.filter(p => p.endsWith('.py'));
    const unsupported = files.filter(p => !tsFiles.includes(p) && !pyFiles.includes(p));
    if (tsFiles.length) {
      const request: ScanRequest = { protocolVersion: 1, repository, files: tsFiles };
      try { results.push(validateResult(scanTypeScript(request), request)); }
      catch { results.push(failure('typescript', tsFiles, 'adapter-failed', 'TypeScript adapter failed or returned an invalid result.')); }
    }
    if (pyFiles.length) results.push(python({ protocolVersion: 1, repository, files: pyFiles }, options.python));
    if (unsupported.length) results.push({ ...failure('unsupported-language', [], 'unsupported-language', 'No adapter for these source languages.'), files: unsupported.map(p => ({ path: p, status: 'unsupported' })) });
    // Hash again: a concurrent edit invalidates this scan's attribution.
    for (const source of sourceFiles) {
      if (!fs.existsSync(path.join(root, source.path)) || hash(fs.readFileSync(path.join(root, source.path))) !== source.sha256) throw new Error(`Source changed during scan: ${target.id}/${source.path}`);
    }
    repositories.push({ repository, scope: { includes, excludedDirectories: [...excludedDirectories].sort(), defaultTestExclusions: true }, sourceFiles, excluded, results: results.map(normalizeResult) });
  }
  const results = repositories.flatMap(r => r.results);
  const operations = results.flatMap(r => r.operations);
  const groups = new Map<string, Inventory['operationGroups'][number]>();
  for (const op of operations) {
    let owner = op.owner;
    if (!owner && op.direction === 'inbound') owner = op.id.split(':')[0];
    if (!owner && op.server) { try { owner = new URL(op.server).origin; } catch { /* unresolved */ } }
    const normalizedPath = httpPath(op);
    if (op.kind !== 'http' || !owner || !op.method || !normalizedPath) continue;
    const identity = JSON.stringify([owner, op.method.toUpperCase(), normalizedPath]);
    const group = groups.get(identity) || { id: `http:${hash(identity).slice(0, 24)}`, owner, method: op.method.toUpperCase(), path: normalizedPath, observations: [] };
    group.observations.push(op.id); groups.set(identity, group);
  }
  return { protocolVersion: 1, analysis: 'static', complete: false, repositories, declarations: results.flatMap(r => r.declarations), schemas: results.flatMap(r => r.schemas), operations, relationships: results.flatMap(r => r.relationships), operationGroups: [...groups.values()].sort((a, b) => a.id.localeCompare(b.id)) };
}

export const stringify = json;
