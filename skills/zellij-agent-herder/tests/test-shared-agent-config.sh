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
SOURCE="$TMP/hindsight-source"
mkdir -p "$AGENTS" "$CLAUDE" "$CODEX" "$HINDSIGHT" "$SOURCE/hooks" "$SOURCE/scripts"

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
cat > "$SOURCE/hooks/hooks.json" <<'JSON'
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"python3 __SCRIPTS_DIR__/session-start.py"}]}],"UserPromptSubmit":[{"hooks":[{"type":"command","command":"python3 __SCRIPTS_DIR__/prompt.py"}]}],"Stop":[{"hooks":[{"type":"command","command":"python3 __SCRIPTS_DIR__/stop.py"}]}]}}
JSON
printf '{"integration":"official-codex"}\n' > "$SOURCE/settings.json"
for script in session-start.py prompt.py stop.py; do
  printf '#!/usr/bin/env python3\n' > "$SOURCE/scripts/$script"
done
chmod 755 "$SOURCE/scripts/session-start.py" "$SOURCE/scripts/stop.py"
chmod 644 "$SOURCE/scripts/prompt.py"
chmod 640 "$SOURCE/settings.json" "$SOURCE/hooks/hooks.json"
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
if PATH="$FAKE_BIN:$PATH" bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" >"$OUTPUT" 2>&1; then
  exit 1
fi
test ! -e "$FAKE_CALLED"
test ! -e "$HINDSIGHT/codex"

PATH="$FAKE_BIN:$PATH" bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" --hindsight-source "$SOURCE" >"$OUTPUT" 2>&1
test ! -e "$FAKE_CALLED"
test -f "$HINDSIGHT/codex/hooks.json"
test -f "$HINDSIGHT/codex/settings.json"
test -x "$HINDSIGHT/codex/scripts/session-start.py"
test ! -x "$HINDSIGHT/codex/scripts/prompt.py"
test -x "$HINDSIGHT/codex/scripts/stop.py"
python3 - "$SOURCE/hooks/hooks.json" "$HINDSIGHT/codex/hooks.json" "$SOURCE/settings.json" "$HINDSIGHT/codex/settings.json" <<'PY'
import os, stat, sys
for source, installed in zip(sys.argv[1::2], sys.argv[2::2]):
    assert stat.S_IMODE(os.stat(source).st_mode) == stat.S_IMODE(os.stat(installed).st_mode)
PY
if grep -R -Fq '__SCRIPTS_DIR__' "$HINDSIGHT/codex"; then exit 1; fi
grep -Fq "$HINDSIGHT/codex/scripts/session-start.py" "$HINDSIGHT/codex/hooks.json"

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
bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" --hindsight-source "$SOURCE" >/dev/null
test "$(find "$AGENTS" -maxdepth 1 -name 'AGENTS.md.bak.*' | wc -l | tr -d ' ')" -gt "$regular_backups_before"
grep -q 'changed regular canonical guidance' "$AGENTS"/AGENTS.md.bak.*

# A second run is idempotent: one import and one copy of every official hook.
hook_backups_before=$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')
config_backups_before=$(find "$HINDSIGHT" -maxdepth 1 -name 'codex.json.bak.*' | wc -l | tr -d ' ')
integration_backups_before=$(find "$HINDSIGHT" -maxdepth 1 -name 'codex.bak.*' | wc -l | tr -d ' ')
bash "$SETUP" --agents-dir "$AGENTS" --claude-dir "$CLAUDE" --codex-dir "$CODEX" --hindsight-dir "$HINDSIGHT" --hindsight-source "$SOURCE" >/dev/null
test "$(grep -Fxc "@$CANONICAL" "$CLAUDE/CLAUDE.md")" -eq 1
test "$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')" -eq "$hook_backups_before"
test "$(find "$HINDSIGHT" -maxdepth 1 -name 'codex.json.bak.*' | wc -l | tr -d ' ')" -eq "$config_backups_before"
test "$(find "$HINDSIGHT" -maxdepth 1 -name 'codex.bak.*' | wc -l | tr -d ' ')" -eq "$integration_backups_before"
python3 - "$CODEX/hooks.json" <<'PY'
import json, sys
hooks = json.load(open(sys.argv[1]))["hooks"]
for event, needle in (("SessionStart", "session-start.py"), ("UserPromptSubmit", "prompt.py"), ("Stop", "stop.py")):
    commands = [hook.get("command", "") for group in hooks[event] for hook in group.get("hooks", [])]
    assert sum(needle in value for value in commands) == 1
PY

# Explicit sources are rejected when required files are missing or content escapes via symlink.
BAD_SOURCE="$TMP/bad-source"
mkdir -p "$BAD_SOURCE/hooks" "$BAD_SOURCE/scripts" "$TMP/outside"
cp "$SOURCE/hooks/hooks.json" "$BAD_SOURCE/hooks/hooks.json"
cp "$SOURCE/settings.json" "$BAD_SOURCE/settings.json"
ln -s "$TMP/outside/escaped.py" "$BAD_SOURCE/scripts/escaped.py"
BAD_HINDSIGHT="$TMP/bad-hindsight"
if bash "$SETUP" --agents-dir "$TMP/bad-agents" --claude-dir "$TMP/bad-claude" --codex-dir "$TMP/bad-codex" --hindsight-dir "$BAD_HINDSIGHT" --hindsight-source "$BAD_SOURCE" >/dev/null 2>&1; then
  exit 1
fi
test ! -e "$BAD_HINDSIGHT/codex"

MALFORMED_SOURCE="$TMP/malformed-source"
mkdir -p "$MALFORMED_SOURCE/hooks" "$MALFORMED_SOURCE/scripts"
printf 'not json\n' > "$MALFORMED_SOURCE/hooks/hooks.json"
printf '{}\n' > "$MALFORMED_SOURCE/settings.json"
if bash "$SETUP" --agents-dir "$TMP/malformed-agents" --claude-dir "$TMP/malformed-claude" --codex-dir "$TMP/malformed-codex" --hindsight-dir "$TMP/malformed-hindsight" --hindsight-source "$MALFORMED_SOURCE" >/dev/null 2>&1; then
  exit 1
fi
test ! -e "$TMP/malformed-hindsight/codex"
