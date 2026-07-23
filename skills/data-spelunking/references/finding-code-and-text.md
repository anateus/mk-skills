# Finding: ripgrep and ast-grep

Two locators. `rg` for text/lines; `ast-grep` when the pattern is *structure* (a call shape, a definition, a JSX element) that text search matches noisily or misses across formatting.

## ripgrep (`rg`)

Locate, then window — the goal is line numbers, not content dumps.

```
rg -n PATTERN path/                 # line numbers (feed to Read offset/limit)
rg -n -i PATTERN                    # case-insensitive
rg -l PATTERN                       # files-with-matches only (cheapest survey)
rg -c PATTERN                       # count per file
rg -n -A3 -B3 PATTERN               # 3 lines of context each side
rg -n -tpy PATTERN                  # restrict to a filetype (py, ts, js, go…)
rg -n -g '!test/**' -g '!*.min.js' PATTERN   # glob include/exclude
rg -nU 'foo[\s\S]*?bar' file        # multiline (-U); keep patterns lazy
rg -n --json PATTERN | jq …         # structured hits for scripting
```

Survey pattern: `rg -l` to find the files, then `rg -n` in the one that matters, then `Read` a ±20-line window around the hit. Do not `rg` a pattern that returns thousands of lines into context — add `-l`/`-c`/`head`, or pipe to a file (see the large-outputs reference).

## ast-grep (`sg`)

Syntax-aware search/rewrite. Metavariables: `$X` (one node), `$$$` (a list, e.g. args/statements). Language via `-l`.

```
sg run -p 'buildAssistantConfig($$$)' -l ts src/       # every call, any args
sg run -p 'const $X = require($Y)' -l js               # a binding shape
sg run -p 'model: { $$$ }' -l ts                        # an object-literal shape
sg run -p 'foo($A)' --json                              # structured matches
sg run -p '$X == null' --rewrite '$X === null' -l ts -U # structural rewrite (preview; -U/--update-all to apply)
```

Use `sg` over `rg` when: the thing you want spans lines or reformats (multiline calls, object literals), when text matches would be swamped by comments/strings, or when you want a safe mechanical rewrite. Use `rg` when the target is a literal string, a log line, an identifier occurrence count, or any non-code text — it is faster and needs no grammar.

Confirm the grammar covers the language (`sg run -p x -l LANG` errors if not). For odd dialects, fall back to `rg` with a tolerant multiline pattern.
