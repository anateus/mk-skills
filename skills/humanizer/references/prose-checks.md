# Prose checks

Vale scans locally using bundled YAML rules. The Python wrapper summarizes its output; it neither rewrites text nor calls an LLM. Editing still needs judgment about voice, evidence, structure, and meaning. Counts are cues to inspect, not a score or proof of AI authorship. The rules cover English prose and a subset of the catalog.

Install [Vale](https://vale.sh/docs/install) 3.20 or newer once (`brew install vale` on macOS). Python 3.9 or newer is sufficient. Ordinary scans require no network or package sync. The explicit configuration ignores host-global Vale styles.

```bash
python3 "<skill-base-dir>/scripts/prose-check.py" draft.md
python3 "<skill-base-dir>/scripts/prose-check.py" draft.md --details StockWords
python3 "<skill-base-dir>/scripts/prose-check.py" draft.md --details all --max-findings 50
python3 "<skill-base-dir>/scripts/prose-check.py" --explain Contrasts
python3 "<skill-base-dir>/scripts/prose-check.py" draft.md --json
```

Use `-` for stdin. Markdown is the default format, including plain prose; use `--format txt` to treat every character as prose. Markdown scans exclude frontmatter, code, link destinations, and blockquotes. Quoted source prose elsewhere can still match: preserve quotations when editing. Locations refer to the original input. Findings are ordered by location, limited to 20 by default, and match excerpts stop at 240 characters. Counts include all matches even when details are omitted. `--details RULE` selects just that rule; `--explain RULE` prints its examples from [the catalog](signs-of-ai-writing.md).

The initial tiers are:

| Tier | Rules | Treatment |
|---|---|---|
| Strong | StageOpeners, ChatResidue, StockPhrases | Show locations and matched text. Review in context; no automatic replacements. |
| Weak | StockWords, Contrasts, Hedges, Dashes, Bold | Show counts, then drill down when a cluster or the writer's preferences warrants it. |

Edit `styles/Humanizer/*.yml` to adjust words, regex patterns, exceptions, or severity. `warning` produces strong details; `suggestion` produces weak counts. Add a `rules.json` entry pointing to the applicable catalog section when adding a rule. Use [Vale's existence rules](https://docs.vale.sh/checks/existence) for word lists and patterns, and scoped rules for formatting. Preserve `~text.frontmatter` on general prose rules. Run `python3 -B tests/humanizer/test_prose_check.py -v` from the mk-skills source repository after changing configuration.

Exit 0 means the scan succeeded, including scans with findings. Exit 2 means it failed, so no clean report can be claimed. Grammar and spelling are separate concerns; optional house rules can use Vale's spelling support, while LanguageTool offers broader grammar checks. Neither is needed for this detector.
