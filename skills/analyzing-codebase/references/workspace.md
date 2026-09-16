# Workspace and provenance

Use `docs/code-analysis/` at the repository root unless the user selected another location. Preserve existing files and extend them instead of overwriting them. Create subdirectories only when their first artifact is needed.

## Provenance

Every agent-authored top-level Markdown artifact starts with YAML frontmatter describing the target, revision, date, and external references:

```yaml
---
system_path: <absolute path to the analyzed root>
commit: <full 40-character git SHA, or "uncommitted" outside git>
updated: YYYY-MM-DD
external_references:
  - path: <absolute path or URL>
    why: <why this source was consulted>
---
```

Use `external_references: []` when the user explicitly scoped the run to the directory. On update, refresh `commit` and `updated`; add newly consulted sources without erasing sources that already informed the artifact. Per-property files inherit provenance from `property-catalog.md`.

For multiple repositories, retain the existing primary `system_path` and `commit` fields and add a `repositories` list containing each stable `id`, absolute `root`, revision, dirty-worktree status, and analysis scope. Record exclusions and coverage per root; one repository's revision cannot describe the others. Capture relevant uncommitted changes or content hashes when the commit alone would misidentify the analyzed source. Distinguish analyzed revisions from deployed versions.

JSON artifacts carry provenance in their JSON envelope, without YAML frontmatter. The static helper writes its own envelope and per-root coverage. Keep agent annotations and proposed cross-repository mappings in separate files so a rescan can replace generated output without erasing analysis. Reuse generated artifacts only while roots, source content, dependencies, filters, and adapter versions remain current.

The generated `contracts/summary.md` uses deterministic frontmatter with `analysis`, `complete`, `external_references`, and per-repository `id`, `system_path`, and `commit`. It omits an update timestamp. Its authoritative source hashes, scope, and coverage live in `inventory.json` and `coverage.json` beside it. Agent-authored analysis keeps the richer frontmatter above.

Top-level artifacts include:

- `system-analysis.md`
- `existing-test-hooks.md`
- `property-catalog.md`
- `test-topology.md`
- `property-relationships.md`
- `evaluation/synthesis.md`
- `evaluation/{lens}.md`
- `contracts/summary.md`
- `transition-inventory.md`
- `transition-analysis.md`

Initialize a new artifact with a short summary plus `Assumptions` and `Open Questions`. The artifact set is a durable handoff, not a raw search dump. Include enough file paths, symbols, and evidence for another reader to verify expensive findings.

## Layout

```text
docs/code-analysis/
  system-analysis.md
  existing-test-hooks.md
  test-topology.md
  property-catalog.md
  property-relationships.md
  contracts/
    inventory.json
    coverage.json
    summary.md
  transition-inventory.json
  transition-inventory.md
  transition-analysis.md
  properties/
    {slug}.md
  evaluation/
    synthesis.md
    mechanism-fit.md
    coverage-balance.md
    implementability.md
    wildcard.md
```

Each property uses one descriptive kebab-case slug in its catalog heading, evidence filename, and relationship references. There is no separate numeric ID.

Create contract and transition artifacts only when their modes need them. Keep portable schema and HTTP exports alongside the contract inventory; read [inventory interpretation](contract-inventory.md) for evidence and identity rules. A transition inventory tracks capability IDs and links to source contract IDs across repositories.
