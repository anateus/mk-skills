# Contract inventory tooling and DataHub

Use existing compilers and schema exporters to build the contract inventory, with a small adapter layer for source locations, boundary relationships, and coverage. DataHub can host a browsable projection. Keep the complete inventory and original specifications as portable artifacts because the catalog projection loses distinctions the analysis needs.

This investigation supports the agreed `for-contracts`, `for-testing`, and `for-transitioning` modes. It includes source inspection and synthetic executable probes, not a completed skill implementation or a DataHub deployment.

## What to reuse

| Need | Candidate | Recommendation and limit |
| --- | --- | --- |
| TypeScript declarations, aliases, inferred types, and references | [ts-morph](https://ts-morph.com/details/types), wrapping the TypeScript compiler | Use for semantic discovery and source relationships. Match its compiler version to the repository; a syntax parser alone cannot resolve inferred types. |
| Broad structural discovery across languages | [ast-grep](https://ast-grep.github.io/guide/introduction.html), built on Tree-sitter | Use query rules to find registrations, schema constructors, and queue operations. Framework-specific rules still need to establish what each match means. |
| Plain TypeScript types to JSON Schema | [ts-json-schema-generator](https://github.com/vega/ts-json-schema-generator) | Reuse for supported data types. The probe handled imported aliases, recursion, a union, a generic instantiation, and a referenced internal type. It failed on the tested Zod-inferred output type. |
| Kiban HTTP contracts | [ts-rest OpenAPI generation](https://ts-rest.com/openapi) | Reuse the existing generator and reconcile its output with mounted routes. Declaration export alone does not establish that an endpoint is exposed. |
| Standalone runtime schemas | [Zod 4 native conversion](https://zod.dev/json-schema), version-specific Zod 3 conversion | Detect the schema version. Kiban's inspected manifest specifies Zod 3, so do not assume `z.toJSONSchema` is available at its imports. [zod-to-json-schema](https://github.com/StefanTerdell/zod-to-json-schema) is archived; use it only as a pinned compatibility bridge if the existing exporter is insufficient. |
| Database model shapes | [Drizzle schema adapters](https://orm.drizzle.team/docs/zod) | Evaluate against the installed Drizzle/Zod versions. Current documentation uses newer import paths. Preserve database constraints and actual query projections separately from generated row shapes. |
| Python schema models | [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/) | Reuse native model export when Pydantic is present. Follow-up source inspection confirmed Kanban's FastAPI/Pydantic and aiohttp paths; Python extraction and conversion remain untested. |
| Messaging contracts | [AsyncAPI tooling](https://www.asyncapi.com/tools/generator) plus registration adapters | Use AsyncAPI as an output format. The official Generator consumes specifications to produce code and documentation; it does not discover arbitrary queue usage. BullMQ and other registration patterns need extraction adapters. |
| Testing consumer | [Schemathesis](https://schemathesis.readthedocs.io/en/stable/) | Candidate for tests generated from OpenAPI. Application invariants, side effects, and queue behavior still need the existing testing analysis. Not exercised here. |
| Transitioning consumer | [oasdiff](https://github.com/oasdiff/oasdiff) | Candidate for OpenAPI change classification. A compatible specification diff does not prove compatible runtime behavior. Not exercised here. |

The inventory adapter should join facts from these tools. For example, a compiler resolves a type, a schema exporter captures its representable constraints, and a route adapter proves where that schema is used. Store those as separate facts with source evidence. Keep agent-reviewed annotations separate from generated records so rescanning does not overwrite them.

## Follow-up from the pinned OpenAPI tools catalog

The [catalog at `09bfeef5fb3598d65cde74755727613743e81700`](https://github.com/apisyouwonthate/openapi.tools/tree/09bfeef5fb3598d65cde74755727613743e81700/src/content/tools) contains 353 tool files. Metadata screening selected 85 candidates by category or description, followed by README and repository-metadata checks for 11 tools. This was a targeted shortlist review, not an execution test of the entire catalog.

| Tool | Addition to this design | Evidence and qualification |
| --- | --- | --- |
| [Redocly CLI](https://redocly.com/docs/cli/commands/generate-spec) | Bundle and lint specifications; optionally generate candidate contracts from captures and compare exchanges against them | CLI 2.53.0's experimental `generate-spec`, `proxy`, and `drift` commands are released. The synthetic probe exercised generation and drift, plus lint and bundle. Generation currently emits OpenAPI 3.2 only. |
| [Prism](https://github.com/stoplightio/prism) | Exercise low-level clients against a mock provider or validate exchanges through a proxy | Its documented mock server and validation proxy complement the outbound inventory. Not exercised here. |
| [Spectral](https://github.com/stoplightio/spectral) | Apply custom rules to source evidence, completeness annotations, and specification conventions | JSON/YAML rules can cover OpenAPI and AsyncAPI. Lint can require evidence fields, but cannot prove those fields are true. Not exercised here. |
| [mitmproxy2swagger](https://github.com/alufers/mitmproxy2swagger) and [har-to-openapi](https://github.com/jonluca/har-to-openapi) | Alternative capture-to-specification importers | Candidate paths for existing HAR or mitmproxy captures. Their descriptions target OpenAPI 3.0. Neither was exercised here. |
| [api-smart-diff](https://github.com/udamir/api-smart-diff) | Compare more than HTTP specifications, including standalone JSON Schema | Its README lists OpenAPI 3.0, AsyncAPI 2.x, and JSON Schema. AsyncAPI 3.x remains on its roadmap, so it cannot yet replace every comparison adapter. Not exercised here. |
| [typeconv](https://github.com/grantila/typeconv) | Evaluate reusable type conversion and source-location handling | Its `core-types` layer preserves useful metadata but reduces constraints to what the participating type systems share. Preserve native contracts outside that layer. Not exercised here. |

The catalog's TypeScript-to-OpenAPI entries do not establish automatic discovery of arbitrary low-level clients. [ts-oas](https://github.com/ts-oas/ts-oas) expects endpoint types containing fields such as `path`, `method`, and `responses`. [SDK-IT](https://github.com/januarylabs/sdk-it) documents a TypeScript backend workflow including Hono. These are possible adapters where their input contracts match; the reviewed documentation does not establish that they replace wrapper and client-call analysis.

[Optic](https://github.com/opticdev/optic) closely matches the combined capture, diff, and testing use case, but its repository is archived. Prefer evaluating the released Redocly commands for that role. [libopenapi](https://github.com/pb33f/libopenapi) is another parser/resolver candidate if a Go implementation becomes useful; no need to introduce a Go component for the initial TypeScript path.

The [Redocly probe](../research/openapi-catalog-probe/) generated three operations from four synthetic exchanges, parameterized the repeated GET path, retained POST 201 and DELETE 204, passed specification lint, and reported no drift on the original exchanges. A deliberate response-field type mutation produced one schema-consistency error and a nonzero exit. These results were obtained with optional AI refinement disabled. The proxy command and DataHub ingestion of the resulting OpenAPI 3.2 artifact remain untested.

Add recorded exchanges as optional evidence alongside provider declarations and static client analysis. Record the capture's source, exercised scenarios, and operation coverage. An inferred path template or enum is a hypothesis for review; unobserved endpoints, error responses, optional fields, and alternate types remain unknown. Use synthetic fixtures for the first integration. Published artifacts must contain schema metadata and permitted source references without captured credential values or customer payloads.

## What the probes established

The [probe directory](../research/contract-inventory-probe/) contains synthetic inputs, executable checks, locked JavaScript dependencies, pinned Python dependencies, and the observed results. The fixtures are deliberately small; these results do not establish repository-wide coverage.

The TypeScript probe used `ts-morph` 28.0.0, `ts-json-schema-generator` 2.9.0, Zod 3.25.76, and `zod-to-json-schema` 3.25.2. It found a non-exported declaration and resolved the input and output of a Zod transform to `string` and `number`. The JSON Schema generator handled the plain TypeScript fixture but returned `Unhandled error while creating Base Type.` for `z.output<typeof Count>`.

The Zod 3 converter emitted identical schemas for `z.string().min(2)` and the same validator with a refinement rejecting `blocked`. The validators behaved differently on that value. The default export of a string-to-number transform described its input. These observations require explicit input/output labels and a record of constraints that conversion does not preserve. They also rule out using schema equality as proof of behavioral equivalence.

The initial fixture used Node's older module resolution setting. ts-morph's bundled TypeScript 6.0.2 rejected it as deprecated; switching the synthetic fixture to Node16 resolution allowed the probe to run. The schema generator used TypeScript 5.9.3. This establishes a version-compatibility concern, not a reason to change Kiban's configuration.

## External APIs and low-level clients

`for-contracts` should inventory outbound HTTP APIs and generate OpenAPI for the recoverable client-used surface, including calls made through `fetch`, Axios, SDKs, and shared HTTP wrappers. Each boundary records its direction relative to the analyzed application. Link all callers to the same external operation identity, based on provider, API version, method, and path; keep the consuming repository separate from that identity.

Preserve two artifacts when a provider publishes a specification: the upstream OpenAPI document at a recorded version or content hash, and the surface used by our clients. The latter records the operations called and the requests and responses our code expects. It is partial evidence about usage, not a claim that the provider exposes only those operations. Compare the two to find drift and undocumented client assumptions without overwriting either.

For low-level clients, follow imports and wrapper calls to recover the HTTP method, base URL configuration, path template, query serialization, headers, body encoding, and response handling. Use types and runtime validators where present. Record authentication mechanisms without credential values. An SDK operation can be linked to a published specification when the package version and operation mapping are established; otherwise keep the relationship unresolved.

A TypeScript response cast or an Axios generic establishes a client expectation. It does not establish what the provider returns or whether the client validates the response. Keep provider declarations, client expectations, and runtime validation as separate evidence. Preserve the actual wire representation before a wrapper renames fields, unwraps envelopes, or transforms values.

Unknown details remain explicit. Never invent a successful status, JSON content type, required field, or endpoint path to fill out a specification. Use an annotated partial operation where OpenAPI permits it; if a valid operation cannot be represented without fabrication, keep the candidate in the inventory and export coverage report. OpenAPI's operation, parameter, and response rules constrain what the exporter can emit. [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html).

Keep client-side retries, timeouts, pagination, and idempotency behavior in the inventory alongside the operation. These are useful inputs to testing and transitioning even when standard OpenAPI fields cannot express them. DataHub can expose the external operation, its provider, source specification, and consuming applications, with links back to the full inventory. Consumer relationships are distinct from data lineage.

## DataHub can browse the inventory

DataHub's existing source model maps API endpoints to datasets with the `API_ENDPOINT` subtype. Its JSON Schema source maps schemas to datasets with the `Schema` subtype and provides flattened fields for browsing. These are useful starting points for a projection using standard entities. [OpenAPI source documentation](https://docs.datahub.com/docs/generated/ingestion/sources/openapi), [JSON Schema source documentation](https://docs.datahub.com/docs/generated/ingestion/sources/json-schema).

The offline probe ran the actual `acryl-datahub` 1.7.0 source classes and collected metadata workunits. The OpenAPI document was supplied in memory, HTTP requests were forbidden, and `enable_api_calls_for_schema_extraction` was explicitly false. No DataHub server or UI was exercised.

| Synthetic input | Observed DataHub 1.7.0 result |
| --- | --- |
| GET and POST on `/widgets`, each with a distinct 200 response | One dataset, carrying the GET response schema |
| POST `/created`, with only a 201 response | Endpoint omitted |
| DELETE `/removed`, with only a 204 response | Endpoint omitted |
| GET `/widgets` also has a distinct 400 response | Error schema omitted |
| JSON Schema containing an enum, a union, required fields, and constraints | Browsable fields emitted; the complete raw schema preserved in `OtherSchema.rawSchema` |

The four-operation, three-path OpenAPI fixture yielded one dataset. Source inspection explains why: `get_endpoints` keys records by path and requires a 200 response, while schema extraction selects the first supported schema. [Pinned parser source](https://github.com/datahub-project/datahub/blob/v1.7.0/metadata-ingestion/src/datahub/ingestion/source/openapi_parser.py), [pinned extraction source](https://github.com/datahub-project/datahub/blob/v1.7.0/metadata-ingestion/src/datahub/ingestion/source/openapi.py).

Use a small exporter over the inventory for complete operation identity. Give each endpoint a stable identity containing its service, method, and normalized path; preserve request, response status, and media type distinctions. Give schemas their own stable identities and link catalog records back to the complete artifact. Store the analyzed revision as provenance rather than creating a new catalog identity for every commit.

Start with standard dataset/subtype records, source links, descriptions, and properties for contract IDs and extraction status. Test richer navigation before promising that arbitrary type-reference edges will be browsable. Data lineage edges should represent observed data flow; an import or a type reference alone does not establish lineage. Custom entities introduce schema and UI work, so the first slice should avoid requiring them. [Metadata model extension guide](https://docs.datahub.com/docs/metadata-modeling/extending-the-metadata-model).

A publisher must distinguish a complete scan from an incomplete one before removing catalog records. Scope updates to records owned by this exporter, preserve human annotations, and make repeat publication idempotent. Canonical artifacts remain available when DataHub is unavailable.

## First implementation slice

The [polyglot implementation plan](../plans/2026-09-14-polyglot-contract-analysis.md) now defines the sequence. Start with `for-contracts` and one shared inventory from TypeScript and Python; add `for-transitioning` and the testing consumer in the next slice so the inventory supports a concrete modernization decision early.

Implement bounded TypeScript/ts-rest/Zod and Python/FastAPI/Pydantic paths through the shared inventory. Include outbound HTTP extraction for synthetic low-level clients and shared wrappers. Acceptance fixtures should retain all four HTTP operations above, distinguish inputs from outputs, preserve raw schemas, and report unsupported refinements. They should also demonstrate a non-exported type, an unresolved registration, and a declared-but-unmounted route so coverage reporting can detect known omissions. The DataHub metadata-file exporter follows as an independent consumer.

For outbound extraction, verify a dynamic path parameter, encoded query values, request serialization, and a response cast without runtime validation. Two callers of the same provider operation should share one operation identity. An unresolved URL or method must remain visible in coverage, and a mismatch with a provider specification must remain visible as a disagreement. These outbound fixtures are planned acceptance checks; the saved feasibility probes do not yet exercise them.

Apply that slice to bounded local monorepo, Kiban, and Kanban source paths, including legacy provider registries and shared-type imports. Establish a broader monorepo discovery baseline with explicit coverage, then use the transition inventory to track replacement mappings, remaining callers, shared-state dependencies, and retirement evidence. Evaluate compiler compatibility, route mounting, schema conversion, and producer/consumer links before expanding to database models or messaging. Generated TypeScript and Python models use a shared conformance corpus with explicit conversion gaps. Publishing and UI verification are later integration checks against the authorized catalog environment; they are not prerequisites for local extraction.

## Provenance and limits

Investigated on 2026-09-14. The local Kiban checkout was at `039829b6b61718248b5b665ef86369e25486e677`; its manifest specified ts-rest `^3.52.1`, Zod `^3.25.76`, Drizzle `^0.45.2`, and TypeScript `^5.9.3`. Runtime use was checked in `src/api/v1/internal/calls/tools/tools.contract.ts`, `src/api/v1/internal/calls/tools/tools.handler.ts`, and `scripts/generate-openapi-specs.ts`. Those imports and call sites establish an existing export path; the Kiban application and exporter were not executed.

DataHub 1.7.0 was selected from the planned OSS deployment recorded in Hindsight. This investigation makes no claim about what is deployed. Public documentation was checked alongside pinned source and the installed SDK. Documentation recommends an `openapi` installation extra, but the 1.7.0 distribution warned that the extra does not exist; the plain package contained both source classes and ran the probes.

CUE remains optional. Its [JSON Schema and OpenAPI integration](https://cuelang.org/docs/integration/) makes it a candidate for later constraint work, but it was not exercised here. The immediate need is preserving extraction evidence and conversion gaps, which choosing another schema language does not eliminate.
