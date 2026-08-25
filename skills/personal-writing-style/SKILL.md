---
name: personal-writing-style
description: Extract the user's own writing from local Claude and Codex transcripts, iMessage, Mimestream, or Slack exports; infer a source-aware style profile; and apply it when drafting or rewriting in the user's voice. Use when asked to learn, analyze, imitate, or write in the user's personal style. Do not use for generic prose cleanup without a personal corpus or profile.
---

# Personal writing style

Learn recurring choices in the user's writing, then reproduce those choices without changing facts or inventing experiences.

## Choose the task

- To build or refresh a corpus, read [corpus extraction](references/corpus-extraction.md). Access private message stores only when the user has asked for extraction. Keep corpus files outside repositories and shared directories.
- To infer or update the style profile, read [style profiling](references/style-profiling.md). Treat each medium as its own sample frame. Separate stable habits from email, chat, and coding-prompt variants.
- To draft or rewrite, load the user's existing style profile and select the closest medium. Use the path named in the host's `## Personal writing style` guidance section. If no section exists, use `~/.local/share/personal-writing-style/style-profile.md` when present. Preserve meaning, quoted text, identifiers, code, required format, and confidence. Do not copy accidental typos or private details merely because they appear in samples.
- To install or update the always-on profile locator in `AGENTS.md` or `CLAUDE.md`, read [profile guidance installation](references/profile-guidance-installation.md).

## Applying the profile

Follow stable traits first, then the relevant medium variant. Prefer several evidenced habits over conspicuous imitation of one phrase. When the requested genre is absent from the profile, use stable traits and state that the medium-specific match is inferred.

If the profile conflicts with a contract, safety requirement, or the user's current instruction, follow the stronger constraint. Never add a personal anecdote, opinion, relationship, or claim that the user did not supply.

After drafting, compare the result with the profile's positive traits and avoid list. Remove copied names, addresses, message fragments, and other corpus residue.
