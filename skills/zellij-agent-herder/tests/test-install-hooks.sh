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
{"theme":"dark","hooks":{"Stop":[{"hooks":[{"type":"command","command":"unrelated-claude"}]}]}}
JSON
cat > "$CODEX/hooks.json" <<'JSON'
{"version":1,"hooks":{"Stop":[{"hooks":[{"type":"command","command":"unrelated-codex"}]}]}}
JSON

run_installer() {
  CLAUDE_CONFIG_DIR="$CLAUDE" CODEX_CONFIG_DIR="$CODEX" bash "$INSTALLER" "$@"
}

run_installer --all >/dev/null
test -x "$CLAUDE/hooks/zellij-agent-status.sh"
test -x "$CLAUDE/hooks/hunk-autodiff.sh"
test -x "$CLAUDE/hooks/zellij-origin.sh"
test -x "$CODEX/hooks/zellij-agent-status.sh"
test -x "$CODEX/hooks/hunk-autodiff.sh"
test -x "$CODEX/hooks/zellij-origin.sh"
compgen -G "$CLAUDE/settings.json.bak.*" >/dev/null
compgen -G "$CODEX/hooks.json.bak.*" >/dev/null
run_installer --all >/dev/null

python3 - "$CLAUDE/settings.json" "$CODEX/hooks.json" <<'PY'
import json, sys
c, x = map(lambda p: json.load(open(p)), sys.argv[1:])
assert c["theme"] == "dark"
assert x["version"] == 1
assert sum("zellij-origin.sh" in h.get("command", "") for g in c["hooks"]["SessionStart"] for h in g["hooks"]) == 1
assert sum("hunk-autodiff.sh" in h.get("command", "") for g in x["hooks"]["PostToolUse"] for h in g["hooks"]) == 1
assert all("async" not in h for g in x["hooks"]["PostToolUse"] for h in g["hooks"])
assert any("unrelated" in h.get("command", "") for g in x["hooks"]["Stop"] for h in g["hooks"])
assert any(g.get("matcher") == "apply_patch|Edit|Write" and any("hunk-autodiff.sh" in h.get("command", "") for h in g["hooks"]) for g in x["hooks"]["PostToolUse"])
assert {"UserPromptSubmit", "Stop", "Notification", "SessionEnd", "SessionStart", "PostToolUse"} <= set(c["hooks"])
assert {"UserPromptSubmit", "PermissionRequest", "Stop", "SessionStart", "PostToolUse"} <= set(x["hooks"])
PY
echo "Claude install: PASS"
echo "Codex install: PASS"

claude_before=$(find "$CLAUDE" -maxdepth 1 -name 'settings.json.bak.*' | wc -l | tr -d ' ')
codex_before=$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')
run_installer --uninstall --all >/dev/null
claude_after=$(find "$CLAUDE" -maxdepth 1 -name 'settings.json.bak.*' | wc -l | tr -d ' ')
codex_after=$(find "$CODEX" -maxdepth 1 -name 'hooks.json.bak.*' | wc -l | tr -d ' ')
test "$claude_after" -gt "$claude_before"
test "$codex_after" -gt "$codex_before"

python3 - "$CLAUDE/settings.json" "$CODEX/hooks.json" <<'PY'
import json, sys
for path in sys.argv[1:]:
    cfg = json.load(open(path))
    commands = [h.get("command", "") for groups in cfg.get("hooks", {}).values() for g in groups for h in g.get("hooks", [])]
    assert any("unrelated" in command for command in commands)
    assert not any(any(name in command for name in ("zellij-agent-status.sh", "hunk-autodiff.sh", "zellij-origin.sh")) for command in commands)
PY
for root in "$CLAUDE" "$CODEX"; do
  test ! -e "$root/hooks/zellij-agent-status.sh"
  test ! -e "$root/hooks/hunk-autodiff.sh"
  test ! -e "$root/hooks/zellij-origin.sh"
done
echo "uninstall preservation: PASS"
