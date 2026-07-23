# Large outputs, transcripts, and MCP fetches

The recurring failure: one oversized result (a multi-MB transcript, a broad grep, a bulk ticket body) lands in context. In the main agent it wastes budget; in a small-context subagent it makes autocompaction thrash and the agent abort. Keep the big thing on disk; move only the answer.

## Pipe big output to a file, slice the file

```
rg -n PATTERN big/ > /tmp/hits.txt
rg -n KEY /tmp/hits.txt | head -40         # now slice cheaply
```

Anything you expect to exceed ~a few hundred KB: redirect first, inspect second. In this harness a large `Bash` result is auto-spilled to a persisted-output file — read a filtered slice of that path, never re-run the command to "see it all."

## The bundled extractor (`scripts/jsonl-extract.py`)

For line-delimited JSON and Claude Code / Anthropic session transcripts. It returns regex-matched, line-referenced, truncated snippets — the routine you would otherwise hand-write each time.

```
# CC session transcript (auto-detected): find where a topic was discussed
scripts/jsonl-extract.py ~/.claude/projects/<proj>/<uuid>.jsonl \
    --match 'Medallion|no-available-llm|root cause' -i --out /tmp/hits.txt

# generic NDJSON: project a field and filter
scripts/jsonl-extract.py events.ndjson --mode ndjson --field payload.status --match '5\d\d'

# fallback: truncating grep over anything
scripts/jsonl-extract.py weird.log --mode text --match ERROR
```

Flags: `--mode auto|ndjson|transcript|text`, `--field a.b.c` (ndjson projection), `--match REGEX`, `-i`, `--max-chars N` (default 400), `--no-filter` (keep boilerplate), `--out PATH` (write to a file instead of context — prefer this for anything but a handful of hits).

Transcript mode understands the message schema: `text` blocks, `tool_use` inputs (truncated), and `tool_result` text; it tags each hit `L<line> <role>` and drops agent-listing / system-reminder / task-notification noise. It reads line by line, so file size is not a memory problem.

To pin a hit's surroundings: note the `L<line>` from a match, then `sed -n '<line>p' FILE` for that raw record, or read the neighbours.

## MCP fetches and trackers

- Prefer list/summary calls (e.g. Linear `list_issues`) over per-record fetches. `get_issue`-style calls return full descriptions + comments and are the classic single-oversized-result culprit — do not loop them.
- When a subagent must *edit* a large record, pass its current content in the dispatch prompt so it can do a surgical replace instead of re-fetching it into a small window.
- If you must read one big record, read it once, extract the fields you need to a note, and drop the raw body.

## Dispatch contract for spelunking subagents

Hand the agent the tool and the discipline, not the corpus:

1. Locate with `rg`/`sg`/`qsv`/the extractor; read only narrow windows.
2. Write findings to a named file (`scratch/<topic>.md`).
3. Return a short summary (≤~250 words) + explicit "could not determine", not raw dumps.

Agents that follow this finish; agents handed raw files or bulk fetches abort. Mirrors the read-discipline block in `~/.agents/AGENTS.md`.
