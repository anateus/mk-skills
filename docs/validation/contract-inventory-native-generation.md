# Native contract import and language generation

The second contract-inventory slice adds TypeScript workspace resolution, explicit native artifact import, and derived language models. It builds on `7ea4466`, which introduced the static inventory. The workflows remain partial source analysis; they don't establish deployed behavior or retirement readiness.

## Checked behavior

The package's 43 tests pass with Node dependencies from `package-lock.json` and Python 3.12 dependencies from `generation-requirements.lock`. They cover both public CLI commands as well as adapter behavior. The new cases include:

- Selected-source `tsconfig` aliases, relative configuration inheritance, workspace package exports, configuration hashes, malformed configuration, cycles, and scope exclusions.
- JSON Schema 2020-12 and OpenAPI 3.1 imports with local references, recursive schemas, source pointers, request requiredness, multiple media types, non-200 successes, and empty responses. Ajv validates schema projections and Redocly checks generated HTTP documents.
- Python-origin native schemas compiled into TypeScript declarations with valid and invalid assignments; TypeScript-origin schemas generated into Pydantic models with validation and serialization checks for missing and nullable fields.
- Rejected remote references, unsafe paths, unsupported schema constraints, code-generation extensions, and unavailable Python dependencies. Generated output ownership cannot replace the source inventory.

The repository-wide `node scripts/validate.js` gate also passes: hook and skill checks, contract inventory, curation, prose checks, evaluation tooling, Zellij helpers, installers, plugin schema, and whitespace. After the final version metadata and generated-summary wording changes, the package tests were rerun. Local logs are `/tmp/contract-next-validation.log` and `/tmp/contract-next-version-check.log`.

Independent review found that a closed empty object generated TypeScript `{}`, which accepted primitive values. That shape now skips with an explicit issue, and the original reproduction confirms no model is emitted. Integration review also found that reference rewriting could alter literal `$ref` keys inside example or constant data. Traversal now follows schema-bearing keywords only; a regression preserves literal data through OpenAPI export.

## Bounded source pilot

The same 66 selected files from the first pilot were rescanned across monorepo, Kiban, and Kanban. Every source hash matched the first inventory. The result remains 247 declarations and 72 boundary candidates. This is the first pilot's selected capability scope, not all three repositories.

For monorepo, the inventory now records five configuration files. Relationships emitted by its TypeScript adapter increased from 118 to 121, and diagnostics decreased from 117 to 87. These are counts of all adapter relationships and diagnostics in that fixed source cohort, not counts of fully resolved contracts. Kiban records two configuration files; its selected sources and the Kanban cohort produced unchanged relationship and diagnostic counts.

The exact source revisions remain:

| Root | Revision |
| --- | --- |
| monorepo | `16aab70bd2076ece35f192814fe8a234569ca394` |
| kiban | `039829b6b61718248b5b665ef86369e25486e677` |
| kanban | `7d08ee0bbd6bf28d03280d8ded78fa8af737f427` |

The local inventory is `/Users/mike/.local/share/mk-skills/contract-inventory/domu-pilot-native-generation/`. Its JSON artifacts contain the exact filters, source and configuration hashes, diagnostics, and omissions. No target module was executed and no live Domu system was accessed.

## Remaining limits

Native import reads pre-existing JSON artifacts; it doesn't run FastAPI, Pydantic, ts-rest, or Zod exporters inside target applications. OpenAPI 3.0/3.2 and unsupported schema resource scopes stay explicit omissions. The model generator accepts a bounded JSON Schema 2020-12 subset; OpenAPI's default schema dialect remains unsupported for generation. TypeScript output supplies declarations only. Source gaps, numeric differences, and structural typing limits remain in the conversion report.

A capability-level transition artifact, broader external API extraction, and an offline DataHub projection remain subsequent work. None of these test results authorizes removal of a monorepo capability.
