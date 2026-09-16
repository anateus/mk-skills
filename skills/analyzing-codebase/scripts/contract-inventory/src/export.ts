import * as fs from 'node:fs';
import * as path from 'node:path';
import { hash, httpPath, stringify, type Inventory } from './inventory.js';
import type { Operation, SchemaRecord } from './types.js';

interface ExportRecord { id: string; status: 'exported' | 'skipped'; artifact?: string; reason?: string; }
export interface Bundle { files: Map<string, string>; failed: boolean; coverage: Record<string, unknown>; }
const key = (id: string) => hash(id).slice(0, 24);
const schemaUri = (id: string) => `https://contracts.invalid/schemas/${key(id)}.json`;
const methods = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']);

function rewriteRefs(value: unknown, records: Map<string, SchemaRecord>, prefix?: string): unknown {
  if (Array.isArray(value)) return value.map(item => rewriteRefs(item, records, prefix));
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).map(([name, child]) => {
    if (name === '$ref' && typeof child === 'string') {
      if (records.has(child)) return [name, prefix ? `#/components/schemas/${key(child)}` : schemaUri(child)];
      if (prefix && child.startsWith('#/')) return [name, prefix + child.slice(1)];
      if (prefix && child === '#') return [name, prefix];
    }
    return [name, rewriteRefs(child, records, prefix)];
  }));
}

function validServer(server: string | undefined): string | undefined {
  if (!server) return undefined;
  try {
    const url = new URL(server);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) return undefined;
    return url.origin + (url.pathname === '/' ? '' : url.pathname);
  } catch { return undefined; }
}

function operationSpec(op: Operation, schemas: Map<string, SchemaRecord>): Record<string, unknown> {
  const responses: Record<string, unknown> = {};
  for (const response of op.responses) {
    const content = response.mediaType && response.schemaId && schemas.has(response.schemaId)
      ? { [response.mediaType]: { schema: { $ref: `#/components/schemas/${key(response.schemaId)}` } } } : undefined;
    responses[response.status] = { description: 'Response declared in analyzed source', ...(content ? { content } : {}) };
  }
  const parameters = [...new Set([...httpPath(op)!.matchAll(/\{([^{}]+)\}/g)].map(m => m[1]))].map(name => ({ name, in: 'path', required: true, schema: {}, 'x-contract-gap': 'Parameter constraints not independently resolved by exporter' }));
  const server = validServer(op.server);
  return {
    operationId: `operation_${key(op.id)}`,
    summary: op.name,
    responses,
    ...(parameters.length ? { parameters } : {}),
    ...(server ? { servers: [{ url: server }] } : {}),
    ...(op.requestSchemaId && op.requestMediaType && schemas.has(op.requestSchemaId)
      ? { requestBody: { content: { [op.requestMediaType]: { schema: { $ref: `#/components/schemas/${key(op.requestSchemaId)}` } } } } } : {}),
    'x-contract-id': op.id,
    'x-contract-direction': op.direction,
    'x-contract-source-path': op.path,
    'x-contract-mounted': op.mounted ?? 'unresolved',
    'x-contract-status': op.status,
    'x-contract-evidence': op.evidence,
    'x-contract-gaps': [...op.gaps, ...(!server ? ['Server location not resolved; document is a contract fragment, not a runnable target.'] : [])],
  };
}

