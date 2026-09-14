# Workspace and provenance

Use `docs/code-analysis/` at the repository root unless the user selected another location. Preserve existing files and extend them instead of overwriting them. Create subdirectories only when their first artifact is needed.

## Provenance

Every top-level artifact starts with YAML frontmatter describing the target, revision, date, and external references:

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

Top-level artifacts include:

- `system-analysis.md`
- `existing-test-hooks.md`
- `property-catalog.md`
- `test-topology.md`
- `property-relationships.md`
- `evaluation/synthesis.md`
- `evaluation/{lens}.md`

Initialize a new artifact with a short summary plus `Assumptions` and `Open Questions`. The artifact set is a durable handoff, not a raw search dump. Include enough file paths, symbols, and evidence for another reader to verify expensive findings.

## Layout

```text
docs/code-analysis/
  system-analysis.md
  existing-test-hooks.md
  test-topology.md
  property-catalog.md
  property-relationships.md
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
