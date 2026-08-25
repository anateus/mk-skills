# Profile guidance installation

The skills CLI installs files but does not run bundled scripts. After installing the skill, run `scripts/install-guidance.py` from the installed skill directory.

Install the skill globally for every supported agent:

```bash
pnpx skills add anateus/mk-skills \
  --skill personal-writing-style \
  --agent '*' \
  --global \
  --yes
```

Preview the named `## Personal writing style` section in both global instruction files:

```bash
python3 <installed-skill-dir>/scripts/install-guidance.py --all-global
```

Apply after reviewing the diff:

```bash
python3 <installed-skill-dir>/scripts/install-guidance.py --all-global --apply
```

The default profile is `~/.local/share/personal-writing-style/style-profile.md`. Record another location with `--profile PATH`. Target one file with `--into agents-global`, `--into claude-global`, or `--target PATH`.

The installer is dry-run by default. On apply, it backs up each existing target to `<target>.bak`, then adds or replaces only the `personal-writing-style:profile` managed block. Re-running does not duplicate the section. Missing target files require `--create`, and their parent directories must already exist.

If global `CLAUDE.md` already imports global `AGENTS.md`, `--all-global` writes the block only to `AGENTS.md` and reports that Claude inherits it. This avoids loading the same guidance twice.

The installed section tells agents when to read the profile. It also tells them not to read the raw corpus unless the user asks to rebuild or audit the profile.
