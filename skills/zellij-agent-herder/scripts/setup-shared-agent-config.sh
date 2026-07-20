#!/usr/bin/env bash
# Establish host-neutral guidance and share Hindsight's official Codex hooks.
set -euo pipefail

AGENTS_DIR="$HOME/.agents"
CLAUDE_DIR="$HOME/.claude"
CODEX_DIR="$HOME/.codex"
HINDSIGHT_DIR="$HOME/.hindsight"
INSTALL_HINDSIGHT=false
HINDSIGHT_SOURCE=""

usage() {
  echo "usage: $0 [--agents-dir DIR] [--claude-dir DIR] [--codex-dir DIR] [--hindsight-dir DIR] [--hindsight-source DIR] [--install-hindsight]" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --agents-dir|--claude-dir|--codex-dir|--hindsight-dir|--hindsight-source)
      [ "$#" -ge 2 ] || usage
      case "$1" in
        --agents-dir) AGENTS_DIR="$2" ;;
        --claude-dir) CLAUDE_DIR="$2" ;;
        --codex-dir) CODEX_DIR="$2" ;;
        --hindsight-dir) HINDSIGHT_DIR="$2" ;;
        --hindsight-source) HINDSIGHT_SOURCE="$2" ;;
      esac
      shift 2
      ;;
    --install-hindsight) INSTALL_HINDSIGHT=true; shift ;;
    *) usage ;;
  esac
done

if [ -n "$HINDSIGHT_SOURCE" ]; then
  [ ! -L "$HINDSIGHT_SOURCE" ] || { echo "Hindsight source root must not be a symlink" >&2; exit 1; }
  python3 - "$HINDSIGHT_SOURCE" <<'PY'
import json, os, pathlib, sys

root = pathlib.Path(sys.argv[1])
required = (root / "hooks" / "hooks.json", root / "settings.json")
scripts = root / "scripts"
if not root.is_dir() or not scripts.is_dir() or scripts.is_symlink():
    raise SystemExit("Hindsight source requires a regular scripts directory")
for path in required:
    if not path.is_file() or path.is_symlink():
        raise SystemExit(f"Hindsight source is missing regular file: {path}")
for directory, names, files in os.walk(scripts, followlinks=False):
    base = pathlib.Path(directory)
    for name in names + files:
        path = base / name
        if path.is_symlink():
            raise SystemExit(f"Hindsight source contains escaping symlink: {path}")
        if name in files and not path.is_file():
            raise SystemExit(f"Hindsight source contains non-regular file: {path}")
with required[0].open(encoding="utf-8") as stream:
    hooks_doc = json.load(stream)
with required[1].open(encoding="utf-8") as stream:
    settings = json.load(stream)
if not isinstance(hooks_doc, dict) or not isinstance(settings, dict):
    raise SystemExit("Hindsight hooks and settings must be JSON objects")
hooks = hooks_doc.get("hooks", hooks_doc)
if not isinstance(hooks, dict):
    raise SystemExit("Hindsight hooks must be a JSON object")
for event in ("SessionStart", "UserPromptSubmit", "Stop"):
    groups = hooks.get(event)
    if not isinstance(groups, list):
        raise SystemExit(f"Hindsight source requires {event} hook groups")
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            raise SystemExit(f"Malformed Hindsight {event} hook group")
        for hook in group["hooks"]:
            if not isinstance(hook, dict) or not isinstance(hook.get("command"), str):
                raise SystemExit(f"Malformed Hindsight {event} hook command")
PY
fi

backup_if_changed() {
  local current="$1" replacement="$2"
  if [ -e "$current" ] || [ -L "$current" ]; then
    if [ ! -L "$current" ] && cmp -s "$current" "$replacement"; then
      return
    fi
    cp -P "$current" "$current.bak.$(date +%Y%m%d%H%M%S).$$"
  fi
}

mkdir -p "$AGENTS_DIR" "$CLAUDE_DIR" "$CODEX_DIR" "$HINDSIGHT_DIR"
CANONICAL="$AGENTS_DIR/AGENTS.md"
GUIDANCE_TMP="$(mktemp "${TMPDIR:-/tmp}/shared-agent-guidance.XXXXXX")"
CLAUDE_TMP="$(mktemp "${TMPDIR:-/tmp}/shared-claude-overlay.XXXXXX")"
INSTALL_TMP=""
trap 'rm -f "$GUIDANCE_TMP" "$CLAUDE_TMP"; [ -z "$INSTALL_TMP" ] || rm -rf "$INSTALL_TMP"' EXIT

