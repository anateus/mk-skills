#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../../../" && pwd)"
CTL="$ROOT_DIR/skills/zellij-agent-herder/scripts/hunk-stream.py"
ORIGIN="$ROOT_DIR/skills/zellij-agent-herder/scripts/zellij-origin.sh"
AUTODIFF="$ROOT_DIR/skills/zellij-agent-herder/scripts/hunk-autodiff.sh"
STATUS="$ROOT_DIR/skills/zellij-agent-herder/scripts/zellij-agent-status.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export HOME="$T/home" XDG_CACHE_HOME="$T/cache"; mkdir -p "$HOME"
git -C "$T" init -q repo
git -C "$T/repo" config user.email test@example.com
git -C "$T/repo" config user.name Test
printf 'one\n' > "$T/repo/a.txt"
git -C "$T/repo" add a.txt && git -C "$T/repo" commit -qm base
BASE="$(git -C "$T/repo" rev-parse HEAD)"
S1="$(python3 "$CTL" signature --root "$T/repo" --base "$BASE")"
printf 'two\n' >> "$T/repo/a.txt"
S2="$(python3 "$CTL" signature --root "$T/repo" --base "$BASE")"
[ "$S1" != "$S2" ]
printf 'new\n' > "$T/repo/new.txt"
S3="$(python3 "$CTL" signature --root "$T/repo" --base "$BASE")"
[ "$S2" != "$S3" ]
K1="$(python3 "$CTL" state-key --session s --parent terminal_1 --root "$T/repo" --kind worktree)"
K2="$(python3 "$CTL" state-key --session s --parent terminal_1 --root "$T/repo" --kind worktree)"
[ "$K1" = "$K2" ]
echo 'identity/signature: PASS'

mkdir -p "$T/bin"
export ZELLIJ_LOG="$T/zellij.log" ZELLIJ_DATA="$T/zellij-data"
mkdir -p "$ZELLIJ_DATA"
printf '%s\n' '[{"id":"terminal_1","title":"parent","is_focused":false},{"id":"terminal_9","title":"old","is_focused":true}]' > "$ZELLIJ_DATA/panes.json"
printf '%s\n' '[{"client_id":1,"focused_pane":"terminal_9"}]' > "$ZELLIJ_DATA/clients.json"
printf '9\n' > "$ZELLIJ_DATA/next"
touch "$ZELLIJ_LOG"
cat > "$T/bin/zellij" <<'PY'
#!/usr/bin/env python3
import json, os, sys

data = os.environ["ZELLIJ_DATA"]
args = sys.argv[1:]
with open(os.environ["ZELLIJ_LOG"], "a") as log:
    log.write(" ".join(args) + "\n")
if len(args) >= 3 and args[0] == "--session" and args[2] == "action":
    args = args[3:]
def load(name):
    with open(os.path.join(data, name + ".json")) as source:
        return json.load(source)
def save(name, value):
    with open(os.path.join(data, name + ".json"), "w") as target:
        json.dump(value, target)
command, rest = args[0], args[1:]
if command == "list-panes":
    print(json.dumps(load("panes")))
elif command == "list-clients":
    print("CLIENT_ID ZELLIJ_PANE_ID")
    for client in load("clients"):
        print(client["client_id"], client["focused_pane"])
elif command == "focus-pane-id":
    pane_id = rest[0]
    panes = load("panes")
    for pane in panes:
        pane["is_focused"] = pane["id"] == pane_id
    clients = load("clients")
    for client in clients:
        client["focused_pane"] = pane_id
    save("panes", panes); save("clients", clients)
elif command == "new-pane":
    with open(os.path.join(data, "next"), "r+") as counter:
        number = int(counter.read()) + 1
        counter.seek(0); counter.write(str(number)); counter.truncate()
    title = rest[rest.index("--name") + 1]
    pane_id = "terminal_" + str(number)
    panes = load("panes")
    panes.append({"id": pane_id, "title": title, "is_focused": False})
    save("panes", panes)
    print("terminal_999" if os.environ.get("ZELLIJ_FAKE_BAD_ID") else pane_id)
elif command == "close-pane":
    pane_id = rest[rest.index("-p") + 1]
    save("panes", [pane for pane in load("panes") if pane["id"] != pane_id])
