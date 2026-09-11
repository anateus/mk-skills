"""Build committed review packages and reconcile declared coverage with Git."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


IDENTITY = ("change", "old_path", "new_path", "old_oid", "new_oid", "old_mode", "new_mode")
PROVENANCE = ("version", "repository", "base", "head", "base_tip")
DIFF_OPTIONS = ["--no-ext-diff", "--no-textconv", "--find-renames", "--no-relative",
                "--ignore-submodules=none", "--no-color"]


def git(root, *args, output=None):
    result = subprocess.run(["git", *args], cwd=root, stdout=output or subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip()
                         or f"git {args[0]} failed ({result.returncode})")
    return result.stdout


def revision(root, ref):
    return git(root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()


def inventory(base, head, base_tip):
    root = str(Path(os.fsdecode(git(None, "rev-parse", "--show-toplevel"))[:-1]).resolve())
    base, head = revision(root, base), revision(root, head)
    git(root, "merge-base", "--is-ancestor", base, head)
    if base_tip is not None:
        base_tip = revision(root, base_tip)
        merge_bases = git(root, "merge-base", "--all", base_tip, head).decode().splitlines()
        if merge_bases != [base]:
            raise ValueError("BASE must be the unique merge base of --base-tip and HEAD")

    fields = git(root, "diff", *DIFF_OPTIONS, "--raw", "--no-abbrev", "-z", base, head, "--").split(b"\0")
    files = []
    offset = 0
    while offset < len(fields) - 1:
        old_mode, new_mode, old_oid, new_oid, change = fields[offset].decode("ascii").split()
        old_mode = old_mode.removeprefix(":")
        old_path = new_path = os.fsdecode(fields[offset + 1])
        offset += 2
        if change.startswith(("R", "C")):
            new_path = os.fsdecode(fields[offset])
            offset += 1
        files.append({
            "change": change,
            "old_path": None if change == "A" else old_path,
            "new_path": None if change == "D" else new_path,
            "old_oid": None if set(old_oid) == {"0"} else old_oid,
            "new_oid": None if set(new_oid) == {"0"} else new_oid,
            "old_mode": old_mode,
            "new_mode": new_mode,
            "coverage": "unreviewed",
            "reason": "",
        })
    return {"version": 1, "repository": root, "base": base, "head": head,
            "base_tip": base_tip, "files": files, "review_failures": []}


def write_package(manifest):
    created = []
    try:
        with tempfile.NamedTemporaryFile(prefix="review-package.", dir=os.environ.get("TMPDIR") or "/tmp",
                                         delete=False) as package:
            package_path = Path(package.name)
            created.append(package_path)
            root, base, head = (manifest[key] for key in ("repository", "base", "head"))

            def write(text):
                package.write(text.encode("utf-8", "surrogateescape"))
                package.flush()

            write(f"# Review package\n\n- Repository root: `{root}`\n- Base SHA: `{base}`\n- Head SHA: `{head}`\n")
            if manifest["base_tip"]:
                write(f"- PR base branch SHA: `{manifest['base_tip']}`\n")
            write("- Coverage manifest: append `.manifest.json` to this package's path.\n\n## Commits\n\n")
            git(root, "log", "--no-color", "--format=- `%H` %s", f"{base}..{head}", "--", output=package)
            write("\n## Diff stat\n\n```text\n")
            git(root, "diff", *DIFF_OPTIONS, "--stat", base, head, "--", output=package)
            write("```\n\n## Full diff\n\n```diff\n")
            git(root, "diff", *DIFF_OPTIONS, "--unified=10", base, head, "--", output=package)
            write("```\n")

        manifest_path = Path(str(package_path) + ".manifest.json")
        fd = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created.append(manifest_path)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(manifest, output, indent=2)
            output.write("\n")
        return package_path
    except BaseException:
        for artifact in created:
            artifact.unlink(missing_ok=True)
        raise


def check_coverage(manifest_path, expected):
    with open(manifest_path, encoding="utf-8") as source:
        saved = json.load(source)
    if not isinstance(saved, dict):
        raise ValueError("manifest must be a JSON object")
    for key in PROVENANCE:
        if key not in saved or saved[key] != expected[key]:
            raise ValueError(f"stale or mismatched provenance: {key}; regenerate and revalidate coverage")
    entries = saved.get("files")
    if not isinstance(entries, list) or len(entries) != len(expected["files"]):
        raise ValueError("file inventory differs from Git (missing or extra entries)")
    remaining = {tuple(entry[key] for key in IDENTITY) for entry in expected["files"]}
    gaps = []
    for entry in entries:
        if not isinstance(entry, dict) or any(key not in entry for key in IDENTITY):
            raise ValueError("file inventory entry is missing identity fields")
        identity = tuple(entry[key] for key in IDENTITY)
        if any(value is not None and not isinstance(value, str) for value in identity) or identity not in remaining:
            raise ValueError("file inventory differs from Git (duplicate, stale, or altered entry)")
        remaining.remove(identity)
        coverage, reason = entry.get("coverage"), entry.get("reason")
        if coverage not in ("reviewed", "partial", "skipped", "unreviewed"):
            raise ValueError("coverage must be reviewed, partial, skipped, or unreviewed")
        if not isinstance(reason, str) or (coverage in ("partial", "skipped") and not reason.strip()):
            raise ValueError("partial and skipped coverage require a reason; reason must be a string")
        if coverage != "reviewed":
            gaps.append({key: entry[key] for key in ("old_path", "new_path", "coverage", "reason")})
    failures = saved.get("review_failures")
    if not isinstance(failures, list) or any(not isinstance(f, str) or not f.strip() for f in failures):
        raise ValueError("review_failures must be a list of nonempty strings")
    print(json.dumps({"total": len(entries), "reviewed": len(entries) - len(gaps),
                      "gaps": gaps, "review_failures": failures}, indent=2))
    return 1 if gaps or failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("package", "check"):
        sub = commands.add_parser(command)
        if command == "check":
            sub.add_argument("manifest", help="package path with .manifest.json appended")
        sub.add_argument("base", metavar="BASE")
        sub.add_argument("head", metavar="HEAD")
        sub.add_argument("--base-tip", help="PR base branch revision; BASE must be its unique merge base with HEAD")
    args = parser.parse_args()
    try:
        expected = inventory(args.base, args.head, args.base_tip)
        if args.command == "package":
            print(write_package(expected))
            return 0
        return check_coverage(args.manifest, expected)
    except (ValueError, OSError) as error:
        print(f"review-{args.command}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
