# Corpus extraction

The bundled Go command scans all selected stores, keeps only user-authored text, deduplicates exact repeats, and selects a deterministic sample per source. It writes gzip-compressed NDJSON with `id`, `source`, `timestamp`, `word_count`, and `text`. It omits recipients, channel names, subjects, project paths, and account identifiers.

## Run

First inspect the sample frame without writing text:

```bash
scripts/writing-corpus --dry-run
```

Then write the private corpus outside the repository:

```bash
scripts/writing-corpus \
  --output "${XDG_DATA_HOME:-$HOME/.local/share}/personal-writing-style/corpus.jsonl.gz"
```

The default keeps 5,000 deterministic samples per source, rejects messages shorter than 8 characters, and truncates each sample at 12,000 characters. Use `--max-per-source 0` only when the full text is needed. The output mode is `0600`. The file is gzip data regardless of its suffix; use `.jsonl.gz` so downstream tools detect it correctly.

The JSON stats printed to stderr define the observed frame: author-attributed rows inspected, eligible candidates, exact duplicates, emitted samples, unavailable sources, and attributed iMessage bodies skipped. Retain these counts with any profile derived from the corpus.

## Sources

| Source | Default input | Selection |
|---|---|---|
| Claude | `~/.claude/projects/**/*.jsonl` | Main-session string and text-block prompts; tool results, sidechains, and subagents excluded |
| Codex | `~/.codex/sessions/**/*.jsonl` | User `input_text`; injected AGENTS and environment blocks excluded |
| iMessage | `~/Library/Messages/chat.db` | Plain-text outgoing messages; reactions and received messages excluded |
| Mimestream | sandboxed `Mimestream.sqlite` | Sent messages with cached plain-text or HTML bodies; quoted reply history trimmed |
| Slack | A standard Slack export | Messages matching explicit `--slack-user-id` |

Override any path with `--claude-dir`, `--codex-dir`, `--imessage-db`, or `--mimestream-db`. Select a subset with `--sources claude,codex`.

For Slack:

```bash
scripts/writing-corpus \
  --slack-export /path/to/slack-export \
  --slack-user-id U123456 \
  --output /private/path/corpus.jsonl.gz
```

Slack's local desktop cache is LevelDB and does not provide a reliable author-filtered corpus. Use an official export or a tool such as [slackdump](https://github.com/rusq/slackdump), subject to workspace policy. Slackdump can create incremental archives but may trigger enterprise security alerts.

Most outgoing iMessages have a `text` value. The command reports and skips rows available only as Apple's attributed-body format. [imessage-exporter](https://github.com/ReagentX/imessage-exporter) and its Rust library decode that format comprehensively, but linking the GPL library into this MIT repository would change distribution obligations.

## Performance and failure behavior

The command streams JSONL and SQLite query results. A hash heap bounds retained text to the requested sample size; the exact-deduplication hash set scales with eligible candidates. It compresses only the selected output, using gzip's fast level. The wrapper caches the compiled Go binary and rebuilds it when its source changes.

Inspect the corpus without expanding it on disk:

```bash
gzip -dc /private/path/corpus.jsonl.gz | jq -c 'select(.source == "claude")' | head
```

Missing default stores appear as unavailable in stats and do not stop other sources. Schema, permission, or parsing failures appear in that source's `error` field. Do not describe a source as represented unless `available` is true and its emitted count is nonzero.
