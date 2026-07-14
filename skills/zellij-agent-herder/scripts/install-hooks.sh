#!/usr/bin/env bash
# Installs the zellij-agent-herder Claude Code hooks. Idempotent; safe to re-run.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="$HOME/.claude/hooks"; SETTINGS="$HOME/.claude/settings.json"
mkdir -p "$DEST_DIR"
cp "$SRC/zellij-agent-status.sh" "$DEST_DIR/zellij-agent-status.sh"; chmod +x "$DEST_DIR/zellij-agent-status.sh"
cp "$SRC/hunk-autodiff.sh"       "$DEST_DIR/hunk-autodiff.sh";       chmod +x "$DEST_DIR/hunk-autodiff.sh"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak.$(date +%Y%m%d%H%M%S)"
STATUS_HOOK="bash '$DEST_DIR/zellij-agent-status.sh'" HUNK_HOOK="bash '$DEST_DIR/hunk-autodiff.sh'" \
python3 - "$SETTINGS" <<'PY'
import json, os, sys
path = sys.argv[1]; status_cmd = os.environ["STATUS_HOOK"]; hunk_cmd = os.environ["HUNK_HOOK"]
try: cfg = json.load(open(path))
except Exception: cfg = {}
hooks = cfg.setdefault("hooks", {})
def ensure(event, cmd, matcher=None, extra=None):
    groups = hooks.setdefault(event, [])
    if any(cmd in hk.get("command","") for g in groups for hk in g.get("hooks", [])): return
    entry = {"type":"command","command":cmd,"timeout":10}
    if extra: entry.update(extra)
    g = {"hooks":[entry]}
    if matcher is not None: g["matcher"] = matcher
    groups.append(g)
for ev in ("UserPromptSubmit","Stop","Notification","SessionEnd"): ensure(ev, status_cmd)
ensure("PostToolUse", hunk_cmd, matcher="Edit|Write|MultiEdit|NotebookEdit", extra={"async": True})
json.dump(cfg, open(path,"w"), indent=2); open(path,"a").write("\n")
print("installed zellij-agent-herder hooks into", path)
PY
