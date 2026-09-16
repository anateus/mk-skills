# OpenAPI catalog feasibility probe

This probe checks Redocly CLI 2.53.0's experimental traffic inference and drift commands using four synthetic HTTP exchanges. It generates three operations, retains 201 and 204 responses, validates and bundles the specification, then confirms that changing a response field from a string to a number produces a drift error.

Run from the repository root in a disposable directory:

```bash
probe_dir=$(mktemp -d)
cp docs/research/openapi-catalog-probe/* "$probe_dir/"
cd "$probe_dir"
npm ci --ignore-scripts --no-audit --no-fund
python3 probe.py
```

The initial run used Node.js 26.8.2 and Python 3.9.6. `package-lock.json` pins the CLI. The script writes generated specifications, drift reports, and `results.json` into the disposable directory. It does not start a proxy or invoke the optional AI refinement.

The generator currently emits OpenAPI 3.2.0. This probe establishes behavior on its small fixture; it does not establish compatibility with DataHub, capture completeness, or correctness of inferred path templates and constraints on arbitrary traffic. See the [tooling assessment](../../designs/2026-09-14-contract-inventory-tooling.md) for the recommendation.
