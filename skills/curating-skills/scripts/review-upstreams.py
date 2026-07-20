#!/usr/bin/env python3
"""Create a deterministic Markdown bundle for conceptual upstream reviews."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile


REQUIRED_SOURCE = {"name", "url", "branch", "reviewedCommit", "license", "mappings"}
REQUIRED_MAPPING = {"localSkill", "upstreamPaths"}


class ReviewError(Exception):
    pass


def run_git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, capture_output=True, check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise ReviewError(detail)
    return result.stdout


def load_manifest(path):
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewError(f"manifest could not be read: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ReviewError("manifest must be an object with version 1")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ReviewError("manifest sources must be a non-empty list")
    names = set()
    for source in sources:
        if not isinstance(source, dict) or not REQUIRED_SOURCE <= source.keys():
            raise ReviewError("manifest source is missing required fields")
        if not all(isinstance(source[key], str) and source[key] for key in REQUIRED_SOURCE - {"mappings"}):
            raise ReviewError(f"manifest source {source.get('name', '<unknown>')} has invalid metadata")
        name = source["name"]
        if name in names:
            raise ReviewError(f"manifest source name is duplicated: {name}")
        names.add(name)
        if not isinstance(source["mappings"], list) or not source["mappings"]:
            raise ReviewError(f"manifest source {name} has no mappings")
        for mapping in source["mappings"]:
            if not isinstance(mapping, dict) or not REQUIRED_MAPPING <= mapping.keys():
                raise ReviewError(f"manifest source {name} has an invalid mapping")
            paths = mapping["upstreamPaths"]
            if not isinstance(mapping["localSkill"], str) or not mapping["localSkill"]:
                raise ReviewError(f"manifest source {name} has an invalid local skill")
            if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
                raise ReviewError(f"manifest source {name} has invalid upstream paths")
    return manifest


def cache_name(name):
    value = "".join(character if character.isalnum() or character in "-_" else "-" for character in name)
    return value.strip("-") or "source"


def prepare_repo(source, cache_dir):
    repo = cache_dir / cache_name(source["name"])
    try:
        if (repo / ".git").is_dir():
            run_git(repo, "remote", "set-url", "origin", source["url"])
        else:
            cache_dir.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", "--no-checkout", "--origin", "origin", source["url"], str(repo)],
                text=True, capture_output=True, check=False,
            )
            if result.returncode:
                raise ReviewError(result.stderr.strip() or "clone failed")
        run_git(repo, "fetch", "--prune", "origin", source["branch"])
    except ReviewError as error:
        raise ReviewError(f"{source['name']}: fetch failed: {error}") from error

    head_ref = f"refs/remotes/origin/{source['branch']}"
    try:
        head = run_git(repo, "rev-parse", "--verify", f"{head_ref}^{{commit}}").strip()
        reviewed = run_git(
            repo, "rev-parse", "--verify", f"{source['reviewedCommit']}^{{commit}}",
        ).strip()
    except ReviewError as error:
        raise ReviewError(
            f"{source['name']}: reviewed commit {source['reviewedCommit']} or branch head is unavailable: {error}",
        ) from error
    return repo, reviewed, head


def inventory(repo, reviewed, head):
    lines = run_git(repo, "diff", "--name-status", "--find-renames", reviewed, head).splitlines()
    changes = []
    for line in lines:
        fields = line.split("\t")
        status = fields[0]
        if status.startswith("R") and len(fields) == 3:
            changes.append((status, fields[1], fields[2]))
        elif len(fields) == 2:
            changes.append((status, fields[1]))
    return changes


def path_matches(path, prefix):
    prefix = prefix.rstrip("/")
    return path == prefix or path.startswith(prefix + "/")


def mapped_changes(changes, mapping):
    paths = mapping["upstreamPaths"]
    return [
        change for change in changes
        if any(path_matches(changed_path, prefix) for changed_path in change[1:] for prefix in paths)
    ]


def format_change(change):
    if change[0].startswith("R"):
        return f"- `{change[0]}` `{change[1]}` → `{change[2]}`"
    return f"- `{change[0]}` `{change[1]}`"


def source_report(source, repo, reviewed, head):
    changes = inventory(repo, reviewed, head)
    mappings = sorted(source["mappings"], key=lambda item: item["localSkill"])
    affected = [(mapping, mapped_changes(changes, mapping)) for mapping in mappings]
    affected = [(mapping, changeset) for mapping, changeset in affected if changeset]
    commit_lines = run_git(
        repo, "log", "--reverse", "--format=%H%x09%s", f"{reviewed}..{head}",
    ).splitlines()

    lines = [
        f"## {source['name']}", "",
        f"- URL: `{source['url']}`",
        f"- Branch: `{source['branch']}`",
        f"- Recorded commit: `{reviewed}`",
        f"- Current upstream: `{head}`",
        f"- License: `{source['license']}`",
        "", "### Commits", "",
    ]
    lines.extend(
        f"- `{commit.split(chr(9), 1)[0]}` {commit.split(chr(9), 1)[1]}" for commit in commit_lines
    )
    if not commit_lines:
        lines.append("- No commits since the recorded revision.")
    lines.extend(["", "### Inventory Changes", ""])
    lines.extend(format_change(change) for change in changes)
    if not changes:
        lines.append("- No file changes.")
    lines.extend(["", "### Affected Local Skills", ""])
    for mapping, changeset in affected:
        paths = ", ".join(f"`{path}`" for path in sorted({p for c in changeset for p in c[1:]}))
        lines.append(f"- `{mapping['localSkill']}`: {paths}")
    if not affected:
        lines.append("- No mapped local skills are affected.")
    lines.extend(["", "### Mapped Diffs", ""])
    for mapping, changeset in affected:
        selected_paths = sorted({path for change in changeset for path in change[1:]})
        diff = run_git(
            repo, "diff", "--no-ext-diff", "--find-renames", "--unified=3",
            reviewed, head, "--", *selected_paths,
        ).rstrip()
        lines.extend([f"#### {mapping['localSkill']}", "", "```diff", diff, "```", ""])
    if not affected:
        lines.extend(["No mapped diffs.", ""])
    lines.extend([
        "### Manual Review Checklist", "",
        "1. Compare current local behavior with behavior at the recorded upstream commit and current upstream behavior.",
        "2. Identify ideas worth adapting; do not copy upstream files over local skills.",
        "3. Record an accept or reject decision with rationale for each relevant change.",
        "4. Validate every affected local skill and its contracts after an accepted adaptation.",
        "5. Advance `reviewedCommit` only after accepted and explicitly rejected changes are recorded.",
        "", "This report does not update `reviewedCommit`, local skills, or the upstream repository.", "",
    ])
    return lines


def build_report(manifest, cache_dir):
    lines = [
        "# Upstream Skill Review", "",
        "Generated deterministically from recorded revisions and fetched branch heads.", "",
    ]
    for source in sorted(manifest["sources"], key=lambda item: item["name"]):
        repo, reviewed, head = prepare_repo(source, cache_dir)
        lines.extend(source_report(source, repo, reviewed, head))
    return "\n".join(lines).rstrip() + "\n"


def argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    return parser


def main(argv=None):
    parser = argument_parser()
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        if args.cache_dir:
            report = build_report(manifest, args.cache_dir)
        else:
            with tempfile.TemporaryDirectory(prefix="mk-skills-curation-") as temporary:
                report = build_report(manifest, Path(temporary))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
    except (ReviewError, OSError) as error:
        parser.exit(1, f"review-upstreams: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