elif command == "rename-pane":
    pane_id = rest[rest.index("-p") + 1]
    title = rest[-1]
    panes = load("panes")
    for pane in panes:
        if pane["id"] == pane_id:
            pane["title"] = title
    save("panes", panes)
else:
    raise SystemExit("unsupported fake zellij command: " + repr(args))
PY
chmod +x "$T/bin/zellij"
ORIGINAL_PATH="$PATH"
export PATH="$T/bin:$PATH"

P1="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
P2="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
[ "$P1" = "$P2" ]
[ "$(grep -c 'new-pane' "$ZELLIJ_LOG")" = 1 ]
grep -q 'focus-pane-id terminal_1' "$ZELLIJ_LOG"
grep -q 'new-pane --direction right' "$ZELLIJ_LOG"
grep -q 'focus-pane-id terminal_9' "$ZELLIJ_LOG"

zellij --session s action close-pane -p "$P1"
P3="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
[ -z "$P3" ]
[ "$(grep -c 'new-pane' "$ZELLIJ_LOG")" = 1 ]
printf 'changed\n' >> "$T/repo/a.txt"
P4="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
[ -n "$P4" ]
[ "$(grep -c 'new-pane' "$ZELLIJ_LOG")" = 2 ]
zellij --session s action close-pane -p "$P4"
P5="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
[ -z "$P5" ]
P6="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo --explicit)"
[ -n "$P6" ]

# With no attached client, spawning falls back to plain tiled new-pane.
printf '[]\n' > "$ZELLIJ_DATA/clients.json"
before="$(wc -l < "$ZELLIJ_LOG")"
P7="$(python3 "$CTL" ensure --session s --parent terminal_2 --root "$T/repo" --base "$BASE" --kind worktree --label fallback --explicit)"
tail -n "+$((before + 1))" "$ZELLIJ_LOG" | grep -q 'new-pane --cwd'
! tail -n "+$((before + 1))" "$ZELLIJ_LOG" | grep -q -- '--direction'

# A bad returned ID is recovered via the unique generated pane title.
export ZELLIJ_FAKE_BAD_ID=1
P8="$(python3 "$CTL" ensure --session s --parent terminal_3 --root "$T/repo" --base "$BASE" --kind worktree --label recovered --explicit)"
unset ZELLIJ_FAKE_BAD_ID
[ "$P8" != terminal_999 ]

# Roll-up closes only the supplied child panes and keeps the original fixed base.
printf '%s\n' '[{"client_id":1,"focused_pane":"terminal_9"}]' > "$ZELLIJ_DATA/clients.json"
rollup_new_before="$(grep -c 'new-pane' "$ZELLIJ_LOG")"
AGG="$(python3 "$CTL" rollup --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --label session --child-pane "$P7" --child-pane "$P8")"
[ -n "$AGG" ]
[ "$(( $(grep -c 'new-pane' "$ZELLIJ_LOG") - rollup_new_before ))" = 1 ]
grep -q "close-pane -p $P7" "$ZELLIJ_LOG"
grep -q "close-pane -p $P8" "$ZELLIJ_LOG"
last_new="$(grep 'new-pane' "$ZELLIJ_LOG" | tail -1)"
case "$last_new" in *"hunk diff $BASE --watch"*) ;; *) exit 1 ;; esac
python3 - "$XDG_CACHE_HOME" "$P7" "$P8" <<'PY'
import glob, json, os, sys
states = [json.load(open(path)) for path in glob.glob(os.path.join(sys.argv[1], "zellij-agent-herder", "streams", "*.json"))]
for pane_id in sys.argv[2:]:
    state = next(state for state in states if state.get("pane_id") == pane_id)
    assert state.get("complete") is True
PY
python3 - "$ZELLIJ_DATA/panes.json" "$P6" <<'PY'
import json, sys
assert sys.argv[2] in {pane["id"] for pane in json.load(open(sys.argv[1]))}
PY
echo 'reconciliation/placement/rollup: PASS'