cat > "$GUIDANCE_TMP" <<'EOF'
# Shared agent guidance

<important if="you are about to state, document, or rely on what a project uses or how it works">
Verify from the inside, not the surface. Treat manifests, dependencies, design documents, and READMEs as claims to check against actual imports, entrypoints, symbols, paths, and runtime wiring. Distinguish current behavior from legacy and target architecture, and attribute claims that cannot be verified directly.
</important>

<important if="you are about to save a memory, recall past context, or decide which memory system to use">
Use Hindsight with the shared `claude_code` bank as the primary cross-session memory system when its host integration is available. Treat local file-based memory as a fallback, and do not split writes across both systems by default. Hindsight may be exposed through lifecycle hooks rather than interactive tools, so rely only on capabilities available in the current host.
</important>

<important if="you are inside a Zellij session and have just finished a coding task with changes to review">
Use the zellij-agent-herder work-stream-aware Hunk review flow to open or update the stream's review pane proactively. Keep review associated with the originating work stream and do not wait for the user to request it.
</important>
EOF

backup_if_changed "$CANONICAL" "$GUIDANCE_TMP"
if [ -L "$CANONICAL" ]; then
  rm "$CANONICAL"
fi
cp "$GUIDANCE_TMP" "$CANONICAL"

CLAUDE_FILE="$CLAUDE_DIR/CLAUDE.md"
python3 - "$CLAUDE_FILE" "$CANONICAL" "$CLAUDE_TMP" <<'PY'
import pathlib, re, sys

source, canonical, output = map(pathlib.Path, sys.argv[1:])
text = source.read_text(encoding="utf-8") if source.exists() else ""
blocks = re.findall(r'<important if="[^"]*(?:Fable|Opus)[^"]*">.*?</important>', text, re.I | re.S)
if not blocks:
    blocks = ['''<important if="the model is Fable or Opus">
For coding tasks, use your judgement to delegate suitable work to an appropriate lower-power model.
</important>''']
result = f"@{canonical}\n\n# Claude-only guidance\n\n{blocks[0].strip()}\n"
output.write_text(result, encoding="utf-8")
PY
backup_if_changed "$CLAUDE_FILE" "$CLAUDE_TMP"
cp "$CLAUDE_TMP" "$CLAUDE_FILE"

CODEX_GUIDANCE="$CODEX_DIR/AGENTS.md"
if [ ! -L "$CODEX_GUIDANCE" ] || [ "$(readlink "$CODEX_GUIDANCE" 2>/dev/null || true)" != "$CANONICAL" ]; then
  if [ -e "$CODEX_GUIDANCE" ] || [ -L "$CODEX_GUIDANCE" ]; then
    cp -P "$CODEX_GUIDANCE" "$CODEX_GUIDANCE.bak.$(date +%Y%m%d%H%M%S).$$"
    rm -f "$CODEX_GUIDANCE"
  fi
  [ -f "$CANONICAL" ] || { echo "canonical guidance was not created" >&2; exit 1; }
  ln -s "$CANONICAL" "$CODEX_GUIDANCE"
fi

HINDSIGHT_CODEX_DIR="$HINDSIGHT_DIR/codex"
if [ -n "$HINDSIGHT_SOURCE" ]; then
  INSTALL_TMP="$(mktemp -d "$HINDSIGHT_DIR/.codex.install.XXXXXX")"
  mkdir -p "$INSTALL_TMP/scripts"
  cp -p "$HINDSIGHT_SOURCE/settings.json" "$INSTALL_TMP/settings.json"
  cp -pR "$HINDSIGHT_SOURCE/scripts/." "$INSTALL_TMP/scripts/"
  python3 - "$HINDSIGHT_SOURCE/hooks/hooks.json" "$INSTALL_TMP/hooks.json" "$HINDSIGHT_CODEX_DIR/scripts" <<'PY'
import json, os, stat, sys

source, target, scripts_dir = sys.argv[1:]
with open(source, encoding="utf-8") as stream:
    document = json.load(stream)
def substitute(value):
    if isinstance(value, str):
        return value.replace("__SCRIPTS_DIR__", scripts_dir)
    if isinstance(value, list):
        return [substitute(item) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item) for key, item in value.items()}
    return value
document = substitute(document)
with open(target, "w", encoding="utf-8") as stream:
    json.dump(document, stream, indent=2)
    stream.write("\n")
