# Contract inventory first slice

The first implementation provides a runnable static inventory across TypeScript and Python, plus the `for-contracts`, `for-testing`, and `for-transitioning` workflows. It supports the first bounded monorepo/Kiban/Kanban pilot from the [implementation plan](../plans/2026-09-14-polyglot-contract-analysis.md).

The helper lives at `skills/analyzing-codebase/scripts/contract-inventory/`. It uses the TypeScript 5.9.3 compiler API and Python's standard-library AST. Neither adapter imports or executes analyzed application modules. Install its locked dependencies and run the checks from the repository root:

```bash
npm --prefix skills/analyzing-codebase/scripts/contract-inventory ci --ignore-scripts --no-audit --no-fund
node scripts/validate.js
```

The package has 18 offline tests covering both adapters and the shared CLI. Integration checks compile exported JSON Schemas with Ajv and lint OpenAPI fragments with Redocly. They also exercise deterministic rescans, explicit omissions, import-side-effect isolation, unsupported source languages, output ownership, preservation of the prior inventory on adapter failure, and symlink rejection for failed-attempt output.

## Local pilot

The pilot scanned the source scopes below. Counts describe those selected files, not repository-wide coverage or deployed endpoints.

| Repository | Selected files | Declarations | Boundary candidates |
| --- | ---: | ---: | ---: |
| monorepo | 52 | 167 | 66 |
| kiban | 4 | 9 | 2 |
| kanban | 10 | 71 | 4 |

Monorepo scope: `services/calls/process-tools/` and `libs/types/src/`. Kiban scope: `src/api/v1/internal/calls/tools/`. Kanban scope: the API entrypoint and calls router, calls/agent model directories, dynamic tool manager, event service/models, and HTTP session manager. The generated `coverage.json` records exact filters, revisions, source hashes, exclusions, and adapter diagnostics for each root.

The 72 candidates include 31 HTTP observations and 41 tool registrations. Four HTTP operations have enough static information to produce OpenAPI fragments; 68 candidates remain in inventory with explicit export omissions. The pilot produced 235 standalone schema projections and two OpenAPI documents. Schema compilation and specification lint validate representation, not native behavioral equivalence.

Local artifacts are at `/Users/mike/.local/share/mk-skills/contract-inventory/domu-pilot/`, outside the skill repository. `summary.md` is the entrypoint; `inventory.json` and `coverage.json` retain detailed evidence. No live service or DataHub publication was used.

## Independent evaluation and fixes

A separate synthetic forward evaluation used the skill to inventory a legacy TypeScript handler, its remaining caller, and a Python replacement candidate, then produce transition artifacts. The transition analysis kept retirement blocked by the caller and unresolved behavioral requirements.

That evaluation found nested provider registries disappearing without diagnostics and schema-specific validation gaps missing from standalone OpenAPI components. The adapter now reports unsupported nested registrations; OpenAPI components preserve status, gaps, and evidence. A separate CLI/export review found colon path parameters emitted literally and failed attempts following an output symlink. Supported inbound `/:id` segments now become `/{id}` parameters while retaining the source path, and the writer rejects a symlinked attempts directory. Regression tests cover these cases.

## Limits and next work

The helper is deliberately partial. TypeScript resolves selected relative imports; package and tsconfig aliases produce unresolved-import diagnostics. Python uses static Pydantic projections; inherited fields, coercion, validators, and full serialization behavior require review. Dynamic methods, destinations, registrations, and missing response evidence remain candidates or diagnostics rather than invented specifications.

Native schema-export execution, generated Python/TypeScript models, provider-specification reconciliation, DataHub publication, AsyncAPI export, and captured-traffic extraction remain later slices. Transition artifacts are evidence-backed agent analysis using the inventory; the scanner does not automatically establish replacement equivalence or authorize retirement. A broad monorepo baseline and migration sequencing remain work to perform with the new workflow beyond this bounded pilot.
