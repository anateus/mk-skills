---
name: data-spelunking
description: Find and extract facts from data too large to read whole — big source files, logs, session/JSONL transcripts, CSV/JSON datasets, verbose tool output, trackers — without overflowing (or thrashing) the context window. A decision tree that routes to the cheapest right tool (ripgrep, ast-grep, qsv, jq/yq, windowed reads, a bundled JSONL/transcript extractor) and the read discipline that keeps subagents from aborting. Use when a task means searching or pulling specifics from a large corpus, or when dispatching subagents to mine files, logs, transcripts, or trackers.
---

# Data Spelunking

Return the *answer*, not the corpus. The failure mode is reading a whole large thing — a 1k-line file, a multi-MB transcript, a bulk ticket fetch — so it fills the window. In small-context subagents that also causes autocompaction to thrash and the agent to abort mid-task. Locate first, then read narrow.

## The balance

Reading the text directly is fine when the corpus is small and you need most of it. Reach for a tool when it is large, is queried repeatedly, or you need one slice of many. Don't front-load tool docs either: the one-liners below are usually enough — open a reference only when a one-liner falls short. That is the point of progressive disclosure; keep it cheap.

## Decide by data shape

| Corpus | Tool | One-liner |
|--------|------|-----------|
| Text / logs — find where | `rg` | `rg -n PATTERN path/` → line numbers, then read a window |
| Code — structural (calls, defs, shapes) | `ast-grep` / `sg` | `sg run -p 'foo($X)' -l ts` — matches syntax, not text |
| Tabular (CSV/TSV) | `qsv` | `qsv headers f.csv`; `qsv search -s col RE`; `qsv frequency`; `qsv stats` — streams, never loads whole |
| JSON / YAML | `jq` / `yq` | `jq '.a.b' f.json` — project before printing |
| NDJSON / CC session transcripts / huge tool dumps | `scripts/jsonl-extract.py` | regex → matched snippets with `file:line`, bounded |

## Read narrow, never whole

After locating, read only the window: `Read` with `offset`/`limit`, or `sed -n 'START,ENDp'`. For a symbol: `rg -n 'name' file` → read ±20 lines around the hit. Whole-file reads are for files you will genuinely use end to end.

## Big or repeated output → a file, not context

Pipe large searches to a scratch file and grep/slice that:

```
rg -n PATTERN path/ > /tmp/hits.txt ; rg -n KEY /tmp/hits.txt | head
```

Never let a multi-hundred-KB result land in context. For line-delimited JSON and Claude Code session transcripts, use the bundled extractor instead of `cat`/`grep` on raw JSON:

```
scripts/jsonl-extract.py SESSION.jsonl --match 'PATTERN' -i --out /tmp/hits.txt
```

It understands the Claude Code / Anthropic message schema (text + `tool_use` input + `tool_result`), drops boilerplate, tags each hit `L<line> <role>`, and truncates. `--mode ndjson --field a.b.c` projects a path out of generic NDJSON; `--mode text` is a truncating grep for anything else.

## When delegating spelunking to a subagent

Small-context agents thrash if handed a raw corpus. Give them the tool plus a contract: locate-then-window, write findings to a file, return a short summary — not raw dumps. Never call heavy MCP fetches (e.g. Linear `get_issue`) in a loop; use list/summary calls, and when an agent must edit a large record pass its current content in the dispatch instead of having it re-fetch. This mirrors the read-discipline block in `~/.agents/AGENTS.md`.

## References

- Read [finding code and text](references/finding-code-and-text.md) for `rg` and `ast-grep` recipes — context flags, structural metavariables, rewrites, and when each wins.
- Read [tabular and JSON](references/tabular-and-json.md) for `qsv` (search / stats / frequency / slice) and `jq`/`yq` projection on large files.
- Read [large outputs and transcripts](references/large-outputs-and-transcripts.md) for the extractor's full flags, the Claude Code transcript schema, and the pipe-to-file / MCP-fetch discipline.
