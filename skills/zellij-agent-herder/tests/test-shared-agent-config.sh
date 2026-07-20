#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETUP="$ROOT/scripts/setup-shared-agent-config.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

AGENTS="$TMP/agents"
CLAUDE="$TMP/claude"
CODEX="$TMP/codex"
HINDSIGHT="$TMP/hindsight"
mkdir -p "$AGENTS" "$CLAUDE" "$CODEX" "$HINDSIGHT/codex"

cat > "$CLAUDE/CLAUDE.md" <<'EOF'
# CLAUDE.md

<important if="the model is Fable or Opus">
For all coding tasks use your judgement to delegate to an appropriate lower power model.
</important>

<important if="you are inside a zellij session and have just finished a coding task with changes to review">
Use the zellij-agent-herder skill to open /hunk-review.
</important>

<important if="you are about to save a memory, recall past context, or decide which memory system to use">
Use Hindsight MCP tools and bank claude_code as primary memory.
</important>

<important if="you are about to state, document, or rely on what a project uses or how it works">
Verify from the inside, not the surface.
</important>
EOF

cat > "$CODEX/AGENTS.md" <<'EOF'
unrelated existing Codex guidance
EOF
cat > "$CODEX/hooks.json" <<'JSON'
{"version":1,"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"zellij-origin"}]}],"Stop":[{"hooks":[{"type":"command","command":"unrelated-stop"}]}]}}
JSON

TOKEN='fixture-token-must-never-leak'
cat > "$HINDSIGHT/codex/hooks.json" <<JSON
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"python3 $HINDSIGHT/codex/session-start.py"}]}],"UserPromptSubmit":[{"hooks":[{"type":"command","command":"python3 $HINDSIGHT/codex/prompt.py"}]}],"Stop":[{"hooks":[{"type":"command","command":"python3 $HINDSIGHT/codex/stop.py"}]}]}}
JSON
cat > "$HINDSIGHT/codex.json" <<JSON
{"endpoint":"https://memory.invalid","apiToken":"$TOKEN","bankId":"old","dynamicBankId":true,"extra":"preserve"}
JSON

OUTPUT="$TMP/stdout"
bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" >"$OUTPUT"

CANONICAL="$AGENTS/AGENTS.md"
test -f "$CANONICAL"
test "$(grep -c '<important if=' "$CANONICAL")" -eq 3
grep -q 'Verify from the inside' "$CANONICAL"
grep -q 'Hindsight' "$CANONICAL"
grep -q 'claude_code' "$CANONICAL"
grep -q 'work stream' "$CANONICAL"
grep -q 'Hunk' "$CANONICAL"
! grep -Eqi 'Fable|Opus|lower power model|MCP tools' "$CANONICAL"
echo 'shared guidance: PASS'

test "$(head -n 1 "$CLAUDE/CLAUDE.md")" = "@$CANONICAL"
test "$(grep -Fxc "@$CANONICAL" "$CLAUDE/CLAUDE.md")" -eq 1
test "$(grep -c '<important if=' "$CLAUDE/CLAUDE.md")" -eq 1
grep -q 'Fable or Opus' "$CLAUDE/CLAUDE.md"
! grep -q 'Verify from the inside' "$CLAUDE/CLAUDE.md"
echo 'Claude overlay: PASS'

test -L "$CODEX/AGENTS.md"
test "$(readlink "$CODEX/AGENTS.md")" = "$CANONICAL"
compgen -G "$CODEX/AGENTS.md.bak.*" >/dev/null
grep -q 'unrelated existing' "$CODEX"/AGENTS.md.bak.*
echo 'Codex symlink: PASS'

python3 - "$CODEX/hooks.json" "$HINDSIGHT/codex.json" <<'PY'
import json, sys
hooks, config = (json.load(open(path)) for path in sys.argv[1:])
assert hooks["version"] == 1
assert {"SessionStart", "UserPromptSubmit", "Stop"} <= set(hooks["hooks"])
commands = {event: [hook.get("command", "") for group in hooks["hooks"][event] for hook in group.get("hooks", [])] for event in hooks["hooks"]}
assert "zellij-origin" in commands["SessionStart"]
assert "unrelated-stop" in commands["Stop"]
assert any("session-start.py" in value for value in commands["SessionStart"])
assert any("prompt.py" in value for value in commands["UserPromptSubmit"])
assert any("stop.py" in value for value in commands["Stop"])
assert config == {"endpoint":"https://memory.invalid", "apiToken":"fixture-token-must-never-leak", "bankId":"claude_code", "dynamicBankId":False, "extra":"preserve"}
PY
! grep -Fq "$TOKEN" "$OUTPUT"
! grep -R -Fq "$TOKEN" "$ROOT"
echo 'shared Hindsight bank: PASS'

# A second run is idempotent: one import and one copy of every official hook.
hook_backups_before=$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')
config_backups_before=$(find "$HINDSIGHT" -maxdepth 1 -name 'codex.json.bak.*' | wc -l | tr -d ' ')
bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" >/dev/null
test "$(grep -Fxc "@$CANONICAL" "$CLAUDE/CLAUDE.md")" -eq 1
test "$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')" -eq "$hook_backups_before"
test "$(find "$HINDSIGHT" -maxdepth 1 -name 'codex.json.bak.*' | wc -l | tr -d ' ')" -eq "$config_backups_before"
python3 - "$CODEX/hooks.json" <<'PY'
import json, sys
hooks = json.load(open(sys.argv[1]))["hooks"]
for event, needle in (("SessionStart", "session-start.py"), ("UserPromptSubmit", "prompt.py"), ("Stop", "stop.py")):
    commands = [hook.get("command", "") for group in hooks[event] for hook in group.get("hooks", [])]
    assert sum(needle in value for value in commands) == 1
PY
