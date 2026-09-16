# For contracts

Inventory declarations and the boundaries that use them: schemas, types, inbound endpoints, outbound API calls, tool registrations, messages, and storage interfaces. Keep declared shapes, wire behavior, client expectations, and runtime validation distinguishable. A type declaration alone does not establish an active boundary.

Read [workspace and provenance](workspace.md) and [inventory interpretation](contract-inventory.md). Reuse a current inventory for `for-testing` or `for-transitioning`; refresh it when roots, revisions, dependencies, filters, or adapter versions change.

## Establish scope

Record each repository with a stable local ID, root, analyzed revision, and included paths. Include known consumers and shared packages when the decision crosses repositories. Start with broad file and entrypoint discovery, then resolve the requested capability deeply. Keep excluded files, unsupported languages and constructs, unresolved imports, parse failures, and unexamined boundaries visible in coverage.

For the Domu transition, monorepo is a primary inventory root alongside Kiban and Kanban. Survey monorepo services and shared packages; use `services/calls/process-tools/` plus its shared-type dependencies as the first detailed legacy pilot. Trace its provider variants and callers before matching it to a replacement. A bounded pilot does not establish full monorepo coverage.

## Run the static helper

The helper lives at `scripts/contract-inventory/` relative to this skill directory. Set up its isolated dependencies there, without changing the target repositories:

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build
node dist/cli.js scan \
  --root monorepo=/absolute/path/to/monorepo \
  --root kiban=/absolute/path/to/kiban \
  --root kanban=/absolute/path/to/kanban \
  --out /absolute/path/to/analysis/contracts
```

Repeat `--include path` to limit relative paths across all roots, or use `--include ID:path` for one root. When using filters, supply a matching scope for every root; `--include ID:.` selects that root broadly. These are path prefixes, not glob patterns. Record filters with the output and review their effect on each root's coverage. Use `--python /absolute/path/to/python3` when the default Python executable is unsuitable.

The helper skips tests, fixtures, docs, generated and dependency directories, symlinks, Git-ignored files, and source files over 2 MiB. Include filters do not override those exclusions. Inspect excluded declarations or consumers separately when the decision needs them. Choose a dedicated generated-output directory; `manifest.json` identifies its managed contents. Keep agent annotations outside that directory.

The helper uses the TypeScript compiler and Python's standard-library AST. It discovers bounded declaration, schema, route, registration, and HTTP client patterns without importing target modules or starting services. TypeScript resolution follows supported `tsconfig` aliases and workspace package exports only to selected source files; coverage records the configuration hashes. Include shared packages explicitly when their types matter.

Use `--artifact ID:relative/file.json` to import an existing JSON Schema 2020-12 or OpenAPI 3.1 document. Artifacts are explicitly selected and may live in directories excluded from source discovery. References resolve only within the selected artifact set; select each referenced document separately. Standalone JSON Schema needs an explicit `$schema`. Unsupported dialects, OpenAPI 3.0/3.2, resource scopes, and unresolved references remain gaps. Import preserves source hashes and JSON pointers, not a copy of the original document.

The `generate` command derives TypeScript declarations and Python models from a supported schema subset. Read [model generation](model-generation.md) for setup, commands, and conformance limits. Inspect adapter capabilities and gaps before using an extracted fact. Native Pydantic/FastAPI or ts-rest/Zod runtime export execution, DataHub publication, AsyncAPI export, and recorded-traffic extraction remain follow-on work.

If the helper cannot run, continue bounded source analysis and record the unavailable adapter. Do not substitute successful prose analysis for a successful executable scan.

## Resolve the useful boundaries

Follow imports, route mounting, registry dispatch, callers, and response handling for the capability under study. An unmounted route stays a declaration or candidate. Preserve internal types as well as exported types; either may cross a boundary through serialization or shared code. Retain provider-specific registration names and dispatch variants even when their input shapes match.

For outbound APIs, trace low-level clients and wrappers to the method, base URL, path construction, query/body encoding, and response transformation. A cast or generic records a client expectation. A validator records only the rule it actually checks. Keep retries, timeouts, idempotency, pagination, authentication mechanisms, and unresolved configuration as evidence-backed notes without recording credential values or example customer payloads.

Preserve an existing provider specification with its source version or hash. A generated client-used surface describes what the scanned callers establish; it does not replace the provider's contract. Unknown method, path, response, or media-type details stay gaps. Never invent them to make an OpenAPI operation exportable.

## Review and hand off

Read `inventory.json`, `coverage.json`, and `summary.md`, then inspect the emitted schemas and HTTP artifacts relevant to the decision. Check representative records against their source locations, including a known declaration, a boundary, and a deliberate unsupported case. A clean parse and a valid specification establish neither full discovery nor runtime equivalence.

Keep agent findings and proposed relationships in separate analysis artifacts so a rescan cannot overwrite them. Link them by contract IDs and source evidence. State which gaps could change the testing or transition decision. Inventory completion means the requested scope has an explicit account of findings and omissions; it never means every runtime contract has been proved.
