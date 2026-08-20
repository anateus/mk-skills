#!/usr/bin/env bash
# Install or remove mk-skills subagent artifact hooks for Claude Code and Codex.
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

is_owned_link() {
  local link="$1" target
  [ -L "$link" ] || return 1
  target="$(readlink "$link")"
  case "$target" in
    */subagent-artifact-discipline/scripts/artifact-discipline.js) return 0 ;;
    *) return 1 ;;
  esac
}

remove_owned_link() {
  local link="$1"
  if is_owned_link "$link"; then
    rm -f "$link"
  fi
}

configure_host() {
  local host="$1" root config hooks_dir link
  if [ "$host" = claude ]; then
    root="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
    config="$root/settings.json"
  else
    root="${CODEX_CONFIG_DIR:-$HOME/.codex}"
    config="$root/hooks.json"
  fi

  hooks_dir="$root/hooks"
  link="$hooks_dir/mk-skills-artifact-discipline.js"

  if [ "$ACTION" = uninstall ] && [ ! -f "$config" ]; then
    remove_owned_link "$link"
    return 0
  fi

  if [ "$ACTION" = install ]; then
    if { [ -e "$link" ] || [ -L "$link" ]; } && ! is_owned_link "$link"; then
      echo "refusing to replace unowned hook runtime: $link" >&2
      return 1
    fi
    mkdir -p "$hooks_dir"
    ln -sfn "$SRC/artifact-discipline.js" "$link"
    [ -f "$config" ] || printf '{}\n' > "$config"
  fi

  MK_SA_ACTION="$ACTION" MK_SA_LINK="$link" python3 - "$config" <<'PY'
import json
import os
import shlex
import shutil
import sys
import tempfile
from datetime import datetime

path = sys.argv[1]
with open(path, encoding="utf-8") as source:
    config = json.load(source)
if not isinstance(config, dict):
    raise SystemExit(f"hook configuration must be an object: {path}")

before = json.dumps(config, sort_keys=True, separators=(",", ":"))
action = os.environ["MK_SA_ACTION"]
link = os.environ["MK_SA_LINK"]
command = f"node {shlex.quote(link)}"
events = ("SubagentStart", "SubagentStop")

hooks = config.get("hooks")
if action == "install":
    if hooks is None:
        hooks = config["hooks"] = {}
    if not isinstance(hooks, dict):
        raise SystemExit(f"hook configuration field 'hooks' must be an object: {path}")
elif not isinstance(hooks, dict):
    raise SystemExit(0)

for event in events:
    groups = hooks.get(event, [])
    if not isinstance(groups, list):
        raise SystemExit(f"hook event '{event}' must be an array: {path}")

    kept_groups = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            kept_groups.append(group)
            continue
        kept_hooks = [hook for hook in group["hooks"] if not (
            isinstance(hook, dict) and hook.get("command") == command
        )]
        if kept_hooks:
            copy = dict(group)
            copy["hooks"] = kept_hooks
            kept_groups.append(copy)
        elif len(kept_hooks) == len(group["hooks"]):
            kept_groups.append(group)

    if action == "install":
        kept_groups.append({
            "hooks": [{
                "type": "command",
                "command": command,
                "timeout": 10,
            }],
        })
        hooks[event] = kept_groups
    elif kept_groups:
        hooks[event] = kept_groups
    else:
        hooks.pop(event, None)

if action == "uninstall" and not hooks:
    config.pop("hooks", None)

after = json.dumps(config, sort_keys=True, separators=(",", ":"))
if before == after:
    raise SystemExit(0)

stamp = datetime.now().strftime("%Y%m%d%H%M%S")
backup = f"{path}.bak.{stamp}.{os.getpid()}"
shutil.copy2(path, backup)

directory = os.path.dirname(path)
mode = os.stat(path).st_mode
fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(path)}.", dir=directory)
try:
    os.fchmod(fd, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as target:
        json.dump(config, target, indent=2)
        target.write("\n")
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY

  if [ "$ACTION" = uninstall ]; then
    remove_owned_link "$link"
  fi
}

case "$HOST" in
  claude) configure_host claude ;;
  codex) configure_host codex ;;
  all)
    configure_host claude
    configure_host codex
    ;;
esac

echo "$ACTION complete for $HOST"