export function buildBundle(inventory: Inventory): Bundle {
  const files = new Map<string, string>();
  const schemas = new Map(inventory.schemas.filter(s => s.schema).map(s => [s.id, s]));
  const schemaExports: ExportRecord[] = [];
  for (const record of inventory.schemas) {
    if (!record.schema) { schemaExports.push({ id: record.id, status: 'skipped', reason: 'No representable static schema' }); continue; }
    const artifact = `schemas/${key(record.id)}.json`;
    files.set(artifact, stringify({
      ...(rewriteRefs(record.schema, schemas) as object), $schema: record.dialect, $id: schemaUri(record.id),
      'x-contract-id': record.id, 'x-contract-role': record.role, 'x-contract-status': record.status,
      'x-contract-gaps': record.gaps, 'x-contract-evidence': record.evidence,
    }));
    schemaExports.push({ id: record.id, status: 'exported', artifact });
  }
  const operationExports: ExportRecord[] = [];
  // Separate colliding observations instead of merging incompatible client expectations.
  const documents = new Map<string, Array<{ paths: Record<string, Record<string, unknown>>; ops: string[] }>>();
  for (const op of inventory.operations) {
    const normalizedPath = httpPath(op);
    let reason: string | undefined;
    if (op.kind !== 'http') reason = 'Non-HTTP boundary; retained in inventory';
    else if (!normalizedPath || !op.method || !methods.has(op.method.toLowerCase())) reason = 'HTTP method or path unresolved';
    else if (!op.responses.length || op.responses.some(r => !/^(?:[1-5][0-9]{2}|[1-5]XX|default)$/.test(r.status))) reason = 'Response status unresolved; exporter does not invent responses';
    if (reason) { operationExports.push({ id: op.id, status: 'skipped', reason }); continue; }
    const repo = op.id.split(':')[0];
    const group = stringify([repo, op.owner || validServer(op.server) || 'unresolved', op.direction]);
    const bins = documents.get(group) || [];
    const method = op.method!.toLowerCase();
    let document = bins.find(doc => !doc.paths[normalizedPath!]?.[method]);
    if (!document) { document = { paths: {}, ops: [] }; bins.push(document); }
    (document.paths[normalizedPath!] ||= {})[method] = operationSpec(op, schemas);
    document.ops.push(op.id); documents.set(group, bins);
  }
  const components = Object.fromEntries([...schemas.values()].map(record => {
    const projection = rewriteRefs(record.schema, schemas, `#/components/schemas/${key(record.id)}`) as Record<string, unknown>;
    // Component references resolve within this OpenAPI document, not the native resource URI.
    delete projection.$id;
    delete projection.$schema;
    return [key(record.id), { ...projection, 'x-contract-id': record.id, 'x-contract-role': record.role,
      'x-contract-status': record.status, 'x-contract-gaps': record.gaps, 'x-contract-evidence': record.evidence }];
  }));
  for (const [group, bins] of documents) for (const [index, document] of bins.entries()) {
    const artifact = `openapi/${key(group)}-${index + 1}.json`;
    files.set(artifact, stringify({
      openapi: '3.1.0', info: { title: 'Static contract inventory fragment', version: '0.1.0' },
      paths: document.paths, components: { schemas: components },
      'x-contract-complete': false, 'x-contract-analysis': 'static',
    }));
    for (const id of document.ops) operationExports.push({ id, status: 'exported', artifact });
  }
  const roots = inventory.repositories.map(root => ({
    repository: root.repository, scope: root.scope, excluded: root.excluded,
    files: root.sourceFiles.map(source => ({ ...source, status: root.results.flatMap(r => r.files).find(f => f.path === source.path)?.status })),
    adapters: root.results.map(r => r.adapter), diagnostics: root.results.flatMap(r => r.diagnostics),
    counts: { files: root.sourceFiles.length, declarations: root.results.reduce((n, r) => n + r.declarations.length, 0), operations: root.results.reduce((n, r) => n + r.operations.length, 0) },
  }));
  const failed = inventory.repositories.some(root => root.results.some(result => result.files.some(file => file.status === 'failed')));
  const coverage = { protocolVersion: 1, complete: false, scanStatus: failed ? 'failed' : 'partial', analysis: 'static', roots, exports: { schemas: schemaExports, operations: operationExports.sort((a, b) => a.id.localeCompare(b.id)) } };
  files.set('inventory.json', stringify(inventory));
  files.set('coverage.json', stringify(coverage));
  const provenance = inventory.repositories.map(r => `  - id: ${JSON.stringify(r.repository.id)}\n    system_path: ${JSON.stringify(r.repository.root)}\n    commit: ${JSON.stringify(r.repository.revision)}`).join('\n');
  const rows = roots.map(root => `| ${root.repository.id} | ${root.counts.files} | ${root.counts.declarations} | ${root.counts.operations} |`).join('\n');
  files.set('summary.md', `---\nanalysis: static\ncomplete: false\nrepositories:\n${provenance}\nexternal_references: []\n---\n\n# Contract inventory\n\nThis is a partial static inventory of the selected source files. It does not establish deployed behavior, complete consumer coverage, or readiness to retire a capability.\n\n| Repository | Selected source files | Declarations | Boundary candidates |\n| --- | --- | --- | --- |\n${rows}\n\nRead [coverage.json](coverage.json) for exclusions, unsupported constructs, failures, and export omissions. [inventory.json](inventory.json) retains evidence, relationships, and conversion gaps. Source hashes describe the analyzed working tree. Type and schema matches do not establish behavioral equivalence.\n\nGenerated HTTP documents are contract fragments; verify server locations, mounting, and provider evidence before using them to drive requests. Keep reviewed annotations and transition decisions outside this generated directory.\n`);
  return { files, failed, coverage };
}

