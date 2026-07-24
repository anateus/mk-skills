---
name: data-spelunking
description: Find and extract facts from data too large to read whole — big source files, logs, session/JSONL transcripts, CSV/JSON datasets, verbose tool output, trackers — without overflowing (or thrashing) the context window. A decision tree that routes to the cheapest right tool (ripgrep, ast-grep, qsv, jq/yq, windowed reads, a bundled JSONL/transcript extractor) and the read discipline that keeps subagents from aborting. Use when a task means searching or pulling specifics from a large corpus, or when dispatching subagents to mine files, logs, transcripts, or trackers.
---

# Data Spelunking

Return the answer, not the corpus. Locate first, then read narrow. Never allow a large file, transcript, search result, dataset, or record body to land whole in context.

## Core workflow

1. Survey shape and size without printing content.
2. Locate candidate files, records, symbols, or line numbers.
3. Read only the relevant fields or narrow line windows.
4. Redirect potentially large intermediate output to a scratch file, then filter it.
5. Report findings and uncertainty; do not return raw dumps.

## Decide by data shape

| Corpus | Start with |
|---|---|
| Text or logs | `rg -l` to survey, `rg -n` to locate, then line windows |
| Source structure | `ast-grep` / `sg` for calls, definitions, and syntax shapes |
| CSV or TSV | `qsv headers`, then projection, filtering, or aggregation |
| JSON or YAML | `jq` / `yq`; project or aggregate before printing |
| NDJSON, session transcripts, huge tool output | `scripts/jsonl-extract.py` with bounded output |

## When delegating spelunking to a subagent

Give the agent this workflow and a named findings-file path, not the raw corpus. Require a short returned summary with explicit unknowns. For trackers or heavy MCP records, use summary/list calls and avoid repeated full-record fetches.

## Load details only when needed

- Read [finding code and text](references/finding-code-and-text.md) when searching code or logs, using structural search, or planning a mechanical rewrite.
- Read [tabular and JSON](references/tabular-and-json.md) when inspecting CSV, TSV, JSON, or YAML.
- Read [large outputs and transcripts](references/large-outputs-and-transcripts.md) when handling transcripts, NDJSON, verbose output, trackers, heavy MCP fetches, or delegated corpus mining.
