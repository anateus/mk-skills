#!/usr/bin/env python3
"""Capture deterministic, local inputs for a human or agent PR review."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import urllib.parse


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import review_coverage as coverage  # noqa: E402


class PrepError(Exception):
    pass


def run(argv, cwd=None, check=True, input=None):
    env = os.environ.copy()
    if argv[0] == "git":
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_LITERAL_PATHSPECS"] = "1"
        env.pop("GIT_CONFIG_COUNT", None)
        for key in list(env):
            if key.startswith("GIT_CONFIG_KEY_") or key.startswith("GIT_CONFIG_VALUE_"):
                env.pop(key, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except subprocess.TimeoutExpired as error:
        raise PrepError(f"{Path(argv[0]).name} timed out after 60 seconds") from error
    if check and proc.returncode:
        raise PrepError(proc.stderr.decode("utf-8", "replace").strip() or f"{argv[0]} failed")
    return proc


def git(repo, *args, check=True):
    return run(["git", *args], cwd=repo, check=check).stdout


def inventory_at(repo, base, head, base_tip):
    current = Path.cwd()
    try:
        os.chdir(repo)
        return coverage.inventory(base, head, base_tip)
    finally:
        os.chdir(current)


def gh_json(args):
    try:
        proc = run(["gh", *args], check=False)
    except PrepError as error:
        raise PrepError("gh api timed out; check authentication and connectivity") from error
    if proc.returncode:
        endpoint = next((arg.split("?")[0] for arg in args if arg.startswith("repos/") or arg.startswith("search/")), "GraphQL")
        raise PrepError(f"gh request failed for {endpoint} (exit {proc.returncode})")
    try:
        return json.loads(proc.stdout)
    except ValueError as error:
        raise PrepError("gh returned invalid JSON") from error


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2).encode("ascii") + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    return hashlib.sha256(raw).hexdigest()


def write_root_indexes(root, readme, index):
    readme_path, index_path = root / "README.md", root / "index.json"
    if readme_path.exists() and not readme_path.read_text(encoding="utf-8").startswith("# Prepared PRs\n"):
        raise PrepError("output README.md exists and is not owned by this helper")
    if index_path.exists():
        try:
            current = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise PrepError("output index.json exists and is not owned by this helper")
        if not isinstance(current, dict) or "prs" not in current or "failures" not in current:
            raise PrepError("output index.json exists and is not owned by this helper")
    for target, content in ((readme_path, readme.encode("utf-8")),
                            (index_path, (json.dumps(index, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("ascii"))):
        temp = target.with_name(target.name + ".tmp")
        if temp.exists():
            raise PrepError(f"temporary output exists: {temp.name}")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temp, target)


def parse_url(value):
    u = urllib.parse.urlparse(value)
    match = re.fullmatch(r"([^/]+)/([^/]+)/pull/(\d+)/?", u.path.lstrip("/")) if u.scheme in ("https", "http") else None
    if not match or u.hostname not in ("github.com", "www.github.com"):
        raise PrepError(f"unsupported GitHub PR URL: {value}")
    return match.group(1), match.group(2), int(match.group(3))


def repo_path(root, owner, name):
    nested, flat = (root / owner / name).resolve(), (root / name).resolve()
    path = nested if nested.is_dir() else flat
    if root.resolve() not in path.parents:
        raise PrepError("repository path escapes --repos-root")
    if not path.is_dir():
        raise PrepError(f"missing local repository: {path}")
    remote = git(path, "remote", "get-url", "origin").decode().strip()
    expected = f"{owner}/{name}"
    remote = remote.removesuffix(".git")
    ssh = re.fullmatch(r"git@github\.com:([^/]+/[^/]+)", remote)
    parsed = urllib.parse.urlparse(remote)
    if ssh:
        actual = ssh.group(1)
    elif parsed.scheme in ("https", "http") and parsed.hostname in ("github.com", "www.github.com"):
        actual = parsed.path.lstrip("/")
    else:
        actual = ""
    if actual != expected:
        raise PrepError(f"origin mismatch for {path}: expected GitHub repository {expected}")
    return path


def paginated(endpoint):
    result = []
    seen = set()
    for page in range(1, 10000):
        data = gh_json(["api", "-H", "Accept: application/vnd.github+json", f"{endpoint}?per_page=100&page={page}"])
        if not isinstance(data, list):
            raise PrepError("Expected a paginated JSON array")
        ids = [row.get("id") for row in data if isinstance(row, dict) and row.get("id") is not None]
        if len(ids) != len(data) or seen.intersection(ids) or len(set(ids)) != len(ids):
            raise PrepError("Invalid or duplicate records during GitHub pagination")
        seen.update(ids)
        result.extend(data)
        if len(data) < 100:
            return result
    raise PrepError("GitHub pagination limit reached")


def graphql_threads(owner, repo, number):
    all_threads, cursor = [], None
    seen_threads, seen_cursors = set(), set()
    thread_query = "query($owner:String!,$name:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){pageInfo{hasNextPage endCursor} nodes{id isResolved isOutdated path line originalLine comments(first:100){pageInfo{hasNextPage endCursor} nodes{id body createdAt author{login} url databaseId}}}}}}}"
    comment_query = "query($threadId:ID!,$commentCursor:String){node(id:$threadId){... on PullRequestReviewThread{comments(first:100,after:$commentCursor){pageInfo{hasNextPage endCursor} nodes{id body createdAt author{login} url databaseId}}}}}"
    for thread_page in range(10000):
        args = ["api", "graphql", "-f", f"query={thread_query}", "-F", f"owner={owner}", "-F", f"name={repo}", "-F", f"number={number}"]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        response = gh_json(args)
        try:
            connection = response["data"]["repository"]["pullRequest"]["reviewThreads"]
        except (KeyError, TypeError):
            raise PrepError("GraphQL response missing review threads")
        for thread in connection["nodes"]:
            if thread["id"] in seen_threads:
                raise PrepError("duplicate review thread during pagination")
            seen_threads.add(thread["id"])
            comments = list(thread["comments"]["nodes"])
            info = thread["comments"]["pageInfo"]
            for comment_page in range(10000):
                if not info["hasNextPage"]:
                    break
                if not info["endCursor"]:
                    raise PrepError("inner thread pagination cursor missing")
                args = ["api", "graphql", "-f", f"query={comment_query}", "-F", f"threadId={thread['id']}", "-F", f"commentCursor={info['endCursor']}"]
                page = gh_json(args)["data"]["node"]["comments"]
                comments.extend(page["nodes"])
                info = page["pageInfo"]
            else:
                raise PrepError("inner thread pagination limit reached")
            thread["comments"]["nodes"] = comments
            all_threads.append(thread)
        if not connection["pageInfo"]["hasNextPage"]:
            return all_threads
        cursor = connection["pageInfo"].get("endCursor")
        if not cursor or cursor in seen_cursors:
            raise PrepError("outer thread pagination cursor missing or repeated")
        seen_cursors.add(cursor)
    raise PrepError("outer thread pagination limit reached")


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)


def text_blob(repo, oid):
    if not oid:
        return None
    data = git(repo, "cat-file", "blob", oid)
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def sensitive_path(path):
    name = PurePosixPath(path).name.lower()
    return (name == ".env" or name.startswith(".env.") or name.endswith((".pem", ".key"))
            or name in {"secret.yaml", "secret.yml", "secrets.yaml", "secrets.yml", "credentials.yaml", "credentials.yml"}
            or any(part.lower() in {"secrets", "secret", "credentials"} for part in PurePosixPath(path).parts))


def ocr_capture(repo, base, head, manifest, output):
    executable = run(["which", "ocr"], check=False).stdout.decode().strip()
    if not executable:
        raise PrepError("--ocr requested but ocr executable not found")
    version = run([executable, "--version"], check=False).stdout.decode("utf-8", "replace").strip()
    preview = run([executable, "delegate", "preview", "--repo", str(repo), "--from", base, "--to", head, "--format", "json"], cwd=repo)
    parsed = json.loads(preview.stdout)
    include = ("schema_version", "mode", "repository", "from", "to", "commit", "merge_base", "total_files", "reviewable_count", "excluded_count", "total_insertions", "total_deletions")
    allow = lambda rows: [{k: row[k] for k in ("path", "status", "insertions", "deletions", "exclude_reason") if k in row} for row in rows]
    selected = {k: parsed[k] for k in include if k in parsed}
    selected["reviewable_files"] = allow(parsed.get("reviewable_files", []))
    selected["excluded_files"] = allow(parsed.get("excluded_files", []))
    dump(output / "ocr-preview.json", selected)
    paths = [x["path"] for x in selected["reviewable_files"] if x.get("path") and not sensitive_path(x["path"])]
    if paths:
        rules = run([executable, "delegate", "rule", "--repo", str(repo), "--from", base, "--to", head, "--format", "json", *paths], cwd=repo)
        groups = json.loads(rules.stdout)
        dump(output / "ocr-rules.json", {"schema_version": groups.get("schema_version"), "groups": groups.get("groups", [])})
    return {"version": version, "preview": "ocr-preview.json", "rules": "ocr-rules.json" if paths else None}


def materialize(repo, base, head, pr, out, comments, reviews, inline, threads, tickets, issues, ocr_enabled=False, replay=False):
    manifest = inventory_at(repo, base, head, pr["base"]["sha"])
    sensitive = [entry for entry in manifest["files"] if any(sensitive_path(p) for p in (entry["old_path"], entry["new_path"]) if p)]
    special_entries = [entry for entry in manifest["files"] if "160000" in (entry["new_mode"], entry["old_mode"]) or "120000" in (entry["new_mode"], entry["old_mode"])]
    if sensitive or special_entries:
        for entry in sensitive:
            entry["reason"] = "sensitive path; content excluded from package"
        for entry in special_entries:
            entry["reason"] = "submodule or symlink; target content excluded"
        dump(out / "diff-package.txt", {"notice": "Full diff omitted because sensitive or special paths changed; inspect excluded paths only under approved handling.", "paths": [{"old_path": e["old_path"], "new_path": e["new_path"]} for e in sensitive + special_entries]})
    else:
        diff_args = ["git", "-c", "core.quotePath=true", "diff", *coverage.DIFF_OPTIONS, "--unified=10", base, head, "--"]
        diff = run(diff_args, cwd=repo).stdout
        (out / "diff-package.txt").write_bytes(diff)
    dump(out / "coverage-manifest.json", manifest)
    (out / "files").mkdir(exist_ok=True)
    for i, entry in enumerate(manifest["files"], 1):
        item = {"index": i, **entry}
        rawname = entry["new_path"] or entry["old_path"] or f"file-{i}"
        stem = f"{i:04d}-{safe_name(rawname)}"
        path = entry["new_path"] or entry["old_path"] or ""
        sensitive = any(sensitive_path(p) for p in (entry["old_path"], entry["new_path"]) if p)
        mode = entry["new_mode"] or entry["old_mode"] or ""
        special = "160000" in (entry["new_mode"], entry["old_mode"]) or "120000" in (entry["new_mode"], entry["old_mode"])
        old = None if sensitive or special else text_blob(repo, entry["old_oid"])
        new = None if sensitive or special else text_blob(repo, entry["new_oid"])
        if not special and (old is not None or new is not None):
            (out / "files" / f"{stem}.before.txt").write_text(old or "", encoding="utf-8")
            (out / "files" / f"{stem}.after.txt").write_text(new or "", encoding="utf-8")
            for label, data in (("before", old or ""), ("after", new or "")):
                lines = data.splitlines(keepends=True)
                for start in range(0, len(lines), 150):
                    chunk = f"Lines {start + 1}-{min(start + 150, len(lines))} of {len(lines)}\n" + "".join(f"{n + 1}: {line}" for n, line in enumerate(lines[start:start + 150], start))
                    (out / "files" / f"{stem}.{label}.{start // 150 + 1:04d}.txt").write_text(chunk, encoding="utf-8")
        classification = []
        if special and "160000" in (entry["new_mode"], entry["old_mode"]): classification.append("submodule")
        if special and "120000" in (entry["new_mode"], entry["old_mode"]): classification.append("symlink")
        if not special and (old is None and entry["old_oid"] or new is None and entry["new_oid"]): classification.append("binary-or-non-UTF8")
        if sensitive: classification.append("sensitive-path-review-required; content excluded")
        item["classification"] = classification
        record = out / "files" / f"{stem}.json"
        record.write_text(json.dumps(item, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="ascii")
        if not sensitive and not special:
            one = run(["git", "--literal-pathspecs", "diff", *coverage.DIFF_OPTIONS, "--unified=10", base, head, "--", rawname], cwd=repo).stdout
            (out / "files" / f"{stem}.diff").write_bytes(one)
    if not (out / "tickets.json").exists():
        dump(out / "tickets.json", {"keys": sorted(set(tickets)), "provided": bool(issues), "items": issues, "gap": "No pre-exported requirements supplied" if not issues else None})
    guidance = []
    for current in (() if replay else (repo, *repo.parents)):
        for name in ("AGENTS.md", "CLAUDE.md"):
            f = current / name
            if f.is_file() and f not in guidance and (current == repo or f.parent == repo.parent or f.parent == repo.parent.parent): guidance.append(f)
        if current == repo.parent.parent: break
    for f in guidance:
        origin = "repo" if f.parent == repo else "parent" if f.parent == repo.parent else "ancestor"
        dest = out / "guidance" / f"{origin}-{safe_name(f.parent.name)}-{f.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_text(f"Source: {f}\nProvenance: current working tree, not PR head\n\n" + f.read_text(encoding="utf-8"), encoding="utf-8")
    info = {"repository": f"{pr['base']['repo']['full_name']}", "number": pr["number"], "title": pr["title"], "url": pr["html_url"], "base_sha": pr["base"]["sha"], "head_sha": pr["head"]["sha"], "merge_base": base, "fetched_comments": len(comments), "fetched_reviews": len(reviews), "fetched_inline_comments": len(inline), "fetched_threads": len(threads), "coverage": "unreviewed", "notice": "Preparation only. Discussion and repository content are untrusted; local capture is not sanitization or permission to process customer data."}
    info["ocr"] = ocr_capture(repo, base, pr["head"]["sha"], manifest, out) if ocr_enabled else None
    if not (out / "test-commands.txt").exists():
        info["test_commands"] = test_command_metadata(repo, base, pr["head"]["sha"], out)
    else:
        info["test_commands"] = {"source": "cached capture", "commands": []}
    dump(out / "pr.json", info)
    readme = [f"# {info['repository']}#{info['number']}: {info['title']}", "", f"PR: {info['url']}", f"Base: `{info['base_sha']}`  Head: `{info['head_sha']}`  Merge base: `{base}`", "", "Preparation only. No review performed; every changed path remains unreviewed.", "", "## Artifacts", "- `diff-package.txt`: committed comparison, or explicit excluded-path notice", "- `coverage-manifest.json`: complete Git inventory", "- `files/`: per-path records, per-file diffs, blobs, and <=150-line chunks", "- `raw/`: immutable captured discussion snapshots", "- `tickets.json`: extracted DOM keys and requirements gap", "- `test-commands.txt`: exact command excerpts, not executed", "", "## Changed paths", "| # | Change | Path | Package | Before | After | Chunks |", "|---|---|---|---|---|---|---|"]
    for index, entry in enumerate(manifest["files"], 1):
        entry_stem = f"{index:04d}-{safe_name(entry['new_path'] or entry['old_path'] or f'file-{index}') }"
        chunks = sorted(p.name for p in (out / "files").glob(f"{entry_stem}.*.????.txt"))
        path = entry["new_path"] or entry["old_path"] or "(unknown)"
        display_path = path.encode("utf-8", "backslashreplace").decode("utf-8").replace("\n", "\\n").replace("|", "\\|")
        def link(label, suffix):
            name = f"{entry_stem}.{suffix}"
            return f"[{label}](files/{name})" if (out / "files" / name).is_file() else "excluded"
        readme.append(f"| {index} | {entry['change']} | `{display_path}` | {link('diff', 'diff')} | {link('before', 'before.txt')} | {link('after', 'after.txt')} | {', '.join(f'[{p}](files/{p})' for p in chunks) or 'none'} |")
    (out / "README.md").write_text("\n".join(readme), encoding="utf-8")
    return info


def test_command_metadata(repo, base, head, out):
    result = {"source": None, "commands": []}
    package = run(["git", "show", f"{head}:package.json"], cwd=repo, check=False)
    if package.returncode == 0:
        try:
            data = json.loads(package.stdout)
            scripts = data.get("scripts", {})
            selected = [(name, value) for name, value in scripts.items() if any(token in name.lower() for token in ("test", "check", "lint")) and isinstance(value, str)]
            result = {"source": "package.json", "commands": [f"npm run {name}: {value}" for name, value in selected]}
            excerpt = "\n".join(f'  "{name}": {json.dumps(value)},' for name, value in selected)
            (out / "test-commands.txt").write_text(f"Source: {head}:package.json scripts. Not executed.\n\n{excerpt}\n", encoding="utf-8")
        except ValueError:
            result = {"source": "package.json (invalid JSON)", "commands": []}
    if result["source"] is None:
        for name in ("Makefile", "makefile", "GNUmakefile"):
            make = run(["git", "show", f"{head}:{name}"], cwd=repo, check=False)
            if make.returncode == 0:
                commands = [line.rstrip() for line in make.stdout.decode("utf-8", "replace").splitlines() if re.match(r"^[A-Za-z0-9_.-]*test[A-Za-z0-9_.-]*\s*:", line, re.I)]
                result = {"source": name, "commands": commands}
                (out / "test-commands.txt").write_text(f"Source: {head}:{name}. Not executed.\n\n" + "\n".join(commands) + "\n", encoding="utf-8")
                break
    return result


def verify_capture(out):
    expected = json.loads((out / "capture-hashes.json").read_text())
    if not isinstance(expected, dict):
        raise PrepError("invalid capture hash manifest")
    root = out.resolve()
    for relative in expected:
        if not isinstance(relative, str):
            raise PrepError("unsafe cached artifact path")
        parts = PurePosixPath(relative)
        candidate = out / relative
        if parts.is_absolute() or ".." in parts.parts or candidate.is_symlink() or root not in candidate.resolve().parents:
            raise PrepError("unsafe cached artifact path")
    paths = list(out.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise PrepError("unsafe cached artifact path")
    actual = {path.relative_to(out).as_posix() for path in paths if path.is_file() and path != out / "capture-hashes.json"}
    if actual != set(expected):
        raise PrepError("cached capture inventory mismatch")
    for relative, digest in expected.items():
        if hashlib.sha256((out / relative).read_bytes()).hexdigest() != digest:
            raise PrepError(f"cached capture hash mismatch: {relative}")


def prepare(url, args):
    owner, name, number = parse_url(url)
    repo = repo_path(args.repos_root, owner, name)
    slug = f"{owner}-{name}-pr-{number}"
    out = args.output / slug
    if args.reuse:
        raw = out / "raw"
        if not out.is_dir(): raise PrepError(f"offline capture not found: {out}")
        if not raw.is_dir(): raise PrepError(f"offline raw snapshot directory missing: {raw}")
    else:
        if out.exists(): raise PrepError(f"output exists; refusing overwrite: {out}")
        out.mkdir(parents=True, mode=0o700)
        raw = out / "raw"; raw.mkdir(mode=0o700)
    try:
        if args.reuse:
            verify_capture(out)
            meta = json.loads((raw / "pr-metadata.json").read_text())
            comments = json.loads((raw / "issue-comments.json").read_text()); reviews = json.loads((raw / "reviews.json").read_text()); inline = json.loads((raw / "inline-comments.json").read_text()); threads = json.loads((raw / "review-threads.json").read_text())
            pr = meta["pull_request"]
            for sha in (pr["base"]["sha"], pr["head"]["sha"]):
                if run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo, check=False).returncode:
                    raise PrepError("cached pinned commit missing from local repository; offline replay cannot fetch")
            base_sha = pr["base"]["sha"]
            replay_number = len(list(args.output.glob(f"{slug}-reuse-*"))) + 1
            replay_name = f"{slug}-reuse-{replay_number}"
            replay = args.output / replay_name
            if replay.exists(): raise PrepError(f"reuse artifact exists; refusing overwrite: {replay_name}")
            replay.mkdir(mode=0o700)
            replay_raw = replay / "raw"
            replay_raw.mkdir(mode=0o700)
            for cached in raw.iterdir():
                if cached.is_file():
                    (replay_raw / cached.name).write_bytes(cached.read_bytes())
            for name in ("guidance", "tickets.json", "ocr-preview.json", "ocr-rules.json"):
                source = out / name
                target = replay / name
                if source.is_dir():
                    shutil.copytree(source, target)
                elif source.is_file():
                    target.write_bytes(source.read_bytes())
            cached_info = json.loads((out / "pr.json").read_text())
            args.ocr = False
            out = replay
        else:
            pr = gh_json(["api", f"repos/{owner}/{name}/pulls/{number}"])
            for filename, endpoint in (("issue-comments.json", f"repos/{owner}/{name}/issues/{number}/comments"), ("reviews.json", f"repos/{owner}/{name}/pulls/{number}/reviews"), ("inline-comments.json", f"repos/{owner}/{name}/pulls/{number}/comments")):
                values = paginated(endpoint); dump(raw / filename, values)
                if filename == "issue-comments.json": comments = values
                elif filename == "reviews.json": reviews = values
                else: inline = values
            threads = graphql_threads(owner, name, number); dump(raw / "review-threads.json", threads)
            metadata = {"pull_request": pr}; dump(raw / "pr-metadata.json", metadata)
            before = (pr["base"]["sha"], pr["head"]["sha"])
            for sha in before:
                if not run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo, check=False).returncode:
                    continue
                fetch = ["git", "-c", "core.hooksPath=/dev/null", "-c", "diff.external=", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential", "fetch", "--no-tags", "--no-write-fetch-head", "origin", sha]
                os.environ["GIT_TERMINAL_PROMPT"] = "0"
                result = run(fetch, cwd=repo, check=False)
                if result.returncode: raise PrepError(f"fetch failed for pinned SHA {sha}; check local GitHub authentication and repository access")
            after = gh_json(["api", f"repos/{owner}/{name}/pulls/{number}"])
            if before != (after["base"]["sha"], after["head"]["sha"]): raise PrepError("PR base/head moved during capture")
            base_sha = before[0]
        head_sha = pr["head"]["sha"]
        for sha in (base_sha, head_sha):
            run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo)
        bases = git(repo, "merge-base", "--all", base_sha, head_sha).decode().splitlines()
        if len(bases) != 1: raise PrepError(f"expected unique merge base, found {len(bases)}")
        tickets = re.findall(r"\bDOM-\d+\b", (pr.get("title", "") + "\n" + pr.get("body", "")), re.I)
        issues = []
        if args.requirements_dir and not args.reuse:
            for f in sorted(args.requirements_dir.glob("*")):
                if f.is_file() and f.suffix.lower() in (".md", ".json"):
                    issues.append({"file": f.name, "content": f.read_text(encoding="utf-8")})
        info = materialize(repo, bases[0], head_sha, pr, out, comments, reviews, inline, threads, tickets, issues, args.ocr, replay=args.reuse)
        if args.reuse:
            for key in ("ocr", "test_commands", "stack_edges", "notice"):
                if key in cached_info: info[key] = cached_info[key]
            (out / "pr.json").write_text(json.dumps(info, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="ascii")
        info["stack_edges"] = {"base-sha-head-match": pr["base"]["sha"] == head_sha, "base-sha-matches-other-pr-heads": []}
        info["artifact_dir"] = out.relative_to(args.output).as_posix()
        current_hashes = {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob("*")) if p.is_file() and p.name != "capture-hashes.json"}
        if not args.reuse:
            dump(out / "capture-hashes.json", current_hashes)
        else:
            info["artifact_dir"] = out.relative_to(args.output).as_posix()
            original_hashes = json.loads((args.output / slug / "capture-hashes.json").read_text())
            derived_hashes = {k: v for k, v in current_hashes.items() if not k.startswith("raw/")}
            dump(out / "capture-hashes.json", {"snapshot": original_hashes, "derived": derived_hashes})
        return info
    except Exception as error:
        if args.reuse and out == args.output / slug:
            failures = args.output / "replay-failures"
            failures.mkdir(mode=0o700, exist_ok=True)
            attempt = len(list(failures.glob(f"{slug}-*.json"))) + 1
            dump(failures / f"{slug}-{attempt}.json", {"error": str(error), "incomplete": True})
        else:
            dump(out / "capture-failure.json", {"error": str(error), "incomplete": True})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("urls", nargs="+")
    p.add_argument("--repos-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--reuse", action="store_true")
    p.add_argument("--requirements-dir", type=Path)
    p.add_argument("--ocr", action="store_true", help="collect fixed OCR preview/rule JSON only; never review")
    args = p.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    failures, completed = [], []
    for url in args.urls:
        try:
            record = prepare(url, args)
            completed.append(record)
        except Exception as e:
            failures.append({"url": url, "error": str(e)})
    for current in completed:
        current["stack_edges"]["base-sha-matches-other-pr-heads"] = [f"{other['repository']}#{other['number']}" for other in completed if other is not current and current["base_sha"] == other["head_sha"]]
    index = ["# Prepared PRs", "", "Preparation only. No review performed.", ""]
    index += [f"- [{x['repository']}#{x['number']}]({x['artifact_dir']}/README.md): {x['title']} (base {x['base_sha']}, head {x['head_sha']}; stack parents: {', '.join(x['stack_edges']['base-sha-matches-other-pr-heads']) or 'none supplied'})" for x in completed]
    if failures: index += ["", "## Incomplete captures", *[f"- {x['url']}: {x['error']}" for x in failures]]
    write_root_indexes(args.output, "\n".join(index) + "\n", {"prs": completed, "failures": failures})
    if failures:
        print(json.dumps({"completed": len(completed), "failed": failures}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
