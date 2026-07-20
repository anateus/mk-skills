#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/../../../" && pwd)"
CTL="$ROOT_DIR/skills/zellij-agent-herder/scripts/hunk-stream.py"
ORIGIN="$ROOT_DIR/skills/zellij-agent-herder/scripts/zellij-origin.sh"
AUTODIFF="$ROOT_DIR/skills/zellij-agent-herder/scripts/hunk-autodiff.sh"
STATUS="$ROOT_DIR/skills/zellij-agent-herder/scripts/zellij-agent-status.sh"
ZJ="$ROOT_DIR/skills/zellij-agent-herder/scripts/zj.sh"
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
printf '%s\n' '[{"id":"terminal_1","title":"parent","is_focused":false,"pane_x":0,"pane_y":0,"pane_columns":40,"pane_rows":24},{"id":"terminal_9","title":"old","is_focused":true,"pane_x":40,"pane_y":0,"pane_columns":40,"pane_rows":24}]' > "$ZELLIJ_DATA/panes.json"
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
    pending_path = os.path.join(data, "pending-focus.json")
    if os.path.exists(pending_path):
        pending = json.load(open(pending_path))
        pending["polls"] -= 1
        if pending["polls"] <= 0:
            clients = load("clients")
            clients[0]["focused_pane"] = pending["pane_id"]
            save("clients", clients)
            os.unlink(pending_path)
        else:
            with open(pending_path, "w") as target:
                json.dump(pending, target)
    print("CLIENT_ID ZELLIJ_PANE_ID")
    for client in load("clients"):
        print(client["client_id"], client["focused_pane"])
elif command == "focus-pane-id":
    # Zellij 0.45 accepts this external action without changing the attached
    # client's focus. Relative creation still follows the client-focused pane.
    pass
