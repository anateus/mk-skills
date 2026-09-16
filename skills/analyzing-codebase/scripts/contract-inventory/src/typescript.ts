import ts from 'typescript';
import path from 'node:path';
import fs from 'node:fs';
import type { AdapterResult, Evidence, JsonSchema, Operation, ScanRequest } from './types.js';

const DIALECT = 'https://json-schema.org/draft/2020-12/schema';
type Projection = { schema: JsonSchema; gaps: string[]; optional?: boolean };
const unknown = (gap: string): Projection => ({ schema: {}, gaps: [gap] });
const key = (node: ts.PropertyName | ts.BindingName): string | undefined =>
  ts.isIdentifier(node) || ts.isStringLiteral(node) || ts.isNumericLiteral(node) ? node.text : undefined;
function unwrap(node: ts.Expression): ts.Expression {
  while (ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node) || ts.isNonNullExpression(node)) node = node.expression;
  return node;
}
function property(node: ts.Node | undefined, name: string): ts.Expression | undefined {
  if (!node || !ts.isObjectLiteralExpression(node)) return undefined;
  const p = node.properties.find(p => p.name && key(p.name) === name);
  return p && ts.isPropertyAssignment(p) ? p.initializer : p && ts.isShorthandPropertyAssignment(p) ? p.name : undefined;
}
function literal(node: ts.Node | undefined): string | number | boolean | null | undefined {
  if (!node) return undefined;
  if (ts.isStringLiteralLike(node)) return node.text;
  if (ts.isNumericLiteral(node)) return Number(node.text);
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (node.kind === ts.SyntaxKind.NullKeyword) return null;
  return undefined;
}

