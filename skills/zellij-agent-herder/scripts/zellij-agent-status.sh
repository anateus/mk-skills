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
if h.get("agent_id"): sys.exit(0)                 # subagent — ignore
evt = str(h.get("hook_event_name") or "")
if evt == "SubagentStop": sys.exit(0)             # never revive idle
if evt == "Notification":
    # Notification fires for several subtypes (permission_prompt, idle_prompt,
    # agent_completed, ...); only a real permission prompt means "blocked".
    if str(h.get("notification_type") or "") != "permission_prompt": sys.exit(0)
    status = "blocked"
else:
    status = {"UserPromptSubmit":"working","Stop":"idle"}.get(evt)
if not status: sys.exit(0)
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
try: subprocess.run(base_cmd+["rename-pane","-p",pane_arg,"%s · %s" % (base, status)], timeout=2)
except Exception: pass
PY
