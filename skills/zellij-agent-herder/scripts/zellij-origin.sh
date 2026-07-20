#!/bin/sh
# SessionStart hook: persist the top-level agent's originating Zellij pane.
set -eu
input="$(cat 2>/dev/null || true)"
[ -n "${ZELLIJ_PANE_ID:-}" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
ZAH_INPUT="$input" python3 - <<'PY'
import json, os, tempfile

try:
    payload = json.loads(os.environ.get("ZAH_INPUT", ""))
except Exception:
    raise SystemExit(0)
if not isinstance(payload, dict) or payload.get("hook_event_name") != "SessionStart":
    raise SystemExit(0)
context = payload.get("context")
if payload.get("agent_id") or payload.get("subagent_id") or payload.get("subagent"):
    raise SystemExit(0)
if isinstance(context, dict) and any(context.get(key) for key in ("agent_id", "subagent_id", "subagent")):
    raise SystemExit(0)
session_id = payload.get("session_id")
if not isinstance(session_id, str) or not session_id or "/" in session_id or "\0" in session_id:
    raise SystemExit(0)
host = os.environ.get("ZAH_HOST") or ("codex" if "model" in payload or "turn_id" in payload else "claude")
if host not in ("claude", "codex"):
    raise SystemExit(0)
pane = str(os.environ["ZELLIJ_PANE_ID"])
if not pane.startswith(("terminal_", "plugin_")):
    pane = "terminal_" + pane
record = {
    "host": host,
    "session_id": session_id,
    "zellij_session": os.environ.get("ZELLIJ_SESSION_NAME", ""),
    "parent_pane": pane,
}
directory = os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "zellij-agent-herder", "origins",
)
os.makedirs(directory, exist_ok=True)
path = os.path.join(directory, "%s-%s.json" % (host, session_id))
fd, temporary = tempfile.mkstemp(prefix=".origin-", dir=directory)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as target:
        json.dump(record, target, sort_keys=True, separators=(",", ":"))
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