elif command == "new-pane":
    with open(os.path.join(data, "next"), "r+") as counter:
        number = int(counter.read()) + 1
        counter.seek(0); counter.write(str(number)); counter.truncate()
    title = rest[rest.index("--name") + 1]
    pane_id = "terminal_" + str(number)
    panes = load("panes")
    clients = load("clients")
    focused_id = clients[0]["focused_pane"] if len(clients) == 1 else None
    focused = next((pane for pane in panes if pane["id"] == focused_id), None)
    if focused is None:
        pane = {"id": pane_id, "title": title, "is_focused": False,
                "pane_x": 80, "pane_y": 0, "pane_columns": 20, "pane_rows": 24}
    else:
        width = max(1, focused["pane_columns"] // 2)
        focused["pane_columns"] -= width
        pane = {"id": pane_id, "title": title, "is_focused": True,
                "pane_x": focused["pane_x"] + focused["pane_columns"],
                "pane_y": focused["pane_y"], "pane_columns": width,
                "pane_rows": focused["pane_rows"]}
        for item in panes:
            item["is_focused"] = False
        clients[0]["focused_pane"] = pane_id
    panes.append(pane)
    save("panes", panes); save("clients", clients)
    print("terminal_999" if os.environ.get("ZELLIJ_FAKE_BAD_ID") else pane_id)
elif command == "move-pane":
    pane_id = rest[rest.index("-p") + 1]
    direction = rest[-1]
    panes = load("panes")
    moving = next(pane for pane in panes if pane["id"] == pane_id)
    if direction in ("left", "right"):
        candidates = [pane for pane in panes if pane is not moving and
                      pane["pane_y"] < moving["pane_y"] + moving["pane_rows"] and
                      moving["pane_y"] < pane["pane_y"] + pane["pane_rows"]]
        if direction == "left":
            neighbor = max((pane for pane in candidates if pane["pane_x"] < moving["pane_x"]),
                           key=lambda pane: pane["pane_x"], default=None)
        else:
            neighbor = min((pane for pane in candidates if pane["pane_x"] > moving["pane_x"]),
                           key=lambda pane: pane["pane_x"], default=None)
        if neighbor is not None:
            moving["pane_x"], neighbor["pane_x"] = neighbor["pane_x"], moving["pane_x"]
    save("panes", panes)
elif command == "move-focus":
    direction = rest[0]
    panes = load("panes")
    clients = load("clients")
    current = next(pane for pane in panes if pane["is_focused"])
    if direction == "left":
        candidate = max((pane for pane in panes if pane["pane_x"] < current["pane_x"]),
                        key=lambda pane: pane["pane_x"], default=None)
    else:
        candidate = min((pane for pane in panes if pane["pane_x"] > current["pane_x"]),
                        key=lambda pane: pane["pane_x"], default=None)
    if candidate is not None:
        for pane in panes:
            pane["is_focused"] = pane is candidate
        with open(os.path.join(data, "pending-focus.json"), "w") as target:
            json.dump({"pane_id": candidate["id"], "polls": 10}, target)
    save("panes", panes)
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
printf '#!/usr/bin/env bash\nexit 0\n' > "$T/bin/hunk"
chmod +x "$T/bin/hunk"
ORIGINAL_PATH="$PATH"
export PATH="$T/bin:$PATH"
export ZAH_FOCUS_GUARD_WINDOW=0

P1="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
P2="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
[ "$P1" = "$P2" ]
[ "$(grep -c 'new-pane' "$ZELLIJ_LOG")" = 1 ]
! grep -q 'focus-pane-id' "$ZELLIJ_LOG"
grep -q 'new-pane --cwd' "$ZELLIJ_LOG"
grep -q "move-pane -p $P1 left" "$ZELLIJ_LOG"
grep -q 'move-focus right' "$ZELLIJ_LOG"
python3 - "$ZELLIJ_DATA/panes.json" "$ZELLIJ_DATA/clients.json" "$P1" <<'PY'
import json, sys
panes = {pane["id"]: pane for pane in json.load(open(sys.argv[1]))}
clients = json.load(open(sys.argv[2]))
parent, watcher = panes["terminal_1"], panes[sys.argv[3]]
assert watcher["pane_x"] == parent["pane_x"] + parent["pane_columns"], (parent, watcher)
assert clients == [{"client_id": 1, "focused_pane": "terminal_9"}], clients
PY

printf 'live-change\n' >> "$T/repo/a.txt"
S_LIVE="$(python3 "$CTL" signature --root "$T/repo" --base "$BASE")"
P_LIVE="$(python3 "$CTL" ensure --session s --parent terminal_1 --root "$T/repo" --base "$BASE" --kind worktree --label repo)"
[ "$P_LIVE" = "$P1" ]
python3 - "$XDG_CACHE_HOME/zellij-agent-herder/streams/$K1.json" "$S_LIVE" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    state = json.load(source)
assert state["signature"] == sys.argv[2], state
PY
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

# Public helpers route through the controller, retain one pane per stream, and preserve
# explicit reopen plus roll-up teardown behavior.
export ZJ_SESSION=helper-s ZELLIJ_PANE_ID=20
source "$ZJ"
helper_new_before="$(grep -c 'new-pane' "$ZELLIJ_LOG")"
H1="$(zj_watch_worktree "$T/repo" "$BASE" helper-worktree)"
H2="$(zj_watch_worktree "$T/repo/." "$BASE" helper-worktree)"
[ "$H1" = "$H2" ]
[ "$(( $(grep -c 'new-pane' "$ZELLIJ_LOG") - helper_new_before ))" = 1 ]

zellij --session helper-s action close-pane -p "$H1"
if zj_watch_worktree "$T/repo" "$BASE" helper-worktree > "$T/dismissed.out"; then
  exit 1
fi
[ ! -s "$T/dismissed.out" ]
R1="$(zj_review_stream "$T/repo" "$BASE" helper-worktree)"
[ -n "$R1" ]
R2="$(zj_review_stream "$T/repo/." "$BASE" helper-worktree)"
[ "$R1" = "$R2" ]

rollup_new_before="$(grep -c 'new-pane' "$ZELLIJ_LOG")"
A1="$(zj_watch_session "$T/repo" "$BASE" helper-session "$R1" "$P6")"
A2="$(zj_watch_session "$T/repo/." "$BASE" helper-session "$R1" "$P6")"
[ "$A1" = "$A2" ]
[ "$(( $(grep -c 'new-pane' "$ZELLIJ_LOG") - rollup_new_before ))" = 1 ]
grep -q "close-pane -p $R1" "$ZELLIJ_LOG"
grep -q "close-pane -p $P6" "$ZELLIJ_LOG"
echo 'public helper routing/reopen/rollup: PASS'

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
! tail -n "+$((before + 1))" "$ZELLIJ_LOG" | grep -q 'focus-pane-id'
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
  unset ZAH_FOCUS_GUARD_WINDOW
  REAL_ZELLIJ="$(PATH="$ORIGINAL_PATH"; command -v zellij)"
  session="zt8-$PPID-$RANDOM"
  feeder_pid=""
  client_pid=""
  cleanup_live() {
    "$REAL_ZELLIJ" delete-session --force "$session" >/dev/null 2>&1 || true
    [ -z "$feeder_pid" ] || kill "$feeder_pid" >/dev/null 2>&1 || true
    [ -z "$client_pid" ] || kill "$client_pid" >/dev/null 2>&1 || true
    [ -z "$feeder_pid" ] || wait "$feeder_pid" 2>/dev/null || true
    [ -z "$client_pid" ] || wait "$client_pid" 2>/dev/null || true
  }
  trap 'cleanup_live; rm -rf "$T"' EXIT
  command -v hunk >/dev/null
  sleep 600 | script -q /dev/null "$REAL_ZELLIJ" --session "$session" options --default-shell zsh >/dev/null 2>&1 &
  client_pid=$!
  feeder_pid="$(jobs -p %%)"
  ready=0
  for _ in $(seq 1 200); do
    if "$REAL_ZELLIJ" --session "$session" action list-panes -j >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 0.1
  done
  [ "$ready" = 1 ]
  setup="$("$REAL_ZELLIJ" --session "$session" action list-panes -j | python3 -c 'import json,sys; print(next(("plugin_" + str(p["id"]) for p in json.load(sys.stdin) if p.get("plugin_url") == "configuration"), ""))')"
  [ -z "$setup" ] || "$REAL_ZELLIJ" --session "$session" action close-pane -p "$setup"
  parent="$("$REAL_ZELLIJ" --session "$session" action list-panes -j | python3 -c 'import json,sys; p=next(p for p in json.load(sys.stdin) if not p.get("is_plugin")); print("terminal_" + str(p["id"]))')"
  "$REAL_ZELLIJ" --session "$session" action rename-pane -p "$parent" agent-parent
  old="$("$REAL_ZELLIJ" --session "$session" action new-pane --direction right --name observer -- sleep 60)"
  live_sid="focus-guard-$RANDOM"
  printf '%s\n' "{\"hook_event_name\":\"SessionStart\",\"session_id\":\"$live_sid\",\"model\":\"gpt-5\",\"turn_id\":\"origin\",\"cwd\":\"$T/repo\"}" > "$T/live-origin.json"
  printf '%s\n' "{\"hook_event_name\":\"PostToolUse\",\"session_id\":\"$live_sid\",\"model\":\"gpt-5\",\"turn_id\":\"edit\",\"cwd\":\"$T/repo\",\"tool_name\":\"apply_patch\",\"tool_input\":{\"file_path\":\"$T/repo/a.txt\"}}" > "$T/live-autodiff.json"
  printf -v hook_command 'PATH=%q ZAH_HOST=codex bash %q < %q && PATH=%q ZAH_HOST=codex bash %q < %q > %q && printf done > %q' \
    "$ORIGINAL_PATH" "$ORIGIN" "$T/live-origin.json" \
    "$ORIGINAL_PATH" "$AUTODIFF" "$T/live-autodiff.json" \
    "$T/live-hook.out" "$T/live-hook.done"
  "$REAL_ZELLIJ" --session "$session" action write-chars -p "$parent" "$hook_command"
  "$REAL_ZELLIJ" --session "$session" action write -p "$parent" 13
  hook_done=0
  for _ in $(seq 1 100); do
    if [ -f "$T/live-hook.done" ]; then
      hook_done=1
      break
    fi
    sleep 0.05
  done
  [ "$hook_done" = 1 ]
  [ "$(cat "$T/live-hook.done")" = done ]
  watcher="$("$REAL_ZELLIJ" --session "$session" action list-panes -j | python3 -c 'import json,sys; p=next(p for p in json.load(sys.stdin) if not p.get("is_plugin") and p.get("title", "").startswith("diff:")); print("terminal_" + str(p["id"]))')"
  "$REAL_ZELLIJ" --session "$session" action list-panes -j -g -s > "$T/live-panes.json"
  "$REAL_ZELLIJ" --session "$session" action list-clients > "$T/live-clients.txt"
  python3 - "$T/live-panes.json" "$parent" "$watcher" "$old" <<'PY'
import json, sys
panes = {("plugin_" if p.get("is_plugin") else "terminal_") + str(p["id"]): p for p in json.load(open(sys.argv[1]))}
assert set(sys.argv[2:]).issubset(panes), (sys.argv[2:], panes)
parent, watcher, old = (panes[pane_id] for pane_id in sys.argv[2:])
assert watcher["pane_x"] == parent["pane_x"] + parent["pane_columns"], (parent, watcher)
assert old["is_focused"], old
PY
  python3 - "$T/live-clients.txt" "$old" <<'PY'
import sys
rows = [line.split() for line in open(sys.argv[1]).read().splitlines()[1:]]
assert len(rows) == 1 and sys.argv[2] in rows[0], (rows, sys.argv[2])
PY
  sleep 1.2
  ! pgrep -f "[h]unk-stream.py focus-guard --session $session" >/dev/null
  "$REAL_ZELLIJ" --session "$session" action list-clients > "$T/live-clients-final.txt"
  python3 - "$T/live-clients-final.txt" "$old" <<'PY'
import sys
rows = [line.split() for line in open(sys.argv[1]).read().splitlines()[1:]]
assert len(rows) == 1 and sys.argv[2] in rows[0], (rows, sys.argv[2])
PY
  cleanup_live
  ! kill -0 "$feeder_pid" 2>/dev/null
  ! kill -0 "$client_pid" 2>/dev/null
  ! "$REAL_ZELLIJ" list-sessions 2>/dev/null | grep -Fq "$session"
  echo "live scratch cleanup: PASS ($session)"
  echo 'live placement/focus: PASS'
fi
