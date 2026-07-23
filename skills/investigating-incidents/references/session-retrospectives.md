# Session retrospectives

Use the bundled script to inventory Claude Code JSONL sessions without dumping raw command bodies or tool results:

```bash
python3 <skill-dir>/scripts/summarize-claude-sessions.py \
  ~/.claude/projects/<project>/<session>.jsonl \
  ~/.claude/projects/<project>/<another-session>.jsonl
```

Pass `--include-subagents` to include JSONL files under each session's `subagents/` directory. The report contains:

- direct user requests, truncated and redacted;
- tool-use counts;
- unique shell-command descriptions, not shell bodies;
- delegated investigation descriptions;
- candidate correction passages.

Treat the output as an index, not ground truth. Read the relevant raw transcript spans and referenced artifacts before extracting a durable skill or operational claim. Compacted summaries are useful navigation aids but can preserve conclusions that later evidence overturned.

Focus the retrospective on:

1. repeated commands that deserve a deterministic script;
2. repeated rediscovery that belongs in a reference;
3. premature conclusions and the discriminator that corrected them;
4. agent tasks that overlapped or lacked a report contract;
5. evidence or access gaps that should become observability work;
6. durable host-neutral behavior rather than incident-specific facts.
