#!/usr/bin/env bash
# Install or remove zellij-agent-herder hooks for Claude Code and Codex.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
ACTION=install
HOST=all

usage() {
  echo "usage: $0 [--uninstall] [--claude|--codex|--all]" >&2
  exit 2
}

for arg in "$@"; do
  case "$arg" in
    --uninstall) ACTION=uninstall ;;
    --claude) HOST=claude ;;
    --codex) HOST=codex ;;
    --all) HOST=all ;;
    *) usage ;;
  esac
done

configure_host() {
  local host="$1" root config async matcher events origin_status
  if [ "$host" = claude ]; then
    root="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
    config="$root/settings.json"
    async=true
    matcher='Edit|Write|MultiEdit|NotebookEdit'
    events='UserPromptSubmit,Stop,Notification,SessionEnd'
    origin_status=false
  else
    root="${CODEX_CONFIG_DIR:-$HOME/.codex}"
    config="$root/hooks.json"
    async=false
    matcher='apply_patch|Edit|Write'
    events='UserPromptSubmit,PermissionRequest,Stop'
    origin_status=true
  fi

  local hooks_dir="$root/hooks"
  if [ "$ACTION" = install ]; then
    mkdir -p "$hooks_dir"
    for script in zellij-agent-status.sh hunk-autodiff.sh zellij-origin.sh pane-identity.py; do
      cp "$SRC/$script" "$hooks_dir/$script"
      chmod +x "$hooks_dir/$script"
    done
  else
    for script in zellij-agent-status.sh hunk-autodiff.sh zellij-origin.sh pane-identity.py; do
      rm -f "$hooks_dir/$script"
    done
    [ -f "$config" ] || return 0
  fi

  [ -f "$config" ] || printf '{}\n' > "$config"
  local backup="$config.bak.$(date +%Y%m%d%H%M%S).$$"
  cp "$config" "$backup"

  ZAH_ACTION="$ACTION" ZAH_HOST_NAME="$host" ZAH_HOOKS_DIR="$hooks_dir" \
    ZAH_ASYNC="$async" ZAH_MATCHER="$matcher" ZAH_STATUS_EVENTS="$events" \
    ZAH_ORIGIN_STATUS="$origin_status" python3 - "$config" <<'PY'
import json, os, shlex, sys

path = sys.argv[1]
with open(path, encoding="utf-8") as source:
    try:
        cfg = json.load(source)
    except Exception:
        cfg = {}
if not isinstance(cfg, dict):
    cfg = {}

action = os.environ["ZAH_ACTION"]
if action == "install":
    hooks = cfg.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = cfg["hooks"] = {}
else:
    hooks = cfg.get("hooks")
    if not isinstance(hooks, dict):
        raise SystemExit(0)

host = os.environ["ZAH_HOST_NAME"]
directory = os.environ["ZAH_HOOKS_DIR"]
names = ("zellij-agent-status.sh", "hunk-autodiff.sh", "zellij-origin.sh")
commands = {name: "ZAH_HOST=%s bash '%s'" % (host, os.path.join(directory, name)) for name in names}
commands["zellij-agent-status.sh"] = "ZAH_HOST=%s ZAH_IDENTITY_SCRIPT='%s' bash '%s'" % (
    host,
    os.path.join(directory, "pane-identity.py"),
    os.path.join(directory, "zellij-agent-status.sh"),
)

def owned(entry):
    command = entry.get("command", "") if isinstance(entry, dict) else ""
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    paths = [word for word in words if os.path.dirname(word) == directory]
    return any(os.path.basename(path) in names for path in paths)

def remove_owned():
    removed = False
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept = []
        event_removed = False
        for group in groups:
            if not isinstance(group, dict):
                kept.append(group)
                continue
            entries = group.get("hooks")
            if not isinstance(entries, list):
                kept.append(group)
                continue
            remaining = [entry for entry in entries if not owned(entry)]
            group_removed = len(remaining) != len(entries)
            if group_removed:
                removed = True
                event_removed = True
            if not group_removed:
                kept.append(group)
            elif remaining:
                updated = dict(group)
                updated["hooks"] = remaining
                kept.append(updated)
        if kept or not event_removed:
            hooks[event] = kept
        else:
            del hooks[event]
    return removed

removed = remove_owned()
if action == "install":
    def add(event, name, matcher=None, asynchronous=False):
        entry = {"type": "command", "command": commands[name], "timeout": 10}
        if asynchronous:
            entry["async"] = True
        group = {"hooks": [entry]}
        if matcher is not None:
            group["matcher"] = matcher
        hooks.setdefault(event, []).append(group)

    for event in os.environ["ZAH_STATUS_EVENTS"].split(","):
        add(event, "zellij-agent-status.sh")
    add("SessionStart", "zellij-origin.sh")
    if os.environ["ZAH_ORIGIN_STATUS"] == "true":
        add("SessionStart", "zellij-agent-status.sh")
    add("PostToolUse", "hunk-autodiff.sh", os.environ["ZAH_MATCHER"], os.environ["ZAH_ASYNC"] == "true")
elif not removed:
    raise SystemExit(0)

with open(path, "w", encoding="utf-8") as target:
    json.dump(cfg, target, indent=2)
    target.write("\n")
PY

  if cmp -s "$backup" "$config"; then
    rm "$backup"
  fi
}

case "$HOST" in
  claude) configure_host claude ;;
  codex) configure_host codex ;;
  all) configure_host claude; configure_host codex ;;
esac

if [ "$ACTION" = install ] && { [ "$HOST" = codex ] || [ "$HOST" = all ]; }; then
  echo "Run /hooks and trust the new or changed zellij-agent-herder definitions."
fi
