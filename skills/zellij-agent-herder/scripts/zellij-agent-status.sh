#!/bin/sh
# Installed into ~/.claude/hooks/ by install-hooks.sh.
# Stamps agent status into the current zellij pane's title: "<base> · <status>".
set -eu
input="$(cat 2>/dev/null || true)"
[ -n "${ZELLIJ_PANE_ID:-}" ] || exit 0
command -v zellij  >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
ZAH_INPUT="$input" python3 - <<'PY'
import json, os, subprocess, sys
try: h = json.loads(os.environ.get("ZAH_INPUT","") or "{}")
except Exception: h = {}
context = h.get("context")
if h.get("agent_id") or h.get("subagent_id") or h.get("subagent"): sys.exit(0)
if isinstance(context, dict) and any(context.get(k) for k in ("agent_id", "subagent_id", "subagent")): sys.exit(0)
evt = str(h.get("hook_event_name") or "")
host = os.environ.get("ZAH_HOST") or ("codex" if "model" in h or "turn_id" in h else "claude")
if evt == "SubagentStop": sys.exit(0)             # never revive idle
if evt == "Notification" and host == "claude":
    # Notification fires for several subtypes (permission_prompt, idle_prompt,
    # agent_completed, ...); only a real permission prompt means "blocked".
    if str(h.get("notification_type") or "") != "permission_prompt": sys.exit(0)
    status = "blocked"
elif evt == "PermissionRequest" and host == "codex":
    status = "blocked"
elif evt == "SessionEnd" and host == "claude":
    status = None                                  # clear the suffix, don't stamp one
elif evt == "SessionStart" and host == "codex":
    status = None                                  # Codex has no SessionEnd cleanup
elif evt not in ("UserPromptSubmit", "Stop"):
    sys.exit(0)
else:
    status = {"UserPromptSubmit":"working","Stop":"idle"}[evt]
pane = os.environ.get("ZELLIJ_PANE_ID"); sess = os.environ.get("ZELLIJ_SESSION_NAME")
if not pane: sys.exit(0)
pane_arg = pane if pane.startswith(("terminal_","plugin_")) else "terminal_%s" % pane
base_cmd = ["zellij"] + (["--session", sess] if sess else []) + ["action"]
title = ""
try:
    out = subprocess.run(base_cmd+["list-panes","-j"], capture_output=True, text=True, timeout=2).stdout
    data = json.loads(out); panes = []
    if isinstance(data, dict):
        for v in data.values(): panes.extend(v if isinstance(v,list) else [v])
    elif isinstance(data, list): panes = data
    for p in panes:
        pid = p.get("id"); pid = pid if isinstance(pid,str) else "terminal_%d" % pid
        if pid == pane_arg: title = str(p.get("title","")); break
except Exception: title = ""
base = title.split(" · ")[0] if title else "agent"
new_title = base if status is None else "%s · %s" % (base, status)
try: subprocess.run(base_cmd+["rename-pane","-p",pane_arg,new_title], timeout=2)
except Exception: pass
PY
