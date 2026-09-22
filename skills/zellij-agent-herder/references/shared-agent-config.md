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

## Jcode memory

Jcode uses native automatic memory for fine-grained recall and Hindsight for explicit, coarser knowledge shared across harnesses. Keep both enabled. The generated guidance asks agents to promote verified decisions, stable preferences, reusable findings, and corrections at meaningful milestones, then retain short native summaries with Hindsight page or document IDs when useful. Corrections update both known copies through supported tools. Recalled facts are not new evidence and should not be copied back automatically.

The existing Jcode adapter's startup and turn/session retention hooks provide secondary recovery. They do not inject recall into the prompt or synchronize the two databases. Keep explicit Hindsight lookup and milestone writes, and report any failed side of a linked update. Retention submission also does not prove successful server-side extraction. Neither store bypasses account and data restrictions.

This helper configures Claude and Codex, not Jcode hooks. It rewrites the canonical shared guidance from its template, so do not rerun it merely to update one paragraph in a customized `AGENTS.md`. Back up that file and replace only its memory-policy block instead. Preserve an existing `~/AGENTS.md` symlink to the canonical file. No native memory export, import, deletion, or provider change is needed for this policy.
