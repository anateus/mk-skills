"""Exercise Redocly against synthetic HAR data; no proxy or AI invocation."""

import json
import subprocess
from pathlib import Path


def run(*args, expected=0):
    result = subprocess.run(
        ["./node_modules/.bin/redocly", *args],
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected, (args, result.stdout, result.stderr)


run(
    "generate-spec", "synthetic.har",
    "--server", "https://api.example.invalid",
    "--title", "Synthetic",
    "-o", "generated.openapi.yaml",
)
run("lint", "generated.openapi.yaml", "--extends", "spec")
run("bundle", "generated.openapi.yaml", "-o", "generated.openapi.json")

spec = json.loads(Path("generated.openapi.json").read_text())
methods = {"get", "post", "delete", "put", "patch", "options", "head"}
operations = [
    {"method": method, "path": path, "responses": list(operation["responses"])}
    for path, path_item in spec["paths"].items()
    for method, operation in path_item.items()
    if method in methods
]
assert spec["openapi"] == "3.2.0"
assert len(operations) == 3
assert any(o["method"] == "post" and "201" in o["responses"] for o in operations)
assert any(o["method"] == "delete" and "204" in o["responses"] for o in operations)
assert any("{" in o["path"] and o["method"] == "get" for o in operations)

run(
    "drift", "synthetic.har", "--api", "generated.openapi.json",
    "--format", "json", "-o", "baseline-drift.json",
)
baseline = json.loads(Path("baseline-drift.json").read_text())
assert baseline["run"]["totalExchanges"] == 4
assert baseline["run"]["totalProblems"] == 0

har = json.loads(Path("synthetic.har").read_text())
content = har["log"]["entries"][0]["response"]["content"]
body = json.loads(content["text"])
body["name"] = 123
content["text"] = json.dumps(body)
Path("mutated.har").write_text(json.dumps(har, indent=2) + "\n")
run(
    "drift", "mutated.har", "--api", "generated.openapi.json",
    "--format", "json", "-o", "mutation-drift.json", expected=1,
)
mutation = json.loads(Path("mutation-drift.json").read_text())
assert mutation["run"]["findingsBySeverity"]["error"] == 1
assert any(
    p["ruleId"] == "schema-consistency" and p["dataPath"] == "/name"
    for p in mutation["problems"]
)

result = {
    "redoclyVersion": "2.53.0",
    "syntheticExchanges": 4,
    "openapi": spec["openapi"],
    "operations": operations,
    "baselineProblems": baseline["run"]["totalProblems"],
    "mutationErrors": mutation["run"]["findingsBySeverity"]["error"],
    "scope": "Local HAR generation, specification lint, bundle, and drift; AI disabled.",
}
Path("results.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
