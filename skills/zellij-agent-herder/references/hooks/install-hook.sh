#!/usr/bin/env bash
# Installs the zellij-agent-herder SessionStart *activation* hook — a discovery
# aid that tells Claude it is inside zellij at session start, so this skill
# triggers reliably. This is separate from scripts/install-hooks.sh (which
# installs the operational status + hunk-autodiff hooks). Idempotent.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="$HOME/.claude/hooks"; SETTINGS="$HOME/.claude/settings.json"
HOOK="zellij-activation.sh"
mkdir -p "$DEST_DIR"
cp "$SRC/$HOOK" "$DEST_DIR/$HOOK"; chmod +x "$DEST_DIR/$HOOK"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
HOOK_CMD="bash '$DEST_DIR/$HOOK'" python3 - "$SETTINGS" <<'PY'
import json, os, sys
path = sys.argv[1]; cmd = os.environ["HOOK_CMD"]
try: cfg = json.load(open(path))
except Exception: cfg = {}
hooks = cfg.setdefault("hooks", {})
# Append to SessionStart without clobbering existing hooks (e.g. herdr's).
groups = hooks.setdefault("SessionStart", [])
present = any(cmd in hk.get("command","") for g in groups for hk in g.get("hooks", []))
if not present:
    groups.append({"hooks":[{"type":"command","command":cmd,"timeout":10}]})
    print("installed zellij-agent-herder SessionStart hook into", path)
else:
    print("zellij-agent-herder SessionStart hook already present in", path)
json.dump(cfg, open(path,"w"), indent=2); open(path,"a").write("\n")
PY
echo "Start a new Claude Code session inside zellij to pick it up."