os.chmod(target, stat.S_IMODE(os.stat(source).st_mode))
PY
  if grep -R -Fq '__SCRIPTS_DIR__' "$INSTALL_TMP"; then
    echo "Hindsight source contains an unresolved scripts placeholder" >&2
    exit 1
  fi
  if [ ! -d "$HINDSIGHT_CODEX_DIR" ] || ! diff -qr "$INSTALL_TMP" "$HINDSIGHT_CODEX_DIR" >/dev/null 2>&1; then
    if [ -e "$HINDSIGHT_CODEX_DIR" ] || [ -L "$HINDSIGHT_CODEX_DIR" ]; then
      mv "$HINDSIGHT_CODEX_DIR" "$HINDSIGHT_CODEX_DIR.bak.$(date +%Y%m%d%H%M%S).$$"
    fi
    mv "$INSTALL_TMP" "$HINDSIGHT_CODEX_DIR"
    INSTALL_TMP=""
  fi
fi

HINDSIGHT_HOOKS="$HINDSIGHT_CODEX_DIR/hooks.json"
if [ ! -f "$HINDSIGHT_HOOKS" ] && [ "$INSTALL_HINDSIGHT" = true ]; then
  if command -v hindsight >/dev/null 2>&1; then
    hindsight codex install --directory "$HINDSIGHT_DIR/codex"
  else
    echo "official Hindsight installer is unavailable; install Hindsight, then rerun with --install-hindsight" >&2
    exit 1
  fi
fi
if [ ! -f "$HINDSIGHT_HOOKS" ]; then
  echo "official Hindsight Codex hooks not found under $HINDSIGHT_DIR/codex; ordinary setup will not download them" >&2
  exit 1
fi

CODEX_HOOKS="$CODEX_DIR/hooks.json"
[ -f "$CODEX_HOOKS" ] || printf '{}\n' > "$CODEX_HOOKS"
HOOKS_TMP="$(mktemp "${TMPDIR:-/tmp}/shared-codex-hooks.XXXXXX")"
cp "$CODEX_HOOKS" "$HOOKS_TMP"
python3 - "$HOOKS_TMP" "$HINDSIGHT_HOOKS" <<'PY'
import json, sys

target_path, source_path = sys.argv[1:]
with open(target_path, encoding="utf-8") as stream:
    target = json.load(stream)
with open(source_path, encoding="utf-8") as stream:
    source = json.load(stream)
if not isinstance(target, dict) or not isinstance(source, dict):
    raise SystemExit("Hindsight hook configuration must be a JSON object")
target_hooks = target.setdefault("hooks", {})
source_hooks = source.get("hooks", source)
for event in ("SessionStart", "UserPromptSubmit", "Stop"):
    groups = source_hooks.get(event, [])
    if not isinstance(groups, list):
        raise SystemExit(f"Hindsight {event} hooks must be a list")
    current = target_hooks.setdefault(event, [])
    for group in groups:
        if group not in current:
            current.append(group)
with open(target_path, "w", encoding="utf-8") as stream:
    json.dump(target, stream, indent=2)
    stream.write("\n")
PY
backup_if_changed "$CODEX_HOOKS" "$HOOKS_TMP"
cp "$HOOKS_TMP" "$CODEX_HOOKS"
rm -f "$HOOKS_TMP"

HINDSIGHT_CONFIG="$HINDSIGHT_DIR/codex.json"
[ -f "$HINDSIGHT_CONFIG" ] || printf '{}\n' > "$HINDSIGHT_CONFIG"
CONFIG_TMP="$(mktemp "${TMPDIR:-/tmp}/shared-hindsight-config.XXXXXX")"
cp "$HINDSIGHT_CONFIG" "$CONFIG_TMP"
python3 - "$CONFIG_TMP" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8") as stream:
    config = json.load(stream)
if not isinstance(config, dict):
    raise SystemExit("Hindsight Codex configuration must be a JSON object")
config["bankId"] = "claude_code"
config["dynamicBankId"] = False
with open(path, "w", encoding="utf-8") as stream:
    json.dump(config, stream, indent=2)
    stream.write("\n")
PY
backup_if_changed "$HINDSIGHT_CONFIG" "$CONFIG_TMP"
cp "$CONFIG_TMP" "$HINDSIGHT_CONFIG"
rm -f "$CONFIG_TMP"

echo "Shared guidance and Hindsight Codex hooks configured (credentials preserved and redacted)."
