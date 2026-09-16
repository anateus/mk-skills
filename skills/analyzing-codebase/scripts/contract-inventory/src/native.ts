import * as fs from 'node:fs';
import * as path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Ajv2020 } from 'ajv/dist/2020.js';
import type { AdapterResult, Evidence, JsonSchema, Operation, ScanRequest, SchemaRecord } from './types.js';

const DIALECT = 'https://json-schema.org/draft/2020-12/schema';
const OAS_DIALECT = 'https://spec.openapis.org/oas/3.1/dialect/base';
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const schemaValue = (value: unknown): value is JsonSchema | boolean => typeof value === 'boolean' || object(value);
const escape = (value: string) => value.replaceAll('~', '~0').replaceAll('/', '~1');
const pointer = (base: string, key: string) => `${base}/${escape(key)}`;
const schemaMaps = new Set(['$defs', 'definitions', 'properties', 'patternProperties', 'dependentSchemas']);
const schemaArrays = new Set(['allOf', 'anyOf', 'oneOf', 'prefixItems']);
const schemaSingles = new Set(['additionalProperties', 'unevaluatedProperties', 'propertyNames', 'items', 'contains', 'unevaluatedItems', 'not', 'if', 'then', 'else', 'contentSchema']);
const methods = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']);
interface Artifact { file: string; uri: string; base: string; data: Record<string, unknown>; kind: 'native-json-schema' | 'native-openapi'; dialect: string; }
interface Location { artifact: Artifact; pointer: string; value: unknown; }

