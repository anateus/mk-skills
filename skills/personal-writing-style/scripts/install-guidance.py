#!/usr/bin/env python3
"""Install personal-writing-style profile guidance into agent instruction files."""
from __future__ import annotations

import argparse
import difflib
import os
import shutil
import sys
from pathlib import Path

BEGIN = "<!-- BEGIN personal-writing-style:profile (managed block; rerunning the installer replaces this section) -->"
END = "<!-- END personal-writing-style:profile -->"


def targets() -> dict[str, Path]:
    return {
        "agents-global": Path.home() / ".agents" / "AGENTS.md",
        "claude-global": Path.home() / ".claude" / "CLAUDE.md",
        "agents-project": Path.cwd() / "AGENTS.md",
        "claude-project": Path.cwd() / "CLAUDE.md",
    }


def default_profile() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return root / "personal-writing-style" / "style-profile.md"


def guidance_block(profile: Path) -> str:
    return f"""{BEGIN}
## Personal writing style

The user's style profile is stored at `{profile}`.

<important if="writing or editing prose intended to sound like the user, or analyzing the user's writing style">
Use `personal-writing-style` and read the profile before drafting. Apply stable traits first, then the closest medium variant. If the profile is missing, state that limitation instead of silently approximating the user's style. Do not read the raw corpus unless the user explicitly asks to rebuild or audit the profile.
</important>
{END}
"""


def merge(existing: str, block: str) -> str:
    has_begin = BEGIN in existing
    has_end = END in existing
    if has_begin != has_end:
        raise ValueError("target contains only one personal-writing-style marker")
    if has_begin:
        start = existing.index(BEGIN)
        finish = existing.index(END, start) + len(END)
        before = existing[:start]
        after = existing[finish:]
        if after.startswith("\n"):
            after = after[1:]
        return before + block + after
    if existing.strip():
        return existing.rstrip() + "\n\n" + block
    return block


def read_target(path: Path, create: bool) -> str:
    if path.is_file():
        return path.read_text(errors="replace")
    if path.exists():
        raise ValueError(f"{path} exists but is not a regular file")
    if not create:
        raise ValueError(f"{path} does not exist; pass --create to make it")
    if not path.parent.is_dir():
        raise ValueError(f"parent directory {path.parent} does not exist")
    return ""


def imports_shared_agents(claude: Path, agents: Path) -> bool:
    if not claude.is_file():
        return False
    shared = agents.expanduser().resolve()
    for line in claude.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("@"):
            continue
        imported = Path(line[1:]).expanduser()
        if imported.resolve() == shared:
            return True
    return False


def show_diff(path: Path, existing: str, updated: str) -> None:
    action = "UPDATE" if BEGIN in existing else ("CREATE" if not existing else "APPEND")
    print(f"[{action}] {path}\n")
    print(
        "".join(
            difflib.unified_diff(
                existing.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=str(path),
                tofile=f"{path} (after merge)",
            )
        )
        or "(no textual diff)"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install personal style profile guidance into AGENTS.md or CLAUDE.md.")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--into", choices=sorted(targets()), help="a standard target location")
    destination.add_argument("--target", help="an explicit AGENTS.md or CLAUDE.md path")
    destination.add_argument("--all-global", action="store_true", help="target both global host files")
    parser.add_argument("--profile", default=str(default_profile()), help="style profile path recorded in the guidance")
    parser.add_argument("--apply", action="store_true", help="write changes; default is a dry-run diff")
    parser.add_argument("--create", action="store_true", help="allow creation when a target file is absent")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    known = targets()
    if args.all_global:
        agents = known["agents-global"]
        claude = known["claude-global"]
        if imports_shared_agents(claude, agents):
            selected = [agents]
            print(f"inherits profile guidance: {claude} imports {agents}; skipping duplicate block")
        else:
            selected = [agents, claude]
    elif args.target:
        selected = [Path(args.target).expanduser()]
    else:
        selected = [known[args.into]]

    profile = Path(args.profile).expanduser().resolve()
    if not profile.is_file():
        print(f"warning: profile does not currently exist: {profile}", file=sys.stderr)
    block = guidance_block(profile)

    pending: list[tuple[Path, str, str]] = []
    try:
        for path in selected:
            existing = read_target(path, args.create)
            pending.append((path, existing, merge(existing, block)))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    changed = [(path, existing, updated) for path, existing, updated in pending if updated != existing]
    for path, existing, updated in pending:
        if updated == existing:
            print(f"up to date: {path} already contains the current profile guidance")
        else:
            show_diff(path, existing, updated)

    if not changed:
        return 0
    if not args.apply:
        print("\nDry-run only. Re-run with --apply to write; each existing target is backed up first.")
        return 0

    for path, existing, updated in changed:
        if existing:
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
            print(f"backup: {backup}")
        path.write_text(updated)
        print(f"wrote: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