# Hook adapters retain the top-level pane even when later events run elsewhere.
export ZELLIJ_SESSION_NAME=claude-s ZELLIJ_PANE_ID=1
printf '%s\n' '{"hook_event_name":"SessionStart","session_id":"claude-session","cwd":"'$T'/repo"}' | bash "$ORIGIN"
python3 - "$XDG_CACHE_HOME/zellij-agent-herder/origins/claude-claude-session.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1])) == {
    "host": "claude", "session_id": "claude-session",
    "zellij_session": "claude-s", "parent_pane": "terminal_1",
}
PY
export ZELLIJ_PANE_ID=7
printf '%s\n' '{"hook_event_name":"SessionStart","session_id":"claude-session","cwd":"'$T'/repo"}' | bash "$ORIGIN"
python3 - "$XDG_CACHE_HOME/zellij-agent-herder/origins/claude-claude-session.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1]))["parent_pane"] == "terminal_1"
PY
printf '%s\n' '{"hook_event_name":"SessionStart","session_id":"claude-session","agent_id":"child","cwd":"'$T'/repo"}' | bash "$ORIGIN"
before="$(grep -c 'new-pane' "$ZELLIJ_LOG")"
printf '%s\n' '{"hook_event_name":"PostToolUse","session_id":"claude-session","cwd":"'$T'/repo","tool_name":"Edit","tool_input":{"file_path":"'$T'/repo/a.txt"}}' | bash "$AUTODIFF"
[ "$(( $(grep -c 'new-pane' "$ZELLIJ_LOG") - before ))" = 1 ]
grep -q 'focus-pane-id terminal_1' "$ZELLIJ_LOG"
for tool in MultiEdit NotebookEdit; do
  sid="claude-$tool"
  ZAH_HOST=claude ZELLIJ_SESSION_NAME="s-$sid" ZELLIJ_PANE_ID=1 bash "$ORIGIN" <<EOF
{"hook_event_name":"SessionStart","session_id":"$sid","cwd":"$T/repo"}
EOF
  before="$(grep -c 'new-pane' "$ZELLIJ_LOG")"
  ZELLIJ_PANE_ID=7 bash "$AUTODIFF" <<EOF
{"hook_event_name":"PostToolUse","session_id":"$sid","cwd":"$T/repo","tool_name":"$tool","tool_input":{"file_path":"$T/repo/a.txt"}}
EOF
  [ "$(( $(grep -c 'new-pane' "$ZELLIJ_LOG") - before ))" = 1 ]
done

export ZELLIJ_PANE_ID=1
export ZELLIJ_SESSION_NAME=codex-s
printf '%s\n' '{"hook_event_name":"SessionStart","session_id":"codex-session","model":"gpt-5","turn_id":"turn-1","cwd":"'$T'/repo"}' | bash "$ORIGIN"
export ZELLIJ_PANE_ID=7
printf '%s\n' '{"hook_event_name":"SessionStart","session_id":"codex-session","model":"gpt-5","turn_id":"turn-child","context":{"agent_id":"child"},"cwd":"'$T'/repo"}' | bash "$ORIGIN"
python3 - "$XDG_CACHE_HOME/zellij-agent-herder/origins/codex-codex-session.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1]))["parent_pane"] == "terminal_1"
PY
for tool in apply_patch Edit Write; do
  sid="codex-$tool"
  ZAH_HOST=codex ZELLIJ_SESSION_NAME="s-$sid" ZELLIJ_PANE_ID=1 bash "$ORIGIN" <<EOF
{"hook_event_name":"SessionStart","session_id":"$sid","cwd":"$T/repo"}
EOF
  before="$(grep -c 'new-pane' "$ZELLIJ_LOG")"
  ZELLIJ_PANE_ID=7 bash "$AUTODIFF" <<EOF
{"hook_event_name":"PostToolUse","session_id":"$sid","model":"gpt-5","turn_id":"turn-$tool","cwd":"$T/repo","tool_name":"$tool","tool_input":{"file_path":"$T/repo/a.txt"}}
EOF
  [ "$(( $(grep -c 'new-pane' "$ZELLIJ_LOG") - before ))" = 1 ]
done
before="$(grep -c 'new-pane' "$ZELLIJ_LOG")"
printf '%s\n' '{"hook_event_name":"PostToolUse","session_id":"codex-session","model":"gpt-5","turn_id":"turn-read","cwd":"'$T'/repo","tool_name":"Read","tool_input":{"file_path":"'$T'/repo/a.txt"}}' | bash "$AUTODIFF"
[ "$(grep -c 'new-pane' "$ZELLIJ_LOG")" = "$before" ]

