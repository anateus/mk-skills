#!/usr/bin/env bash
# Establish host-neutral guidance and share Hindsight's official Codex hooks.
set -euo pipefail

AGENTS_DIR="$HOME/.agents"
CLAUDE_DIR="$HOME/.claude"
CODEX_DIR="$HOME/.codex"
HINDSIGHT_DIR="$HOME/.hindsight"
INSTALL_HINDSIGHT=false

usage() {
  echo "usage: $0 [--agents-dir DIR] [--claude-dir DIR] [--codex-dir DIR] [--hindsight-dir DIR] [--install-hindsight]" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --agents-dir|--claude-dir|--codex-dir|--hindsight-dir)
      [ "$#" -ge 2 ] || usage
      case "$1" in
        --agents-dir) AGENTS_DIR="$2" ;;
        --claude-dir) CLAUDE_DIR="$2" ;;
        --codex-dir) CODEX_DIR="$2" ;;
        --hindsight-dir) HINDSIGHT_DIR="$2" ;;
      esac
      shift 2
      ;;
    --install-hindsight) INSTALL_HINDSIGHT=true; shift ;;
    *) usage ;;
  esac
done

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
trap 'rm -f "$GUIDANCE_TMP" "$CLAUDE_TMP"' EXIT

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

HINDSIGHT_HOOKS="$HINDSIGHT_DIR/codex/hooks.json"
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
