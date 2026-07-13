#!/usr/bin/env bash
# Removes the zellij-agent-herder SessionStart activation hook installed by
# install-hook.sh. Leaves any other hooks (including herdr's SessionStart)
# untouched. Idempotent.
set -euo pipefail
DEST_DIR="$HOME/.claude/hooks"; SETTINGS="$HOME/.claude/settings.json"
HOOK="zellij-activation.sh"
rm -f "$DEST_DIR/$HOOK"
[ -f "$SETTINGS" ] || { echo "no $SETTINGS; nothing to do"; exit 0; }
cp "$SETTINGS" "$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
python3 - "$SETTINGS" "$HOOK" <<'PY'
import json, sys
path, hook = sys.argv[1], sys.argv[2]
try: cfg = json.load(open(path))
except Exception: cfg = {}
hooks = cfg.get("hooks", {})
kept = []
for g in hooks.get("SessionStart", []):
    g["hooks"] = [hk for hk in g.get("hooks", []) if hook not in hk.get("command","")]
    if g["hooks"]:
        kept.append(g)
if kept:
    hooks["SessionStart"] = kept
else:
    hooks.pop("SessionStart", None)
json.dump(cfg, open(path,"w"), indent=2); open(path,"a").write("\n")
print("removed zellij-agent-herder SessionStart hook from", path)
PY