# Claude mappings stay intact; Codex adds PermissionRequest and clears stale status on SessionStart.
export ZELLIJ_SESSION_NAME=status-s
ZELLIJ_PANE_ID=1 bash "$STATUS" <<'EOF'
{"hook_event_name":"UserPromptSubmit","session_id":"codex-session","model":"gpt-5","turn_id":"turn-status"}
EOF
python3 - "$ZELLIJ_DATA/panes.json" <<'PY'
import json, sys
pane = next(p for p in json.load(open(sys.argv[1])) if p["id"] == "terminal_1")
assert pane["title"] == "parent · working", pane
PY
ZELLIJ_PANE_ID=1 bash "$STATUS" <<'EOF'
{"hook_event_name":"PermissionRequest","session_id":"codex-session","model":"gpt-5","turn_id":"turn-status"}
EOF
python3 - "$ZELLIJ_DATA/panes.json" <<'PY'
import json, sys
pane = next(p for p in json.load(open(sys.argv[1])) if p["id"] == "terminal_1")
assert pane["title"] == "parent · blocked", pane
PY
ZELLIJ_PANE_ID=1 bash "$STATUS" <<'EOF'
{"hook_event_name":"UserPromptSubmit","session_id":"codex-session","model":"gpt-5","turn_id":"turn-child","context":{"agent_id":"child"}}
EOF
ZELLIJ_PANE_ID=1 bash "$STATUS" <<'EOF'
{"hook_event_name":"Stop","session_id":"codex-session","model":"gpt-5","turn_id":"turn-status"}
EOF
python3 - "$ZELLIJ_DATA/panes.json" <<'PY'
import json, sys
pane = next(p for p in json.load(open(sys.argv[1])) if p["id"] == "terminal_1")
assert pane["title"] == "parent · idle", pane
PY
ZELLIJ_PANE_ID=1 bash "$STATUS" <<'EOF'
{"hook_event_name":"SessionStart","session_id":"codex-next","model":"gpt-5","turn_id":"turn-next"}
EOF
python3 - "$ZELLIJ_DATA/panes.json" <<'PY'
import json, sys
pane = next(p for p in json.load(open(sys.argv[1])) if p["id"] == "terminal_1")
assert pane["title"] == "parent", pane
PY
echo 'origin/hooks/status normalization: PASS'

if [ "${LIVE_ZELLIJ:-0}" = 1 ]; then
  REAL_ZELLIJ="$(PATH="$ORIGINAL_PATH"; command -v zellij)"
  session="zhs-$PPID-$RANDOM"
  cleanup_live() { "$REAL_ZELLIJ" delete-session --force "$session" >/dev/null 2>&1 || true; }
  trap 'cleanup_live; rm -rf "$T"' EXIT
  command -v hunk >/dev/null
  script -q /dev/null "$REAL_ZELLIJ" --session "$session" options --default-shell zsh >/dev/null 2>&1 &
  for _ in $(seq 1 50); do "$REAL_ZELLIJ" --session "$session" action list-panes -j >/dev/null 2>&1 && break; sleep 0.1; done
  parent="$("$REAL_ZELLIJ" --session "$session" action new-pane -- sleep 60)"
  old="$("$REAL_ZELLIJ" --session "$session" action new-pane -- sleep 60)"
  watcher="$(PATH="$ORIGINAL_PATH" python3 "$CTL" ensure --session "$session" --parent "$parent" --root "$T/repo" --base "$BASE" --kind worktree --label live --explicit)"
  "$REAL_ZELLIJ" --session "$session" action list-panes -j -g -s > "$T/live-panes.json"
  python3 - "$T/live-panes.json" "$parent" "$watcher" "$old" <<'PY'
import json, sys
panes = {("plugin_" if p.get("is_plugin") else "terminal_") + str(p["id"]): p for p in json.load(open(sys.argv[1]))}
parent, watcher, old = (panes[pane_id] for pane_id in sys.argv[2:])
assert watcher["pane_x"] == parent["pane_x"] + parent["pane_columns"], (parent, watcher)
assert old["is_focused"], old
PY
  cleanup_live
  echo 'live placement/focus: PASS'
fi
