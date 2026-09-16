# Generate language models from an inventory

The `generate` command creates derived TypeScript declarations and Pydantic models from the inventory's exported schemas. The original declarations remain authoritative. A generated model isn't evidence that validation, serialization, or business behavior survived a language transition.

Run these commands inside `scripts/contract-inventory/`, relative to the skill directory:

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run build
uv venv --python 3.12 .venv-generation
uv pip install --python .venv-generation/bin/python -r generation-requirements.lock
node dist/cli.js generate \
  --input /absolute/path/to/analysis/contracts \
  --out /absolute/path/to/analysis/models
```

The default Python executable is the package's `.venv-generation/bin/python` (`Scripts/python.exe` on Windows). Pass `--python /absolute/path/to/python` to use another isolated environment with the pinned dependencies. Scanning Python source still needs only Python 3.9+; model generation uses Python 3.12 output and a separate dependency set. It doesn't install packages automatically or import the analyzed application.

Generation uses `json-schema-to-typescript` 16.0.0, `datamodel-code-generator` 0.81.0, and Pydantic 2.13.5. The npm and Python lockfiles record dependencies. The command reads only manifest-listed schemas, resolves references within that set, and passes generators an internal reference graph. It doesn't fetch references or read arbitrary schema paths.

Outputs live in a separate managed directory: `models/typescript/`, `models/python/`, `generation.json`, `coverage.json`, and `manifest.json`. The report links each generated or skipped model to its source ID, schema hash, dependencies, source gaps, generator versions, and conversion issues. Names are deterministic derivatives of contract IDs. Keep reviewed names and application integration outside generated output. Inventory and model manifests have distinct ownership kinds so one command can't overwrite the other's directory.

## Supported conversion and its limits

The initial subset covers JSON Schema 2020-12 primitives, typed arrays, supported object properties, required and optional fields, nullable values, simple string enums, and references. Unsupported constraints or property names cause an explicit skip. Numeric ranges, formats, arbitrary unions, aliases that require renaming, and custom validation aren't silently approximated. Defaults and annotations aren't emitted as executable code or model defaults; their removal is reported. Recursive references remain subject to each generator's result.

OpenAPI's default schema dialect is preserved during import but isn't accepted by this generator. A standalone 2020-12 schema or an OpenAPI document explicitly using that supported dialect can supply generation input. Don't relabel a dialect without checking its semantics.

TypeScript output has no runtime validator. Integer and floating-point differences remain conversion gaps. Pydantic models use strict primitive types and an omission sentinel so an absent optional field doesn't become an explicit null during serialization. Source gaps remain attached even when model generation succeeds.

The synthetic conformance tests compile Python-origin TypeScript declarations, validate TypeScript-origin models with Pydantic, reject selected invalid payloads, and compare serialized output. They establish those cases only. Before adopting a generated model for a transition, add the capability's own validation and serialization corpus, including custom validators and failure paths. Generation never marks contracts behaviorally equivalent or ready to retire.
