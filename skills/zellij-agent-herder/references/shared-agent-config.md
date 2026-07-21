# Shared agent configuration

Use the setup helper to share host-neutral guidance and the `claude_code` Hindsight bank between Claude and Codex:

```bash
bash "<skill-base-dir>/scripts/setup-shared-agent-config.sh"
```

The helper backs up changed personal configuration, preserves credentials, imports shared `AGENTS.md` guidance into Claude, and links Codex to the same guidance. Ordinary setup does not download missing Hindsight integrations.

If the official Codex integration already exists in a trusted local checkout, install from that local source:

```bash
bash "<skill-base-dir>/scripts/setup-shared-agent-config.sh" --hindsight-source <official-codex-integration-dir>
```

The source must contain regular hook declarations, settings, and scripts. The installer rejects symlinks and malformed layouts, stages a local copy under the Hindsight configuration directory, substitutes installed paths, and applies shared configuration. Review backups and run the helper's validation before relying on the result.
