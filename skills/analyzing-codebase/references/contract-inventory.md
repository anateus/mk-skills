# Inventory interpretation

The inventory preserves source evidence and extraction limits across languages. JSON Schema and OpenAPI are useful projections of that evidence. Native validation, serialization, state, and delivery rules can carry behavior those formats do not express.

## Read the artifacts

| Artifact | Use |
|---|---|
| `contracts/inventory.json` | Repository provenance, adapter results, declarations, schemas, operations, relationships, and diagnostics |
| `contracts/coverage.json` | Selected, excluded, unsupported, and failed source coverage for each root |
| `contracts/summary.md` | Readable findings and omissions |
| `contracts/schemas/`, `contracts/openapi/` | The supported extracted surface, with its dialect and gaps |
| `contracts/manifest.json` | Ownership of the generated output directory |

The helper's versioned adapter protocol is defined in `scripts/contract-inventory/src/types.ts` relative to this skill. Its records carry evidence locations and extraction status. Read the emitted envelope rather than assuming the same revision or coverage applies to every repository.

`resolved` describes a supported extraction, not a proved runtime guarantee. `partial` retains useful evidence with named gaps. `unsupported` records a case the adapter cannot represent. Treat aggregate static coverage as partial even when every selected file parsed. A file may contain unsupported boundary kinds or runtime configuration that the parser cannot resolve.

## Keep identity and evidence separate

Use stable repository IDs across rescans. Record analyzed revisions and file content changes as provenance; do not treat an analyzed commit as the deployed version. Source moves and renames may change declaration IDs, so reconcile them with evidence before reporting additions or removals.

Identify HTTP operations by owner or provider, version when established, direction, method, and path. GET and POST on one path are distinct. Keep request and response schemas, response statuses, media types, and input/output schema roles distinct. Two consumers may call one provider operation, but matching path text alone cannot establish that identity.

Relations have a stated meaning and evidence: references, calls, registrations, validation, or serialization. Similar names or structural schemas do not prove substitution, ownership, or data lineage. Proposed cross-repository mappings belong in transition analysis until the actual call chain supports them.

## Preserve semantic gaps

Record whether a shape comes from a declaration, registration, client expectation, runtime validation rule, serialization path, or static call. Source inspection can establish that a validator is wired without proving its behavior for all inputs.

Required versus nullable fields, aliases, omitted values, extra fields, unions, recursion, numeric constraints, dates, defaults, custom validators, and transforms need explicit treatment. Python and TypeScript may disagree on these even when generated declarations look similar. An unsupported refinement or transform remains attached to the source contract; exporting a simpler schema does not discharge it.

Retain source paths and symbols for original declarations. If a native schema or published specification is available, preserve it separately with version/hash and provenance. The helper can import explicitly selected JSON Schema 2020-12 and OpenAPI 3.1 documents, retaining source hashes and JSON pointers. It does not execute native schema exporters. Any later isolated native export needs an inspected entrypoint and a conformance check before its output can replace a static projection. [Model generation](model-generation.md) produces derived language models and a separate conversion report; it never promotes them to source of truth.

## Consumers

Testing analysis links contract IDs to properties, examples, observation points, and validation or serialization gaps. Transition analysis adds proposed ownership, replacements, remaining consumers, coexistence, rollback, and retirement evidence. Keep those annotations separate from generated scan output.

Language conversion and DataHub are planned consumers of this inventory. Generated models require shared valid/invalid examples and serialization checks, with losses recorded. DataHub should expose stable identities, provenance, and complete artifact links; a type reference is not data lineage. Neither consumer is required to use the local inventory.
