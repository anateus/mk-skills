# Tabular and JSON: qsv, jq, yq

Never `cat` a large CSV or pretty-print a large JSON into context. These stream or project so only the slice you need is materialized.

## qsv (CSV / TSV)

Reads streaming — safe on multi-GB files. Start by learning the shape, then narrow.

```
qsv headers f.csv                       # column names + indices (do this first)
qsv count f.csv                         # row count, no load
qsv sample 10 f.csv                     # random 10 rows to eyeball shape
qsv slice -s 0 -e 20 f.csv              # first 20 rows
qsv select col1,col5 f.csv              # project columns
qsv search -s status '^5\d\d$' f.csv    # filter rows where a column matches RE
qsv frequency -s status f.csv           # value distribution for a column
qsv stats f.csv                         # per-column type/min/max/mean/nulls
qsv sqlp f.csv "select a, count(*) from _ group by a"   # SQL over the file
```

Chain: `qsv search -s col RE f.csv | qsv select a,b | qsv slice -e 50`. Pipe the final small result to context; keep the big intermediate on disk. `-T` for TSV. For column stats/nulls before deciding a query, `qsv stats` + `qsv frequency` answer most "which values, how many, any nulls" questions without reading rows.

## jq (JSON) / yq (YAML)

Project *before* printing; a whole parsed document in context is the thing to avoid.

```
jq '.a.b'            f.json             # one path
jq -c '.items[]'     f.json             # compact, one per line
jq '.items | length' f.json             # aggregate, not dump
jq '.items[] | {id, status}' f.json     # keep only needed fields
jq -r '.items[].name' f.json            # raw strings (no quotes)
jq '.. | .error? // empty' f.json       # recursive: pull every .error present
yq '.services.web.image' f.yaml         # same grammar as jq, for YAML
yq -o=json '.' f.yaml | jq …            # YAML → JSON to reuse jq recipes
```

For **NDJSON / line-delimited JSON** (one object per line, incl. many log formats and Claude Code session transcripts) prefer the bundled `scripts/jsonl-extract.py` — `jq` on such files works but returns whole objects; the extractor filters by regex and returns bounded, line-referenced snippets. See the large-outputs reference.

Rule of thumb: if `jq`/`qsv` output would still be large, add a projection, a `length`/`frequency`/`stats`, or a `head` — or send it to a file and slice.
