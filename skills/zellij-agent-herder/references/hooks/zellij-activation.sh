#!/bin/sh
# SessionStart hook — surfaces zellij session context so the zellij-agent-herder
# skill activates reliably. Installed into ~/.claude/hooks/ by install-hook.sh.
# No-ops silently outside zellij. For SessionStart, plain stdout is added to
# Claude's context, so we just print (no JSON, no jq/python dependency).
#
# Self-heal: `npx/pnpx skills add|update` only refreshes ~/.claude/skills/<name>/
# (or a project's ./.claude/skills/<name>/) — it never touches ~/.claude/hooks/,
# so a fix to hunk-autodiff.sh or zellij-agent-status.sh can land in the skill
# source while the *installed* copy Claude Code actually runs keeps executing the
# old, buggy version indefinitely with no signal it drifted (this previously
# resurfaced a legacy pane-placement bug after its source fix). Since this hook already
# fires every session, use it to keep those two ALREADY-installed copies in sync
# with whichever skill dir is active (project dir wins over global — same
# precedence the `skills` CLI itself uses). Only syncs files that already exist
# in ~/.claude/hooks/ — a user who never opted in via install-hooks.sh gets
# nothing created here. Never touches this file itself (a running script
# shouldn't overwrite its own source) — re-run install-hook.sh once after
# editing zellij-activation.sh to pick that change up.
set -eu
# Drain the hook-input JSON on stdin (we don't need it) so nothing blocks.
cat >/dev/null 2>&1 || true
# ZELLIJ is a client index (0 for the primary/only client) whenever inside
# zellij — presence, not truthiness, so "0" still means inside.
[ -n "${ZELLIJ:-}" ] || exit 0
sess="${ZELLIJ_SESSION_NAME:-unknown}"
pane="${ZELLIJ_PANE_ID:-unknown}"

_zah_skill_dir() {
  for d in "$PWD/.claude/skills/zellij-agent-herder" "$HOME/.claude/skills/zellij-agent-herder"; do
    [ -f "$d/scripts/hunk-autodiff.sh" ] && { printf '%s\n' "$d"; return 0; }
  done
  return 1
}
if skill_dir="$(_zah_skill_dir)"; then
  hooks_dir="$HOME/.claude/hooks"
  for f in hunk-autodiff.sh zellij-agent-status.sh; do
    src="$skill_dir/scripts/$f" dst="$hooks_dir/$f"
    if [ -f "$dst" ] && [ -f "$src" ] && ! cmp -s "$src" "$dst" 2>/dev/null; then
      cp "$src" "$dst" 2>/dev/null && chmod +x "$dst" 2>/dev/null || true
    fi
  done
fi

cat <<EOF
You are running inside a zellij session (ZELLIJ=$ZELLIJ, session "$sess", pane "$pane").
The zellij-agent-herder skill applies here: use it for any task involving zellij
panes/tabs/sessions, spawning or coordinating peer coding agents, waiting on their
output or status, or watching a live diff -- prefer it over raw zellij commands.
EOF
exit 0