/** Import only explicitly selected JSON artifacts. No target modules or remote references execute. */
export function importNative(request: ScanRequest): AdapterResult {
  const result: AdapterResult = {
    protocolVersion: 1,
    adapter: { name: 'native-artifacts', version: '0.1.0', capabilities: ['json-schema-2020-12', 'openapi-3.1', 'explicit-local-reference-closure'], limitations: [
      'Only explicitly selected JSON artifacts are read; references are never fetched.',
      'Standalone JSON Schema requires an explicit 2020-12 dialect; OpenAPI 3.0 conversion is unsupported.',
      'Native declarations do not establish deployment, runtime validation completeness, or compatibility with another implementation.',
      'Nested schema resource IDs and dynamic references require separate handling; affected schemas are retained as unsupported records.',
      'OpenAPI parameters, security, callbacks, links, encodings and server alternatives require review; originals remain at their source locations.',
    ] },
    declarations: [], schemas: [], operations: [], relationships: [], files: [], diagnostics: [],
  };
  const artifacts = new Map<string, Artifact>();
  const aliases = new Map<string, Artifact | null>();
  const records = new Map<string, SchemaRecord>();
  const dependencies = new Map<string, Set<string>>();
  const statuses = new Map<string, 'examined' | 'failed' | 'unsupported'>();
  const ajv = new Ajv2020({ strict: false, validateFormats: false, logger: false });
  const root = fs.realpathSync(request.repository.root);
  const evidence = (a: Artifact, at: string): Evidence => ({ file: a.file, line: 1, pointer: at, basis: 'declaration' });
  const id = (a: Artifact, at: string, kind: string) => `${request.repository.id}:native:${encodeURIComponent(a.file)}:${kind}:${encodeURIComponent(at || '#')}`;
  function diagnostic(file: string, code: string, message: string) { result.diagnostics.push({ file, line: 1, code, message }); }
  function alias(uri: string, artifact: Artifact) { aliases.set(uri, aliases.has(uri) && aliases.get(uri) !== artifact ? null : artifact); }

  for (const file of [...new Set(request.files)].sort()) {
    statuses.set(file, 'examined');
    try {
      const absolute = path.resolve(root, file);
      if (path.isAbsolute(file) || !file.endsWith('.json') || path.relative(root, absolute).startsWith('..') || fs.realpathSync(absolute) !== absolute) throw new Error('unsafe-path');
      const data: unknown = JSON.parse(fs.readFileSync(absolute, 'utf8'));
      if (!object(data)) throw new Error('artifact-object-required');
      let kind: Artifact['kind']; let dialect: string;
      if ('openapi' in data) {
        if (typeof data.openapi !== 'string' || !/^3\.1\.\d+$/.test(data.openapi)) {
          statuses.set(file, 'unsupported'); diagnostic(file, 'unsupported-native-version', 'Only OpenAPI 3.1 artifacts are supported; no version conversion was performed.'); continue;
        }
        if (!object(data.info) || typeof data.info.title !== 'string' || typeof data.info.version !== 'string' || (data.paths !== undefined && !object(data.paths)) || (data.components !== undefined && !object(data.components)) || (!data.paths && !data.components && !data.webhooks)) throw new Error('invalid-openapi');
        if (object(data.components) && ['schemas', 'requestBodies', 'responses', 'pathItems'].some(key => data.components && object(data.components) && data.components[key] !== undefined && !object(data.components[key]))) throw new Error('invalid-openapi-components');
        kind = 'native-openapi'; dialect = typeof data.jsonSchemaDialect === 'string' ? data.jsonSchemaDialect : OAS_DIALECT;
      } else { kind = 'native-json-schema'; dialect = typeof data.$schema === 'string' ? data.$schema : ''; }
      if (![DIALECT, OAS_DIALECT].includes(dialect) || (kind === 'native-json-schema' && dialect !== DIALECT)) {
        statuses.set(file, 'unsupported'); diagnostic(file, 'unsupported-native-dialect', 'An explicitly supported JSON Schema dialect is required; no dialect was guessed.'); continue;
      }
      const uri = pathToFileURL(absolute).href;
      const base = kind === 'native-json-schema' && typeof data.$id === 'string' ? new URL(data.$id, uri).href : uri;
      if (new URL(base).hash) throw new Error('fragment-resource-id');
      const artifact = { file, uri, base, data, kind, dialect };
      artifacts.set(file, artifact); alias(uri, artifact); alias(base, artifact);
    } catch {
      statuses.set(file, 'failed'); diagnostic(file, 'invalid-native-artifact', 'Selected artifact could not be read as a supported JSON document within the repository.');
    }
  }

  function locate(a: Artifact, reference: string): Location | undefined {
    let url: URL;
    try { url = new URL(reference, a.base); } catch { return; }
    const fragment = url.hash; url.hash = '';
    const target = aliases.get(url.href);
    if (!target) return;
    let at: string;
    try { at = decodeURIComponent(fragment.slice(1)); } catch { return; }
    if (at && !at.startsWith('/')) return; // Named/dynamic anchors need resource-aware handling.
    let value: unknown = target.data;
    for (const token of at ? at.slice(1).split('/') : []) {
      if (/~(?:[^01]|$)/.test(token)) return;
      const key = token.replaceAll('~1', '/').replaceAll('~0', '~');
      if ((!object(value) && !Array.isArray(value)) || !Object.hasOwn(value, key)) return;
      value = (value as Record<string, unknown>)[key];
    }
    return { artifact: target, pointer: at, value };
  }

  function ensureSchema(a: Artifact, at: string, value: unknown, role: SchemaRecord['role']): string {
    const identity = id(a, at, 'schema');
    if (records.has(identity)) return identity;
    const record: SchemaRecord = { id: identity, name: at || path.basename(a.file), role, dialect: a.dialect, status: 'resolved', evidence: [evidence(a, at)], gaps: [], origin: { kind: a.kind, file: a.file, pointer: at } };
    records.set(identity, record); dependencies.set(identity, new Set());
    if (!schemaValue(value)) {
      record.status = 'unsupported'; record.gaps.push('Native schema is not an object or boolean.');
      statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-schema', 'A native schema has an invalid JSON Schema shape.'); return identity;
    }
    const inheritedDialect = object(value) && typeof value.$schema === 'string' ? value.$schema : a.dialect;
    record.dialect = inheritedDialect;
    if (![DIALECT, OAS_DIALECT].includes(inheritedDialect)) { record.status = 'unsupported'; record.gaps.push('Schema overrides the document with an unsupported dialect.'); return identity; }
    let valid = false;
    try { valid = !!ajv.validateSchema(typeof value === 'boolean' ? value : { ...value, $schema: DIALECT }); } catch { /* no raw errors or schema values in diagnostics */ }
    if (!valid) { record.status = 'unsupported'; record.gaps.push('Schema does not validate against the supported JSON Schema meta-schema.'); statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-schema', 'A native schema failed meta-schema validation.'); return identity; }
    function walk(node: unknown, current: string): unknown {
      if (typeof node === 'boolean') return node;
      if (!object(node)) return node;
      const out: Record<string, unknown> = Object.create(null);
      for (const [key, child] of Object.entries(node)) {
        const childAt = pointer(current, key);
        if (key === '$id') {
          if (current !== '' || a.kind === 'native-openapi') record.gaps.push('Nested or embedded schema resource IDs are not projected.');
          continue;
        }
        if (key === '$dynamicRef' || key === '$dynamicAnchor' || key === '$anchor') { record.gaps.push('Named anchors and dynamic reference semantics are not projected.'); continue; }
        if (key === '$schema' && ![DIALECT, OAS_DIALECT].includes(String(child))) record.gaps.push('Nested schema dialect is unsupported.');
        if (key === '$ref') {
          const target = typeof child === 'string' ? locate(a, child) : undefined;
          if (!target || !schemaValue(target.value)) {
            record.gaps.push('Reference is unresolved, unsupported, or outside the explicitly selected artifact set.');
            diagnostic(a.file, 'unresolved-native-reference', 'A schema reference could not be resolved within explicitly selected artifacts.');
          } else {
            const targetId = ensureSchema(target.artifact, target.pointer, target.value, 'declaration');
            out[key] = targetId; dependencies.get(identity)!.add(targetId);
          }
        } else if (schemaMaps.has(key) && object(child)) {
          out[key] = Object.fromEntries(Object.entries(child).map(([name, nested]) => [name, walk(nested, pointer(childAt, name))]));
        } else if (schemaArrays.has(key) && Array.isArray(child)) out[key] = child.map((nested, index) => walk(nested, pointer(childAt, String(index))));
        else if (schemaSingles.has(key)) out[key] = walk(child, childAt);
        else out[key] = child;
      }
      return out;
    }
    const projected = walk(value, at);
    if (record.gaps.length) { record.status = 'unsupported'; }
    else record.schema = typeof projected === 'boolean' ? projected ? {} : { not: {} } : projected as JsonSchema;
    return identity;
  }

  function resolveObject(a: Artifact, at: string, value: unknown, gaps: string[], seen = new Set<string>()): Location | undefined {
    if (!object(value)) { gaps.push('OpenAPI object has an invalid shape.'); statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-openapi', 'An OpenAPI object has an invalid shape.'); return; }
    if (!('$ref' in value)) return { artifact: a, pointer: at, value };
    const target = typeof value.$ref === 'string' ? locate(a, value.$ref) : undefined;
    const key = target && `${target.artifact.file}#${target.pointer}`;
    if (!target || !key || seen.has(key)) { gaps.push('OpenAPI object reference is unresolved or cyclic.'); diagnostic(a.file, 'unresolved-native-reference', 'An OpenAPI reference could not be resolved within explicitly selected artifacts.'); return; }
    if (Object.keys(value).some(key => !['$ref', 'summary', 'description'].includes(key))) gaps.push('Reference siblings require review; original object retained in source artifact.');
    seen.add(key); return resolveObject(target.artifact, target.pointer, target.value, gaps, seen);
  }

  function importOpenApi(a: Artifact) {
    const data = a.data;
    if (object(data.components) && object(data.components.schemas)) for (const [name, value] of Object.entries(data.components.schemas)) ensureSchema(a, `/components/schemas/${escape(name)}`, value, 'declaration');
    if (data.webhooks !== undefined) diagnostic(a.file, 'unsupported-native-webhooks', 'OpenAPI webhooks remain in the source artifact and are not emitted as HTTP paths.');
    for (const [route, rawItem] of Object.entries(object(data.paths) ? data.paths : {})) {
      if (route.startsWith('x-')) continue;
      const itemGaps: string[] = [];
      const itemLocation = resolveObject(a, `/paths/${escape(route)}`, rawItem, itemGaps);
      if (!itemLocation || !object(itemLocation.value)) continue;
      const item = itemLocation.value;
      for (const [method, rawOperation] of Object.entries(item)) {
        if (!methods.has(method)) continue;
        const gaps = [...itemGaps, 'Imported declaration does not establish deployment or runtime conformance.'];
        if (!object(rawOperation) || !object(rawOperation.responses) || !Object.keys(rawOperation.responses).some(key => !key.startsWith('x-')) || !route.startsWith('/')) {
          statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-openapi', 'An HTTP operation requires a valid path and response map.'); continue;
        }
        const at = pointer(itemLocation.pointer, method);
        const op: Operation = { id: id(a, `/paths/${escape(route)}/${method}`, 'http'), kind: 'http', name: `${method.toUpperCase()} ${route}`, direction: 'inbound', owner: request.repository.id, method: method.toUpperCase(), path: route, responses: [], requests: [], status: 'partial', gaps, evidence: [evidence(a, `/paths/${escape(route)}/${method}`)], details: { sourceFormat: 'openapi-3.1', sourcePointer: at } };
        if (itemLocation.artifact !== a) op.evidence.push(evidence(itemLocation.artifact, at));
        const servers = rawOperation.servers ?? item.servers ?? data.servers;
        if (Array.isArray(servers) && servers.length === 1 && object(servers[0]) && typeof servers[0].url === 'string') {
          try { const server = new URL(servers[0].url); if (!['http:', 'https:'].includes(server.protocol) || server.username || server.password || server.search || server.hash || /[{}]/.test(servers[0].url)) throw new Error(); op.server = server.href.replace(/\/$/, ''); }
          catch { gaps.push('Server URL is relative, templated, or unsuitable for projection.'); }
        } else gaps.push('Server location is absent or has multiple alternatives; no server was selected.');
        if (item.parameters !== undefined || rawOperation.parameters !== undefined) gaps.push('Parameter schemas, styles, and requiredness remain in the original OpenAPI artifact.');
        if (data.security !== undefined || rawOperation.security !== undefined) gaps.push('Security requirements remain in the original OpenAPI artifact.');
        if (rawOperation.callbacks !== undefined) gaps.push('Callbacks remain in the original OpenAPI artifact.');
        function content(location: Location, value: unknown, role: 'input' | 'output'): Array<{ mediaType: string; schemaId?: string }> {
          if (value === undefined) return [];
          if (!object(value)) { statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-openapi', 'An OpenAPI content map has an invalid shape.'); return []; }
          const rows: Array<{ mediaType: string; schemaId?: string }> = [];
          for (const [mediaType, rawMedia] of Object.entries(value)) {
            if (mediaType.startsWith('x-')) continue;
            if (!object(rawMedia) || !mediaType.includes('/')) { statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-openapi', 'An OpenAPI media type entry has an invalid shape.'); continue; }
            const schemaAt = `${location.pointer}/content/${escape(mediaType)}/schema`;
            const schemaId = 'schema' in rawMedia ? ensureSchema(location.artifact, schemaAt, rawMedia.schema, role) : undefined;
            if (rawMedia.encoding !== undefined) gaps.push('Media type encoding remains in the original OpenAPI artifact.');
            rows.push({ mediaType, ...(schemaId ? { schemaId } : {}) });
          }
          return rows;
        }
        if (rawOperation.requestBody !== undefined) {
          const location = resolveObject(itemLocation.artifact, `${at}/requestBody`, rawOperation.requestBody, gaps);
          if (location && object(location.value)) {
            if (!object(location.value.content) || (location.value.required !== undefined && typeof location.value.required !== 'boolean')) { statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-openapi', 'A request body requires a content map and boolean requiredness.'); }
            else op.requests = content(location, location.value.content, 'input').map(row => ({ ...row, required: object(location.value) && location.value.required === true }));
          }
        }
        for (const [status, rawResponse] of Object.entries(rawOperation.responses)) {
          if (status.startsWith('x-')) continue;
          if (!/^(?:[1-5][0-9]{2}|[1-5]XX|default)$/.test(status)) { statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-openapi', 'An HTTP response status is invalid.'); continue; }
          const location = resolveObject(itemLocation.artifact, `${at}/responses/${escape(status)}`, rawResponse, gaps);
          if (!location || !object(location.value)) continue;
          if (typeof location.value.description !== 'string') { statuses.set(a.file, 'failed'); diagnostic(a.file, 'invalid-native-openapi', 'An HTTP response requires a description.'); continue; }
          const rows = content(location, location.value.content, 'output');
          op.responses.push(...(rows.length ? rows.map(row => ({ status, ...row })) : [{ status }]));
          if (location.value.headers !== undefined || location.value.links !== undefined) gaps.push('Response headers and links remain in the original OpenAPI artifact.');
        }
        result.operations.push(op);
      }
    }
  }

  for (const a of artifacts.values()) {
    if (a.kind === 'native-json-schema') ensureSchema(a, '', a.data, 'declaration');
    else importOpenApi(a);
  }
  // Reference closure must be exportable, including transitive external dependencies.
  let changed = true;
  while (changed) {
    changed = false;
    for (const [identity, record] of records) if (record.schema && [...dependencies.get(identity)!].some(target => !records.get(target)?.schema)) {
      delete record.schema; record.status = 'unsupported'; record.gaps.push('A referenced schema has no supported projection.'); changed = true;
    }
  }
  for (const record of records.values()) result.schemas.push(record);
  for (const op of result.operations) {
    const references = [...(op.requests || []).map(row => row.schemaId), ...op.responses.map(row => row.schemaId)].filter((value): value is string => !!value);
    for (const target of new Set(references)) {
      result.relationships.push({ source: op.id, target, kind: 'references', evidence: op.evidence });
      if (!records.get(target)?.schema) op.gaps.push('An operation schema is unresolved or unsupported; inspect the original artifact.');
    }
  }
  for (const [source, targets] of dependencies) for (const target of targets) result.relationships.push({ source, target, kind: 'references', evidence: records.get(source)!.evidence });
  result.files = [...statuses].map(([file, status]) => ({ path: file, status }));
  result.schemas.sort((a, b) => a.id.localeCompare(b.id)); result.operations.sort((a, b) => a.id.localeCompare(b.id));
  result.relationships.sort((a, b) => `${a.source}:${a.target}`.localeCompare(`${b.source}:${b.target}`));
  return result;
}
