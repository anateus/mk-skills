#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLER="$ROOT/scripts/install-hooks.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

CLAUDE="$TMP/claude"
CODEX="$TMP/codex"
mkdir -p "$CLAUDE" "$CODEX"

cat > "$CLAUDE/settings.json" <<'JSON'
{"theme":"dark","hooks":{"SubagentStart":[{"hooks":[{"type":"command","command":"unrelated-claude"}]}]}}
JSON
cat > "$CODEX/hooks.json" <<'JSON'
{"version":1,"hooks":{"SubagentStop":[{"hooks":[{"type":"command","command":"unrelated-codex"}]}]}}
JSON

run_installer() {
  CLAUDE_CONFIG_DIR="$CLAUDE" CODEX_CONFIG_DIR="$CODEX" bash "$INSTALLER" "$@"
}

run_installer --all >/dev/null

for host_root in "$CLAUDE" "$CODEX"; do
  runtime="$host_root/hooks/mk-skills-artifact-discipline.js"
  test -L "$runtime"
  test "$(readlink "$runtime")" = "$ROOT/scripts/artifact-discipline.js"
done

ARTIFACT_ROOT="$TMP/artifacts"
hook_output="$(printf '%s' '{"hook_event_name":"SubagentStart","session_id":"session-1","agent_id":"agent-1"}' | MK_SKILLS_ARTIFACT_DIR="$ARTIFACT_ROOT" node "$CLAUDE/hooks/mk-skills-artifact-discipline.js")"
python3 - "$hook_output" "$ARTIFACT_ROOT" <<'PY'
import json, os, sys

output = json.loads(sys.argv[1])
artifact = os.path.join(sys.argv[2], "session-1", "agent-1", "findings.md")
assert artifact in output["hookSpecificOutput"]["additionalContext"]
assert os.path.isdir(os.path.dirname(artifact))
PY

python3 - "$CLAUDE/settings.json" "$CODEX/hooks.json" <<'PY'
import json, sys

claude, codex = (json.load(open(path, encoding="utf-8")) for path in sys.argv[1:])
assert claude["theme"] == "dark"
assert codex["version"] == 1

for config, unrelated in ((claude, "unrelated-claude"), (codex, "unrelated-codex")):
    commands = {
        hook["command"]
        for event in ("SubagentStart", "SubagentStop")
        for group in config["hooks"][event]
        for hook in group["hooks"]
    }
    assert unrelated in commands
    owned = [command for command in commands if "mk-skills-artifact-discipline.js" in command]
    assert len(owned) == 1
PY

claude_backups_before="$(find "$CLAUDE" -maxdepth 1 -name 'settings.json.bak.*' | wc -l | tr -d ' ')"
codex_backups_before="$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')"
run_installer --all >/dev/null
test "$(find "$CLAUDE" -maxdepth 1 -name 'settings.json.bak.*' | wc -l | tr -d ' ')" = "$claude_backups_before"
test "$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')" = "$codex_backups_before"

run_installer --uninstall --all >/dev/null
test ! -e "$CLAUDE/hooks/mk-skills-artifact-discipline.js"
test ! -e "$CODEX/hooks/mk-skills-artifact-discipline.js"

python3 - "$CLAUDE/settings.json" "$CODEX/hooks.json" <<'PY'
import json, sys

claude, codex = (json.load(open(path, encoding="utf-8")) for path in sys.argv[1:])
assert claude["hooks"]["SubagentStart"] == [{"hooks": [{"type": "command", "command": "unrelated-claude"}]}]
assert "SubagentStop" not in claude["hooks"]
assert codex["hooks"]["SubagentStop"] == [{"hooks": [{"type": "command", "command": "unrelated-codex"}]}]
assert "SubagentStart" not in codex["hooks"]
PY

PRISTINE="$TMP/pristine"
CLAUDE_CONFIG_DIR="$PRISTINE/claude" CODEX_CONFIG_DIR="$PRISTINE/codex" bash "$INSTALLER" --uninstall --all >/dev/null
test ! -e "$PRISTINE"

CONFLICT="$TMP/conflict"
mkdir -p "$CONFLICT/hooks"
printf 'user-owned\n' > "$CONFLICT/hooks/mk-skills-artifact-discipline.js"
if CLAUDE_CONFIG_DIR="$CONFLICT" bash "$INSTALLER" --claude >/dev/null 2>&1; then
  echo "installer replaced an unowned runtime" >&2
  exit 1
fi
grep -qx 'user-owned' "$CONFLICT/hooks/mk-skills-artifact-discipline.js"

printf 'ok\n'
