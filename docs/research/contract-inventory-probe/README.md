# Contract inventory feasibility probes

These synthetic probes record tool behavior for the [contract inventory investigation](../../designs/2026-09-14-contract-inventory-tooling.md). They are not production extraction adapters.

`probe.cjs` exercises TypeScript declaration discovery, inferred input/output types, JSON Schema generation, and Zod 3 conversion losses. `datahub_probe.py` runs DataHub 1.7.0 source classes against synthetic specifications, forbids HTTP requests, and inspects generated metadata workunits. It does not connect to a catalog or verify its UI.

Run in a disposable directory from the repository root:

```bash
probe_dir=$(mktemp -d)
cp docs/research/contract-inventory-probe/* "$probe_dir/"
cd "$probe_dir"
npm ci --ignore-scripts --no-audit --no-fund
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
node probe.cjs
.venv/bin/python datahub_probe.py
```

The scripts overwrite `typescript-results.json` and `datahub-results.json` in that disposable directory. The checked-in results are the observations from 2026-09-14. Assertions include expected limitations: a successful probe does not mean conversion is lossless.

The initial run used Node.js 26.8.2 and Python 3.12.13. JavaScript dependencies are locked in `package-lock.json`; Python dependencies are pinned in `requirements.txt`. The synthetic TypeScript configuration uses Node16 resolution to work with both compiler versions bundled by the selected tools. Repository-specific compiler compatibility remains untested.
