#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(git -C "$ROOT" rev-parse --show-toplevel)"
SETUP="$ROOT/scripts/setup-shared-agent-config.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

AGENTS="$TMP/agents"
CLAUDE="$TMP/claude"
CODEX="$TMP/codex"
HINDSIGHT="$TMP/hindsight"
mkdir -p "$AGENTS" "$CLAUDE" "$CODEX" "$HINDSIGHT/codex"

SENTINEL="$TMP/unrelated-guidance"
printf 'sentinel must remain unchanged\n' > "$SENTINEL"
ln -s "$SENTINEL" "$AGENTS/AGENTS.md"

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

TOKEN="runtime-token-$(date +%s)-$$-$RANDOM"
cat > "$HINDSIGHT/codex/hooks.json" <<JSON
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"python3 $HINDSIGHT/codex/session-start.py"}]}],"UserPromptSubmit":[{"hooks":[{"type":"command","command":"python3 $HINDSIGHT/codex/prompt.py"}]}],"Stop":[{"hooks":[{"type":"command","command":"python3 $HINDSIGHT/codex/stop.py"}]}]}}
JSON
cat > "$HINDSIGHT/codex.json" <<JSON
{"endpoint":"https://memory.invalid","apiToken":"$TOKEN","bankId":"old","dynamicBankId":true,"extra":"preserve"}
JSON

FAKE_BIN="$TMP/bin"
FAKE_CALLED="$TMP/hindsight-called"
mkdir -p "$FAKE_BIN"
cat > "$FAKE_BIN/hindsight" <<EOF
#!/usr/bin/env bash
printf 'unexpected invocation\n' > "$FAKE_CALLED"
exit 99
EOF
chmod +x "$FAKE_BIN/hindsight"

OUTPUT="$TMP/setup-output"
PATH="$FAKE_BIN:$PATH" bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" >"$OUTPUT" 2>&1
test ! -e "$FAKE_CALLED"

CANONICAL="$AGENTS/AGENTS.md"
test -f "$CANONICAL"
test ! -L "$CANONICAL"
test "$(cat "$SENTINEL")" = 'sentinel must remain unchanged'
canonical_backup=$(find "$AGENTS" -maxdepth 1 -name 'AGENTS.md.bak.*' -print -quit)
test -L "$canonical_backup"
test "$(readlink "$canonical_backup")" = "$SENTINEL"
test "$(grep -c '<important if=' "$CANONICAL")" -eq 3
grep -q 'Verify from the inside' "$CANONICAL"
grep -q 'Hindsight' "$CANONICAL"
grep -q 'claude_code' "$CANONICAL"
grep -q 'work stream' "$CANONICAL"
grep -q 'Hunk' "$CANONICAL"
if grep -Eqi 'Fable|Opus|lower power model|MCP tools' "$CANONICAL"; then exit 1; fi
echo 'shared guidance: PASS'

test "$(head -n 1 "$CLAUDE/CLAUDE.md")" = "@$CANONICAL"
test "$(grep -Fxc "@$CANONICAL" "$CLAUDE/CLAUDE.md")" -eq 1
test "$(grep -c '<important if=' "$CLAUDE/CLAUDE.md")" -eq 1
grep -q 'Fable or Opus' "$CLAUDE/CLAUDE.md"
if grep -q 'Verify from the inside' "$CLAUDE/CLAUDE.md"; then exit 1; fi
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
assert config["endpoint"] == "https://memory.invalid"
assert config["apiToken"].startswith("runtime-token-")
assert config["bankId"] == "claude_code"
assert config["dynamicBankId"] is False
assert config["extra"] == "preserve"
PY
if grep -Fq "$TOKEN" "$OUTPUT"; then exit 1; fi
if grep -R -Fq --exclude-dir=.git "$TOKEN" "$REPO_ROOT"; then exit 1; fi
echo 'shared Hindsight bank: PASS'

# Replacing a changed regular canonical file also preserves its content in a backup.
printf 'changed regular canonical guidance\n' > "$CANONICAL"
regular_backups_before=$(find "$AGENTS" -maxdepth 1 -name 'AGENTS.md.bak.*' | wc -l | tr -d ' ')
bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" >/dev/null
test "$(find "$AGENTS" -maxdepth 1 -name 'AGENTS.md.bak.*' | wc -l | tr -d ' ')" -gt "$regular_backups_before"
grep -q 'changed regular canonical guidance' "$AGENTS"/AGENTS.md.bak.*

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
