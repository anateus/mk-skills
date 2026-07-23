#!/usr/bin/env python3
"""Merge mk-skills' shipped agent guidance into a host AGENTS.md / CLAUDE.md.

The guidance ships in ../assets/agents-guidance.md and is written into the
target inside a marker-delimited managed block. Only that block is ever
touched — surrounding content is preserved. Re-running updates the block in
place (idempotent), so it never duplicates and always converges to what the
skill ships.

Safety: dry-run by default (prints a unified diff); --apply writes and first
saves a <target>.bak backup. Never creates files in surprising places — the
target's parent directory must already exist, and a brand-new target file is
only created with --create.

Usage:
  merge-guidance.py --into agents-global            # dry-run (default)
  merge-guidance.py --into agents-global --apply
  merge-guidance.py --target /path/to/AGENTS.md --apply
  merge-guidance.py                                 # list detected targets

  --into  agents-global  -> ~/.agents/AGENTS.md
          claude-global  -> ~/.claude/CLAUDE.md
          agents-project -> ./AGENTS.md
          claude-project -> ./CLAUDE.md
"""
from __future__ import annotations

import argparse
import difflib
import shutil
import sys
from pathlib import Path

BEGIN = "<!-- BEGIN mk-skills:agent-guidance (managed block — edits between the markers are overwritten on re-run) -->"
END = "<!-- END mk-skills:agent-guidance -->"

TARGETS = {
    "agents-global": Path.home() / ".agents" / "AGENTS.md",
    "claude-global": Path.home() / ".claude" / "CLAUDE.md",
    "agents-project": Path.cwd() / "AGENTS.md",
    "claude-project": Path.cwd() / "CLAUDE.md",
}


def fragment_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "agents-guidance.md"


def build_block() -> str:
    frag = fragment_path().read_text().strip()
    return f"{BEGIN}\n{frag}\n{END}\n"


def merged_text(existing: str, block: str) -> str:
    if BEGIN in existing and END in existing:
        pre = existing[: existing.index(BEGIN)]
        post = existing[existing.index(END) + len(END):]
        # drop a leading newline left over from the old block's trailing "\n"
        post = post[1:] if post.startswith("\n") else post
        return pre + block + post
    if existing.strip():
        return existing.rstrip() + "\n\n" + block
    return block


def list_targets() -> None:
    print("Detected candidate targets (pass one via --into or --target):\n")
    for key, path in TARGETS.items():
        state = "exists" if path.is_file() else ("parent ok" if path.parent.is_dir() else "no parent dir")
        managed = ""
        if path.is_file() and BEGIN in path.read_text(errors="replace"):
            managed = "  [already has managed block]"
        print(f"  --into {key:<15} {path}   ({state}){managed}")
    print("\nDry-run by default; add --apply to write (a .bak backup is saved first).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge mk-skills agent guidance into AGENTS.md/CLAUDE.md.")
    ap.add_argument("--into", choices=sorted(TARGETS), help="a standard target location")
    ap.add_argument("--target", help="explicit path to the file to merge into")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry-run diff)")
    ap.add_argument("--create", action="store_true", help="allow creating the target file if absent")
    args = ap.parse_args()

    if not args.into and not args.target:
        list_targets()
        return 0

    target = Path(args.target).expanduser() if args.target else TARGETS[args.into]
    block = build_block()

    if target.is_file():
        existing = target.read_text(errors="replace")
    elif target.exists():
        print(f"error: {target} exists but is not a regular file", file=sys.stderr)
        return 2
    else:
        if not args.create:
            print(f"error: {target} does not exist. Pass --create to make it.", file=sys.stderr)
            return 2
        if not target.parent.is_dir():
            print(f"error: parent dir {target.parent} does not exist (refusing to mkdir).", file=sys.stderr)
            return 2
        existing = ""

    new_text = merged_text(existing, block)

    if new_text == existing:
        print(f"up to date: {target} already contains the current guidance block. No change.")
        return 0

    diff = "".join(
        difflib.unified_diff(
            existing.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(target),
            tofile=f"{target} (after merge)",
        )
    )
    action = "UPDATE" if (BEGIN in existing) else ("CREATE" if existing == "" else "APPEND")
    print(f"[{action}] {target}\n")
    print(diff or "(no textual diff)")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write (a .bak backup is saved first).")
        return 0

    if target.is_file():
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)
        print(f"\nbackup: {backup}")
    target.write_text(new_text)
    print(f"wrote: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