/** Static-only: no target imports, module evaluation, network calls, or request values. */
export function scanTypeScript(request: ScanRequest): AdapterResult {
  const result: AdapterResult = {
    protocolVersion: 1,
    adapter: { name: 'typescript-static', version: '0.1.0', capabilities: ['typescript-declarations', 'local-type-references', 'zod-static-subset', 'ts-rest-routes', 'fetch-axios-candidates', 'tool-registries'], limitations: ['Only selected source files are read; relative imports resolve within that set. Package and tsconfig aliases remain unresolved.', 'Static registration does not establish deployment or reachability.', 'Dynamic routes, arbitrary wrappers, refinements and serialization need review.', 'Class models, declaration merging, generic expansion and inherited fields are not fully projected.'] },
    declarations: [], schemas: [], operations: [], relationships: [], files: [], diagnostics: [],
  };
  const files = [...new Set(request.files)].sort();
  const selected = new Set(files.map(f => path.resolve(request.repository.root, f)));
  const options: ts.CompilerOptions = { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.NodeNext, moduleResolution: ts.ModuleResolutionKind.NodeNext, skipLibCheck: true, noEmit: true, noLib: true, types: [] };
  const host = ts.createCompilerHost(options);
  // Bound reads to selected sources. Import resolution must not pull a monorepo's
  // entire dependency graph or package declarations into a bounded scan.
  host.resolveModuleNames = (names, containingFile) => names.map(name => {
    if (!name.startsWith('.')) return undefined;
    const base = path.resolve(path.dirname(containingFile), name);
    const stem = base.replace(/\.[cm]?js$/, '');
    const candidate = [base, ...['.ts', '.tsx', '.mts', '.cts', '.d.ts'].map(ext => stem + ext), path.join(base, 'index.ts')].find(file => selected.has(file));
    return candidate ? { resolvedFileName: candidate, extension: candidate.endsWith('.tsx') ? ts.Extension.Tsx : candidate.endsWith('.mts') ? ts.Extension.Mts : candidate.endsWith('.cts') ? ts.Extension.Cts : ts.Extension.Ts } : undefined;
  });
  const program = ts.createProgram([...selected], options, host);
  const checker = program.getTypeChecker();
  const sources = program.getSourceFiles().filter(f => selected.has(path.resolve(f.fileName)));
  const relative = (n: ts.Node) => path.relative(request.repository.root, n.getSourceFile().fileName).split(path.sep).join('/');
  const evidence = (n: ts.Node, basis: Evidence['basis'] = 'declaration', symbol?: string): Evidence => ({ file: relative(n), line: n.getSourceFile().getLineAndCharacterOfPosition(n.getStart()).line + 1, basis, ...(symbol ? { symbol } : {}) });
  const identities = new WeakMap<ts.Node, Map<string, string>>();
  const identityCounts = new Map<string, number>();
  const id = (n: ts.Node, kind: string, name: string): string => {
    const localKey = `${kind}:${name}`; const cached = identities.get(n)?.get(localKey); if (cached) return cached;
    const scopes: string[] = [];
    for (let parent = n.parent; parent; parent = parent.parent) if ((ts.isFunctionDeclaration(parent) || ts.isClassDeclaration(parent) || ts.isModuleDeclaration(parent)) && parent.name) scopes.unshift(parent.name.text);
    const base = `${request.repository.id}:typescript:${relative(n)}:${kind}:${encodeURIComponent([...scopes, name].join('.'))}`;
    const count = (identityCounts.get(base) ?? 0) + 1; identityCounts.set(base, count);
    const value = count === 1 ? base : `${base}:duplicate:${count}`;
    const nodeIds = identities.get(n) ?? new Map<string, string>(); nodeIds.set(localKey, value); identities.set(n, nodeIds); return value;
  };
  const declarations = new Map<ts.Node, string>();
  const schemaIds = new Map<ts.Node, string>();
  const zodNames = new Map<ts.SourceFile, Set<string>>();
  const contractNames = new Map<ts.SourceFile, Set<string>>();
  const axiosNames = new Map<ts.SourceFile, Set<string>>();
  const mountNames = new Map<ts.SourceFile, Set<string>>();
  const variables = new Map<ts.Node, ts.Expression>();
  const functions = new Map<ts.Node, ts.FunctionLikeDeclaration>();
  const routerOperations = new Map<ts.Node, Operation[]>();
  const resolve = (n: ts.Node): ts.Node | undefined => {
    let symbol = checker.getSymbolAtLocation(n);
    if (symbol && symbol.flags & ts.SymbolFlags.Alias) symbol = checker.getAliasedSymbol(symbol);
    return symbol?.valueDeclaration ?? symbol?.declarations?.[0];
  };
  const visit = (n: ts.Node, fn: (n: ts.Node) => void) => { fn(n); n.forEachChild(c => visit(c, fn)); };
  function isZod(node: ts.Expression, sf: ts.SourceFile, seen = new Set<ts.Node>()): boolean {
    node = unwrap(node);
    if (seen.has(node)) return false;
    seen.add(node);
    if (ts.isIdentifier(node)) {
      if (zodNames.get(sf)?.has(node.text)) return true;
      const d = resolve(node); const init = d && variables.get(d);
      return !!init && isZod(init, init.getSourceFile(), seen);
    }
    return ts.isCallExpression(node) ? isZod(node.expression, sf, seen) : ts.isPropertyAccessExpression(node) ? isZod(node.expression, sf, seen) : false;
  }
  for (const sf of sources) {
    zodNames.set(sf, new Set()); contractNames.set(sf, new Set()); axiosNames.set(sf, new Set()); mountNames.set(sf, new Set());
    for (const st of sf.statements) {
      if (ts.isImportDeclaration(st) && ts.isStringLiteral(st.moduleSpecifier)) {
        const mod = st.moduleSpecifier.text; const clause = st.importClause;
        if (!checker.getSymbolAtLocation(st.moduleSpecifier)) result.diagnostics.push({ ...evidence(st), code: 'unresolved-import', message: 'Import does not resolve within selected source files; imported contracts may be missing.' });
        const names = clause?.namedBindings && ts.isNamedImports(clause.namedBindings) ? clause.namedBindings.elements : [];
        if (/^zod(?:\/|$)/.test(mod)) {
          if (clause?.name) zodNames.get(sf)!.add(clause.name.text);
          for (const n of names) if (['z', 'default'].includes(n.propertyName?.text ?? n.name.text)) zodNames.get(sf)!.add(n.name.text);
          if (clause?.namedBindings && ts.isNamespaceImport(clause.namedBindings)) zodNames.get(sf)!.add(clause.namedBindings.name.text);
        }
        if (mod === 'axios' && clause?.name) axiosNames.get(sf)!.add(clause.name.text);
        for (const n of names) {
          const imported = n.propertyName?.text ?? n.name.text;
          if (mod === '@ts-rest/core' && imported === 'initContract') contractNames.get(sf)!.add(n.name.text);
          if (mod.startsWith('@ts-rest/') && imported === 'createExpressEndpoints') mountNames.get(sf)!.add(n.name.text);
        }
      }
    }
    visit(sf, n => {
      if (ts.isVariableDeclaration(n) && n.initializer) variables.set(n, unwrap(n.initializer));
      if (ts.isFunctionDeclaration(n) && n.name) functions.set(n, n);
      if (ts.isVariableDeclaration(n) && n.initializer && (ts.isArrowFunction(n.initializer) || ts.isFunctionExpression(n.initializer))) functions.set(n, n.initializer);
    });
  }
  for (const sf of sources) visit(sf, n => {
    if (ts.isInterfaceDeclaration(n) || ts.isTypeAliasDeclaration(n) || (ts.isVariableDeclaration(n) && n.initializer && isZod(n.initializer, sf))) {
      const name = key(n.name); if (!name) return;
      declarations.set(n, id(n, 'declaration', name)); schemaIds.set(n, id(n, 'schema', name));
    }
  });
  function typeProjection(node: ts.TypeNode | undefined, depth = 0): Projection {
    if (!node || depth > 15) return unknown('Type has no supported static projection.');
    const prim: Record<number, string> = { [ts.SyntaxKind.StringKeyword]: 'string', [ts.SyntaxKind.NumberKeyword]: 'number', [ts.SyntaxKind.BooleanKeyword]: 'boolean', [ts.SyntaxKind.NullKeyword]: 'null' };
    if (prim[node.kind]) return { schema: { type: prim[node.kind] }, gaps: [] };
    if (ts.isLiteralTypeNode(node)) { const value = literal(node.literal); return value !== undefined ? { schema: { const: value }, gaps: [] } : unknown('Unsupported literal type.'); }
    if (ts.isParenthesizedTypeNode(node)) return typeProjection(node.type, depth + 1);
    if (ts.isArrayTypeNode(node)) { const p = typeProjection(node.elementType, depth + 1); return { schema: { type: 'array', items: p.schema }, gaps: p.gaps }; }
    if (ts.isUnionTypeNode(node)) { const ps = node.types.map(t => typeProjection(t, depth + 1)); return { schema: { anyOf: ps.map(p => p.schema) }, gaps: ps.flatMap(p => p.gaps) }; }
    if (ts.isIntersectionTypeNode(node)) { const ps = node.types.map(t => typeProjection(t, depth + 1)); return { schema: { allOf: ps.map(p => p.schema) }, gaps: ps.flatMap(p => p.gaps) }; }
    if (ts.isTypeLiteralNode(node)) return membersProjection(node.members, depth + 1);
    if (ts.isTypeReferenceNode(node)) {
      const name = node.typeName.getText();
      if ((name === 'Array' || name === 'ReadonlyArray') && node.typeArguments?.length === 1) { const p = typeProjection(node.typeArguments[0], depth + 1); return { schema: { type: 'array', items: p.schema }, gaps: p.gaps }; }
      const declaration = resolve(node.typeName); const ref = declaration && schemaIds.get(declaration);
      if (ref && !node.typeArguments?.length) return { schema: { $ref: ref }, gaps: [] };
      return unknown(node.typeArguments?.length ? 'Generic instantiation requires semantic expansion.' : 'Referenced type is outside the supported selected declaration set.');
    }
    return unknown(`Unsupported TypeScript type syntax: ${ts.SyntaxKind[node.kind]}.`);
  }
  function membersProjection(members: ts.NodeArray<ts.TypeElement>, depth: number): Projection {
    const properties: Record<string, JsonSchema> = {}; const required: string[] = []; const gaps: string[] = [];
    for (const member of members) {
      if (!ts.isPropertySignature(member) || !member.name || key(member.name) === undefined) { gaps.push('Method, index signature, or computed member needs review.'); continue; }
      const name = key(member.name)!; const p = typeProjection(member.type, depth + 1); properties[name] = p.schema; gaps.push(...p.gaps); if (!member.questionToken) required.push(name);
    }
    return { schema: { type: 'object', properties, ...(required.length ? { required } : {}) }, gaps };
  }
  function zodProjection(expression: ts.Expression, depth = 0): Projection {
    const node = unwrap(expression); if (depth > 20) return unknown('Zod nesting exceeds static projection limit.');
    if (ts.isIdentifier(node)) { const d = resolve(node); const ref = d && schemaIds.get(d); return ref ? { schema: { $ref: ref }, gaps: [] } : unknown('Schema reference is unresolved.'); }
    if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression)) return unknown('Unsupported schema expression.');
    const method = node.expression.name.text; const base = node.expression.expression; const args = node.arguments;
    if (ts.isIdentifier(base) && zodNames.get(node.getSourceFile())?.has(base.text)) {
      if (['string', 'number', 'boolean', 'null'].includes(method)) return { schema: { type: method }, gaps: [] };
      if (['any', 'unknown'].includes(method)) return { schema: {}, gaps: [] };
      if (method === 'literal') { const value = literal(args[0]); return value !== undefined ? { schema: { const: value }, gaps: [] } : unknown('Nonliteral Zod literal.'); }
      if (method === 'enum' && args[0] && ts.isArrayLiteralExpression(args[0])) { const values = args[0].elements.map(literal); return values.every(v => typeof v === 'string') ? { schema: { type: 'string', enum: values }, gaps: [] } : unknown('Dynamic Zod enum.'); }
      if (method === 'array' && args[0]) { const p = zodProjection(args[0], depth + 1); return { schema: { type: 'array', items: p.schema }, gaps: p.gaps }; }
      if ((method === 'union' || method === 'discriminatedUnion') && args[method === 'union' ? 0 : 1] && ts.isArrayLiteralExpression(args[method === 'union' ? 0 : 1])) {
        const ps = (args[method === 'union' ? 0 : 1] as ts.ArrayLiteralExpression).elements.map(e => zodProjection(e, depth + 1)); return { schema: { anyOf: ps.map(p => p.schema) }, gaps: ps.flatMap(p => p.gaps) };
      }
      if (method === 'object' && args[0] && ts.isObjectLiteralExpression(args[0])) {
        const properties: Record<string, JsonSchema> = {}; const required: string[] = []; const gaps: string[] = ['Zod object serialization and unknown-key stripping are not represented.'];
        for (const prop of args[0].properties) {
          if (!ts.isPropertyAssignment(prop) || key(prop.name) === undefined) { gaps.push('Computed or spread Zod property needs review.'); continue; }
          const name = key(prop.name)!; const p = zodProjection(prop.initializer, depth + 1); properties[name] = p.schema; gaps.push(...p.gaps); if (!p.optional) required.push(name);
        }
        return { schema: { type: 'object', properties, ...(required.length ? { required } : {}) }, gaps };
      }
      return unknown(`Unsupported Zod constructor: ${method}.`);
    }
    const p = zodProjection(base, depth + 1);
    if (method === 'optional') return { ...p, optional: true };
    if (method === 'nullable' || method === 'nullish') return { ...p, schema: { anyOf: [p.schema, { type: 'null' }] }, optional: method === 'nullish' || p.optional };
    if (method === 'default') return { ...p, optional: true, gaps: [...p.gaps, 'Default generation is not represented.'] };
    if (method === 'int') return { ...p, schema: { ...p.schema, type: 'integer' } };
    if (method === 'min' || method === 'max') {
      const value = literal(args[0]); const t = p.schema.type;
      const field = t === 'string' ? (method === 'min' ? 'minLength' : 'maxLength') : t === 'array' ? (method === 'min' ? 'minItems' : 'maxItems') : t === 'number' || t === 'integer' ? (method === 'min' ? 'minimum' : 'maximum') : undefined;
      if (typeof value === 'number' && field) return { ...p, schema: { ...p.schema, [field]: value } };
    }
    return { ...p, gaps: [...p.gaps, `Zod ${method} behavior is not represented; preserve native validation and serialization.`] };
  }
  function addSchema(node: ts.Node, name: string, projection: Projection, role: 'declaration' | 'input' | 'output' = 'declaration'): string {
    const sid = schemaIds.get(node) ?? id(node, 'schema', name);
    if (!result.schemas.some(s => s.id === sid)) result.schemas.push({ id: sid, name, role, schema: { $schema: DIALECT, $id: sid, ...projection.schema }, dialect: DIALECT, status: projection.gaps.length ? 'partial' : 'resolved', gaps: [...new Set(projection.gaps)], evidence: [evidence(node)] });
    return sid;
  }
  for (const [node, did] of declarations) {
    const typed = node as ts.InterfaceDeclaration | ts.TypeAliasDeclaration | ts.VariableDeclaration; const name = key(typed.name)!;
    let p = ts.isInterfaceDeclaration(typed) ? membersProjection(typed.members, 0) : ts.isTypeAliasDeclaration(typed) ? typeProjection(typed.type) : zodProjection(typed.initializer!);
    if ((ts.isInterfaceDeclaration(typed) || ts.isTypeAliasDeclaration(typed)) && typed.typeParameters?.length) p.gaps.push('Generic parameters are not instantiated.');
    if (ts.isInterfaceDeclaration(typed) && typed.heritageClauses?.length) p.gaps.push('Inherited interface members require semantic expansion.');
    const sid = addSchema(node, name, p);
    let modifierNode: ts.Node = typed; if (ts.isVariableDeclaration(typed)) modifierNode = typed.parent.parent;
    result.declarations.push({ id: did, name, kind: ts.isVariableDeclaration(typed) ? 'zod-schema' : ts.isInterfaceDeclaration(typed) ? 'interface' : 'type-alias', language: 'typescript', exported: ts.canHaveModifiers(modifierNode) && !!ts.getModifiers(modifierNode)?.some(m => m.kind === ts.SyntaxKind.ExportKeyword), status: p.gaps.length ? 'partial' : 'resolved', schemaId: sid, gaps: [...new Set(p.gaps)], evidence: [evidence(node, 'declaration', name)] });
    visit(node, refNode => { if (ts.isTypeReferenceNode(refNode)) { const target = resolve(refNode.typeName); const targetId = target && declarations.get(target); if (targetId && targetId !== did) result.relationships.push({ source: did, target: targetId, kind: 'references', evidence: [evidence(refNode)] }); } });
  }
  const schemaExpression = (expression: ts.Expression | undefined, name: string, role: 'input' | 'output'): string | undefined => {
    if (!expression) return undefined;
    if (ts.isIdentifier(expression)) { const d = resolve(expression); const ref = d && schemaIds.get(d); if (ref) return ref; }
    return addSchema(expression, name, isZod(expression, expression.getSourceFile()) ? zodProjection(expression) : unknown('Contract schema expression requires review.'), role);
  };
  function routerRoot(expression: ts.Expression): boolean {
    expression = unwrap(expression);
    if (ts.isIdentifier(expression)) { const d = resolve(expression); const init = d && variables.get(d); return !!init && ts.isCallExpression(init) && ts.isIdentifier(init.expression) && !!contractNames.get(init.getSourceFile())?.has(init.expression.text); }
    return false;
  }
  for (const sf of sources) visit(sf, n => {
    if (!ts.isCallExpression(n) || !ts.isPropertyAccessExpression(n.expression) || n.expression.name.text !== 'router' || !routerRoot(n.expression.expression)) return;
    const routerDecl = ts.isVariableDeclaration(n.parent) ? n.parent : undefined;
    const rootName = routerDecl ? key(routerDecl.name) ?? 'router' : `router@${evidence(n).line}`;
    const options = n.arguments[1]; const prefixValue = literal(property(options, 'pathPrefix')); const prefix = typeof prefixValue === 'string' ? prefixValue : '';
    const routes = n.arguments[0]; if (!routes || !ts.isObjectLiteralExpression(routes)) { result.diagnostics.push({ ...evidence(n), code: 'dynamic-router', message: 'Router entries are not a static object.' }); return; }
    for (const route of routes.properties) {
      if (!ts.isPropertyAssignment(route) || !ts.isObjectLiteralExpression(route.initializer)) { result.diagnostics.push({ ...evidence(route), code: 'unresolved-router-entry', message: 'Nested or spread router entry needs registration tracing.' }); continue; }
      const name = key(route.name); if (!name) continue;
      const methodExpression = property(route.initializer, 'method');
      const method = literal(methodExpression); const routePath = literal(property(route.initializer, 'path'));
      if (!methodExpression && !property(route.initializer, 'path')) { result.diagnostics.push({ ...evidence(route), code: 'unresolved-router-entry', message: 'Router entry has no directly declared method or path; nested registration requires tracing.' }); continue; }
      const gaps = ['Mount state is unknown until a supported registration is found.', 'Middleware, authentication, query/header serialization and runtime behavior require review.'];
      const op: Operation = { id: id(n, 'http', `${rootName}.${name}`), kind: 'http', name: `${rootName}.${name}`, direction: 'inbound', ...(typeof method === 'string' ? { method: method.toUpperCase() } : {}), ...(typeof routePath === 'string' && !(options && property(options, 'pathPrefix') && typeof prefixValue !== 'string') ? { path: `${prefix}${routePath}` } : {}), responses: [], status: 'partial', gaps, evidence: [evidence(route, 'declaration', `${rootName}.${name}`)] };
      if (typeof method !== 'string') gaps.push('HTTP method is dynamic or unresolved.');
      if (typeof routePath !== 'string') gaps.push('Route path is dynamic.');
      if (options && property(options, 'pathPrefix') && typeof prefixValue !== 'string') gaps.push('Router path prefix is dynamic.');
      op.requestSchemaId = schemaExpression(property(route.initializer, 'body'), `${rootName}.${name}.request`, 'input');
      if (op.requestSchemaId) gaps.push('Request content type is not statically established.');
      const responses = property(route.initializer, 'responses');
      if (responses && ts.isObjectLiteralExpression(responses)) for (const response of responses.properties) {
        if (ts.isPropertyAssignment(response) && key(response.name)) op.responses.push({ status: key(response.name)!, ...(response.initializer.kind === ts.SyntaxKind.NullKeyword ? {} : { schemaId: schemaExpression(response.initializer, `${rootName}.${name}.response.${key(response.name)}`, 'output') }) });
      } else gaps.push('Response status map is unresolved.');
      result.operations.push(op); if (routerDecl) { const ops = routerOperations.get(routerDecl) ?? []; ops.push(op); routerOperations.set(routerDecl, ops); }
    }
  });
  for (const sf of sources) visit(sf, n => {
    if (!ts.isCallExpression(n) || !ts.isIdentifier(n.expression) || !mountNames.get(sf)?.has(n.expression.text) || !n.arguments[0]) return;
    const d = resolve(n.arguments[0]); if (!d) return;
    for (const op of routerOperations.get(d) ?? []) { op.mounted = true; op.gaps = op.gaps.filter(g => !g.startsWith('Mount state')); op.evidence.push(evidence(n, 'registration')); op.gaps.push('Static registration found; deployed reachability and enclosing mount prefixes are unverified.'); }
  });
  function stringValue(expression: ts.Expression | undefined, bindings = new Map<ts.Node, ts.Expression>(), seen = new Set<ts.Node>()): string | undefined {
    if (!expression) return undefined; expression = unwrap(expression); if (seen.has(expression)) return undefined; seen.add(expression);
    if (ts.isStringLiteralLike(expression)) return expression.text;
    if (ts.isIdentifier(expression)) { const d = resolve(expression); const init = d && (bindings.get(d) ?? variables.get(d)); return init ? stringValue(init, bindings, seen) : undefined; }
    if (ts.isBinaryExpression(expression) && expression.operatorToken.kind === ts.SyntaxKind.PlusToken) { const left = stringValue(expression.left, bindings, new Set(seen)); const right = stringValue(expression.right, bindings, new Set(seen)); return left !== undefined && right !== undefined ? left + right : undefined; }
    // Dynamic substitutions are deliberately not promoted to proven path parameters.
    return undefined;
  }
  function httpCall(n: ts.CallExpression): { url?: ts.Expression; method?: string; options?: ts.Expression; client: string; base?: string } | undefined {
    const callee = n.expression; const sf = n.getSourceFile();
    if (ts.isIdentifier(callee) && callee.text === 'fetch') return { url: n.arguments[0], method: 'GET', options: n.arguments[1], client: 'fetch' };
    if (ts.isPropertyAccessExpression(callee)) {
      let axios = ts.isIdentifier(callee.expression) && axiosNames.get(sf)?.has(callee.expression.text); let base: string | undefined;
      if (!axios && ts.isIdentifier(callee.expression)) {
        const d = resolve(callee.expression); const init = d && variables.get(d);
        if (init && ts.isCallExpression(init) && ts.isPropertyAccessExpression(init.expression) && init.expression.name.text === 'create' && ts.isIdentifier(init.expression.expression) && axiosNames.get(sf)?.has(init.expression.expression.text)) { axios = true; base = stringValue(property(init.arguments[0], 'baseURL')); }
      }
      if (axios && ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'].includes(callee.name.text)) return { url: n.arguments[0], method: callee.name.text.toUpperCase(), options: n.arguments[['post', 'put', 'patch'].includes(callee.name.text) ? 2 : 1], client: 'axios', base };
    }
    return undefined;
  }
  function emitClient(call: ts.CallExpression, transport: ts.CallExpression, bindings = new Map<ts.Node, ts.Expression>(), wrapper?: string) {
    const info = httpCall(transport); if (!info) return;
    const gaps = ['Client call only; provider guarantees, response statuses and schemas are unknown.', 'Headers, payload values, retries, timeouts and serialization are not extracted.'];
    let method = info.method;
    const explicit = property(info.options, 'method');
    if (info.client === 'fetch' && explicit) { const value = stringValue(explicit, bindings); method = value?.toUpperCase(); if (!method) gaps.push('HTTP method is dynamic.'); }
    if (info.client === 'fetch' && info.options && (!ts.isObjectLiteralExpression(info.options) || info.options.properties.some(p => ts.isSpreadAssignment(p)))) { method = undefined; gaps.push('Fetch options may override the HTTP method.'); }
    const url = stringValue(info.url, bindings); let server: string | undefined; let endpoint: string | undefined;
    if (url !== undefined) {
      try { const parsed = new URL(url, info.base); if (['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password) { server = parsed.origin; endpoint = parsed.pathname; if (parsed.search) gaps.push('Query values omitted; query contract requires review.'); } else gaps.push('URL scheme or credentials prevent safe projection.'); }
      catch { if (url.startsWith('/') && !url.includes('?') && !url.includes('#')) endpoint = url; gaps.push('Server base URL is unresolved.'); }
    } else gaps.push('URL is dynamic or unresolved.');
    const line = evidence(call).line; const pos = call.getSourceFile().getLineAndCharacterOfPosition(call.getStart()).character + 1;
    const name = wrapper ? `${wrapper}@${line}:${pos}` : `${info.client}@${line}:${pos}`;
    result.operations.push({ id: id(call, 'client', name), name, kind: 'http', direction: 'outbound', ...(method ? { method } : {}), ...(server ? { server } : {}), ...(endpoint ? { path: endpoint } : {}), status: 'partial', responses: [], gaps, evidence: [evidence(call, 'static-call'), ...(transport !== call ? [evidence(transport, 'static-call', wrapper)] : [])], details: { client: info.client, ...(wrapper ? { wrapper } : {}) } });
  }
  for (const sf of sources) visit(sf, n => {
    if (ts.isCallExpression(n)) {
      if (httpCall(n)) emitClient(n, n);
      else if (ts.isIdentifier(n.expression)) {
        const d = resolve(n.expression); const fn = d && functions.get(d);
        if (fn?.body) {
          const calls: ts.CallExpression[] = []; visit(fn.body, child => { if (ts.isCallExpression(child) && httpCall(child)) calls.push(child); });
          if (calls.length === 1) {
            const bindings = new Map<ts.Node, ts.Expression>(); fn.parameters.forEach((parameter, index) => { if (n.arguments[index]) bindings.set(parameter, n.arguments[index]); });
            emitClient(n, calls[0], bindings, n.expression.text);
          }
        }
      }
    }
    if (ts.isVariableDeclaration(n) && n.initializer && ts.isIdentifier(n.name) && /(?:tools?_?map|tools?_?registry|tools?_?handlers|tools?_?by_?name)$/i.test(n.name.text)) {
      const initializer = unwrap(n.initializer); if (!ts.isObjectLiteralExpression(initializer)) { result.diagnostics.push({ ...evidence(n, 'registration', n.name.text), code: 'unresolved-registration', message: 'Tool registry is not a static object; registration coverage is incomplete.' }); return; }
      for (const entry of initializer.properties) {
        const name = entry.name && key(entry.name); if (!name) { result.diagnostics.push({ ...evidence(entry, 'registration', n.name.text), code: 'unresolved-registration', message: 'Computed or spread registry entry needs registration tracing.' }); continue; }
        const value = ts.isPropertyAssignment(entry) ? entry.initializer : ts.isShorthandPropertyAssignment(entry) ? entry.name : undefined;
        const handler = value && ts.isObjectLiteralExpression(value) ? property(value, 'handler') : value;
        if (!handler || !(ts.isIdentifier(handler) || ts.isPropertyAccessExpression(handler))) { result.diagnostics.push({ ...evidence(entry, 'registration', n.name.text), code: 'unresolved-registration', message: 'Nested, inline or dynamic registry entry needs handler and provider registration tracing.' }); continue; }
        result.operations.push({ id: id(entry, 'tool', `${n.name.text}.${name}`), kind: 'tool', name: `${n.name.text}.${name}`, direction: 'internal', responses: [], status: 'partial', gaps: ['Static registry entry; provider identity, dispatch reachability and behavioral contract require tracing.'], evidence: [evidence(entry, 'registration', n.name.text)], details: { registry: n.name.text, handler: ts.isIdentifier(handler) ? handler.text : handler.name.text } });
      }
    }
  });
  for (const file of files) {
    const full = path.resolve(request.repository.root, file); const sf = sources.find(s => path.resolve(s.fileName) === full);
    if (!sf) { result.files.push({ path: file, status: fs.existsSync(full) ? 'unsupported' : 'failed' }); result.diagnostics.push({ file, code: 'source-unavailable', message: 'Source could not be parsed as a supported TypeScript file.' }); continue; }
    const diagnostics = program.getSyntacticDiagnostics(sf); result.files.push({ path: file, status: diagnostics.length ? 'failed' : 'examined' });
    for (const d of diagnostics) result.diagnostics.push({ file, line: d.start === undefined ? undefined : sf.getLineAndCharacterOfPosition(d.start).line + 1, code: `TS${d.code}`, message: 'TypeScript syntax error; file results may be incomplete.' });
  }
  // Stable ordering across filesystem traversal and diagnostics. No target text is emitted.
  result.declarations.sort((a,b) => a.id.localeCompare(b.id)); result.schemas.sort((a,b) => a.id.localeCompare(b.id)); result.operations.sort((a,b) => a.id.localeCompare(b.id));
  return result;
}
