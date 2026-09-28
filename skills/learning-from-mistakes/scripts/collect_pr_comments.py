#!/usr/bin/env python3
"""Collect published PR conversation, review-body and inline comments with gh.

Requires authenticated gh. Writes confidential source material locally.
Window is comment creation/submission time, start inclusive, end exclusive.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode


PRIORITY = re.compile(r'\bP[0-3]\b', re.I)


class CollectionError(RuntimeError):
    """An actionable collection error whose message contains no response body."""


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamps must include a time zone')
    return parsed.astimezone(dt.timezone.utc)


def api(endpoint):
    try:
        result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CollectionError('Could not run gh api; check installation, authentication and connectivity') from error
    if result.returncode:
        # Don't echo response bodies or credentials from external command output.
        raise CollectionError(f'gh api failed for {endpoint.split("?")[0]} (exit {result.returncode})')
    return json.loads(result.stdout)


def pages(endpoint):
    result = []
    for page in range(1, 10000):
        batch = api(f'{endpoint}?per_page=100&page={page}')
        if not isinstance(batch, list):
            raise CollectionError('Expected a paginated JSON array')
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise CollectionError('Pagination limit reached')


def search_prs(query):
    prs = []
    expected = None
    for page in range(1, 11):
        batch = api('search/issues?' + urlencode(dict(q=query, per_page=100, page=page)))
        count = batch['total_count']
        if batch['incomplete_results'] or count > 1000:
            raise CollectionError('Search incomplete or capped; narrow repositories or partition candidate PRs')
        if expected is not None and count != expected:
            raise CollectionError('Search totals changed during pagination; retry with a fresh snapshot')
        expected = count
        prs.extend(batch['items'])
        if len({pr['id'] for pr in prs}) != len(prs):
            raise CollectionError('Duplicate PRs during search pagination; retry with a fresh snapshot')
        if len(prs) == count:
            return [{key: pr[key] for key in ('id', 'number', 'title', 'repository_url',
                                               'html_url', 'created_at', 'updated_at')} for pr in prs]
        if len(prs) > count or not batch['items']:
            raise CollectionError('Search result count does not match fetched PRs')
    raise CollectionError('Search pagination exhausted before total_count')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--author', default=None)
    parser.add_argument('--repo', action='append', default=[], metavar='OWNER/NAME',
                        help='Restrict repositories; repeat for multiple repositories')
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        start, end = timestamp(args.start), timestamp(args.end)
        if start >= end:
            raise ValueError('Start must precede end')
    except ValueError as error:
        parser.error(str(error))
    if args.out.exists():
        parser.error('Output directory already exists; choose a new snapshot directory')
    if any(not re.fullmatch(r'[\w.-]+/[\w.-]+', repo, flags=re.ASCII) for repo in args.repo):
        parser.error('Repositories must use OWNER/NAME without search qualifiers')
    author = args.author or api('user')['login']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*(?:\[bot\])?', author):
        parser.error('Author must be a GitHub login without search qualifiers')
    query = f'is:pr author:{author} updated:>={start.date()}'
    query += ''.join(f' repo:{repo}' for repo in args.repo)
    prs = search_prs(query)

    def collect(pr):
        repo = pr['repository_url'].split('/repos/')[1]
        number = pr['number']
        records = []
        counts = {}
        for kind, endpoint in [('conversation', f'repos/{repo}/issues/{number}/comments'),
                               ('inline', f'repos/{repo}/pulls/{number}/comments'),
                               ('review', f'repos/{repo}/pulls/{number}/reviews')]:
            rows = pages(endpoint)
            if len({row['id'] for row in rows}) != len(rows):
                raise CollectionError(f'Duplicate {kind} records in {repo}#{number}')
            counts[kind] = dict(fetched=len(rows), in_window=0)
            for row in rows:
                when = row.get('submitted_at') if kind == 'review' else row['created_at']
                body = row.get('body') or ''
                if not when or not body.strip():
                    continue
                if start <= timestamp(when) < end:
                    counts[kind]['in_window'] += 1
                    records.append(dict(repo=repo, pr=number, pr_title=pr['title'],
                        pr_created_at=pr['created_at'], kind=kind, id=row['id'],
                        author=(row.get('user') or {}).get('login'), created_at=when,
                        updated_at=row.get('updated_at'), url=row['html_url'],
                        path=row.get('path'), line=row.get('line'),
                        in_reply_to_id=row.get('in_reply_to_id'), body=body))
        return records, dict(repo=repo, pr=number, counts=counts)

    records, coverage = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for rows, counts in pool.map(collect, prs):
            records.extend(rows)
            coverage.append(counts)
    records.sort(key=lambda r: (timestamp(r['created_at']), r['repo'], r['kind'], r['id']))
    if len({(r['kind'], r['id']) for r in records}) != len(records):
        raise CollectionError('Duplicate collected comment identities')
    candidates = [dict(row, candidate_priorities=sorted(set(label.upper() for label in PRIORITY.findall(row['body']))))
                  for row in records if PRIORITY.search(row['body'])]
    # Reserve a new directory only after collection succeeds; never replace a prior run.
    args.out.mkdir(parents=True, mode=0o700, exist_ok=False)
    hashes = {}
    for filename, value in [('comments.json', records), ('prs.json', prs),
                            ('coverage.json', coverage), ('priority-candidates.json', candidates)]:
        payload = (json.dumps(value, indent=2) + '\n').encode('utf-8')
        (args.out / filename).write_bytes(payload)
        hashes[filename] = hashlib.sha256(payload).hexdigest()
    manifest = dict(schema_version=1, author=author, start=start.isoformat(), end=end.isoformat(), query=query,
                    candidate_prs=len(prs), comments=len(records), priority_candidates=len(candidates),
                    fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    sha256=hashes,
                    excluded='Deleted comments, unpublished reviews, inaccessible repositories and index delays; bodies reflect fetched edits, which do not move old comments into the posting-time window')
    # Rename only a fully written manifest into place as the completion marker.
    marker = args.out / '.manifest.tmp'
    marker.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    marker.rename(args.out / 'manifest.json')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    try:
        main()
    except CollectionError as error:
        print(f'Collection failed: {error}', file=sys.stderr)
        raise SystemExit(1)
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Collection failed ({type(error).__name__}). Check API response shape and output permissions; '
              'inspect the output for a completion manifest before using it.', file=sys.stderr)
        raise SystemExit(1)