/** Replace only a directory previously owned by this tool; leave failed attempts separate. */
export function writeBundle(bundle: Bundle, requestedOut: string): string {
  const out = path.resolve(requestedOut);
  let destination = out;
  const marker = 'manifest.json';
  if (fs.existsSync(out)) {
    if (fs.lstatSync(out).isSymbolicLink() || !fs.statSync(out).isDirectory()) throw new Error('Output must be a dedicated directory, not a symlink or file');
    const entries = fs.readdirSync(out);
    if (entries.length) {
      let manifest;
      try {
        if (!fs.lstatSync(path.join(out, marker)).isSymbolicLink()) manifest = JSON.parse(fs.readFileSync(path.join(out, marker), 'utf8'));
      } catch { /* unowned */ }
      if (manifest?.generator !== '@mk-skills/contract-inventory') throw new Error('Refusing to replace a nonempty output directory not owned by contract-inventory');
      const expected = new Set<string>([...manifest.files, marker]);
      const unmanaged: string[] = [];
      function check(relative: string): void {
        for (const name of fs.readdirSync(path.join(out, relative))) {
          const item = relative ? `${relative}/${name}` : name;
          const stat = fs.lstatSync(path.join(out, item));
          if (item === 'attempts') {
            if (stat.isSymbolicLink() || !stat.isDirectory()) throw new Error('Attempts must be a real directory within the owned output');
            continue;
          }
          if (stat.isDirectory() && !stat.isSymbolicLink()) check(item);
          else if (!expected.has(item)) unmanaged.push(item);
        }
      }
      check('');
      if (unmanaged.length) throw new Error('Output contains unmanaged files; move annotations outside the generated directory before refreshing');
      if (bundle.failed) destination = path.join(out, 'attempts', hash(bundle.files.get('inventory.json')!).slice(0, 24));
    }
  }
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const stage = fs.mkdtempSync(path.join(path.dirname(destination), '.contract-inventory-'));
  const backup = stage + '-previous';
  try {
    for (const [relative, content] of bundle.files) {
      const filename = path.join(stage, relative); fs.mkdirSync(path.dirname(filename), { recursive: true }); fs.writeFileSync(filename, content);
    }
    fs.writeFileSync(path.join(stage, marker), stringify({ generator: '@mk-skills/contract-inventory', version: '0.1.0', files: [...bundle.files.keys()].sort() }));
    if (destination === out && fs.existsSync(path.join(out, 'attempts'))) fs.cpSync(path.join(out, 'attempts'), path.join(stage, 'attempts'), { recursive: true, dereference: false });
    if (fs.existsSync(destination)) fs.renameSync(destination, backup);
    try { fs.renameSync(stage, destination); }
    catch (error) { if (fs.existsSync(backup)) fs.renameSync(backup, destination); throw error; }
    if (fs.existsSync(backup)) fs.rmSync(backup, { recursive: true });
    return destination;
  } finally { if (fs.existsSync(stage)) fs.rmSync(stage, { recursive: true }); }
}
