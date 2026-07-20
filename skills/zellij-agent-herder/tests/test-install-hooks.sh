#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INSTALLER="$ROOT/scripts/install-hooks.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
CLAUDE="$TMP/claude"
CODEX="$TMP/codex"
mkdir -p "$CLAUDE" "$CODEX"

PRISTINE_CLAUDE="$TMP/pristine-claude"
PRISTINE_CODEX="$TMP/pristine-codex"
CLAUDE_CONFIG_DIR="$PRISTINE_CLAUDE" CODEX_CONFIG_DIR="$PRISTINE_CODEX" bash "$INSTALLER" --uninstall --all
test ! -e "$PRISTINE_CLAUDE"
test ! -e "$PRISTINE_CODEX"

ORPHAN_CLAUDE="$TMP/orphan-claude"
mkdir -p "$ORPHAN_CLAUDE/hooks"
touch "$ORPHAN_CLAUDE/hooks/zellij-agent-status.sh" "$ORPHAN_CLAUDE/hooks/unrelated.sh"
CLAUDE_CONFIG_DIR="$ORPHAN_CLAUDE" CODEX_CONFIG_DIR="$PRISTINE_CODEX" bash "$INSTALLER" --uninstall --claude
test ! -e "$ORPHAN_CLAUDE/hooks/zellij-agent-status.sh"
test -e "$ORPHAN_CLAUDE/hooks/unrelated.sh"
test ! -e "$ORPHAN_CLAUDE/settings.json"

printf ' { "hooks" : { "Stop" : [ { "hooks" : [ { "command" : "unrelated-only" } ] } ], "EmptyEvent" : [ ], "EmptyGroup" : [ { "hooks" : [ ] } ] } } \n' > "$CLAUDE/settings.json"
cp "$CLAUDE/settings.json" "$TMP/unrelated-before.json"
CLAUDE_CONFIG_DIR="$CLAUDE" CODEX_CONFIG_DIR="$CODEX" bash "$INSTALLER" --uninstall --claude
cmp "$TMP/unrelated-before.json" "$CLAUDE/settings.json"
test -z "$(find "$CLAUDE" -maxdepth 1 -name 'settings.json.bak.*' -print)"

cat > "$CLAUDE/settings.json" <<'JSON'
{"theme":"dark","hooks":{"Stop":[{"hooks":[{"type":"command","command":"unrelated-claude"}]}],"EmptyEvent":[],"EmptyGroup":[{"matcher":"keep-claude","hooks":[]}]}}
JSON
cat > "$CODEX/hooks.json" <<'JSON'
{"version":1,"hooks":{"Stop":[{"hooks":[{"type":"command","command":"unrelated-codex"}]}],"EmptyEvent":[],"EmptyGroup":[{"matcher":"keep-codex","hooks":[]}]}}
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
assert c["hooks"]["EmptyEvent"] == []
assert c["hooks"]["EmptyGroup"] == [{"matcher": "keep-claude", "hooks": []}]
assert x["hooks"]["EmptyEvent"] == []
assert x["hooks"]["EmptyGroup"] == [{"matcher": "keep-codex", "hooks": []}]
assert sum("zellij-origin.sh" in h.get("command", "") for g in c["hooks"]["SessionStart"] for h in g["hooks"]) == 1
assert sum("hunk-autodiff.sh" in h.get("command", "") for g in x["hooks"]["PostToolUse"] for h in g["hooks"]) == 1
assert all(h.get("async") is True for g in c["hooks"]["PostToolUse"] for h in g["hooks"] if "hunk-autodiff.sh" in h.get("command", ""))
assert all("async" not in h for g in x["hooks"]["PostToolUse"] for h in g["hooks"])
assert any("unrelated" in h.get("command", "") for g in x["hooks"]["Stop"] for h in g["hooks"])
assert any(g.get("matcher") == "apply_patch|Edit|Write" and any("hunk-autodiff.sh" in h.get("command", "") for h in g["hooks"]) for g in x["hooks"]["PostToolUse"])
assert {"UserPromptSubmit", "Stop", "Notification", "SessionEnd", "SessionStart", "PostToolUse"} <= set(c["hooks"])
assert {"UserPromptSubmit", "PermissionRequest", "Stop", "SessionStart", "PostToolUse"} <= set(x["hooks"])
session_start = [h.get("command", "") for g in x["hooks"]["SessionStart"] for h in g["hooks"]]
assert sum("zellij-origin.sh" in command for command in session_start) == 1
assert sum("zellij-agent-status.sh" in command for command in session_start) == 1
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
    assert cfg["hooks"]["EmptyEvent"] == []
    assert len(cfg["hooks"]["EmptyGroup"]) == 1
    assert cfg["hooks"]["EmptyGroup"][0]["hooks"] == []
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

DEFAULT_CLAUDE="$TMP/default-claude"
DEFAULT_CODEX="$TMP/default-codex"
CLAUDE_CONFIG_DIR="$DEFAULT_CLAUDE" CODEX_CONFIG_DIR="$DEFAULT_CODEX" bash "$INSTALLER" >/dev/null
test -f "$DEFAULT_CLAUDE/settings.json"
test -f "$DEFAULT_CODEX/hooks.json"

ONLY_CLAUDE="$TMP/only-claude"
UNTOUCHED_CODEX="$TMP/untouched-codex"
CLAUDE_CONFIG_DIR="$ONLY_CLAUDE" CODEX_CONFIG_DIR="$UNTOUCHED_CODEX" bash "$INSTALLER" --claude >/dev/null
test -f "$ONLY_CLAUDE/settings.json"
test ! -e "$UNTOUCHED_CODEX"

UNTOUCHED_CLAUDE="$TMP/untouched-claude"
ONLY_CODEX="$TMP/only-codex"
CLAUDE_CONFIG_DIR="$UNTOUCHED_CLAUDE" CODEX_CONFIG_DIR="$ONLY_CODEX" bash "$INSTALLER" --codex >/dev/null
test ! -e "$UNTOUCHED_CLAUDE"
test -f "$ONLY_CODEX/hooks.json"
echo "host selection: PASS"
