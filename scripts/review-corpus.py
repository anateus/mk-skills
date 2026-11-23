#!/usr/bin/env python3
"""Maintain a private corpus of reviewed changes with known defects, kept outside this checkout.

The corpus is its own local git repository holding `corpus.json` (repo remotes), `cases/<id>.json`
(one reviewed change each) and rebuildable bare mirrors under `mirrors/`. `build` turns cases into
the inputs of scripts/evaluate-skills.py; `candidates` mines a mirror for defects that escaped review.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ENV_CORPUS = 'MK_SKILLS_REVIEW_CORPUS'
DEFAULT_CORPUS = Path('~/.local/share/mk-skills/review-corpus')
DEFAULT_PROMPT = ('Review BASE..HEAD before I merge it. Write your findings to assessment.md, each with a '
                  'severity (P1 blocks the merge, P2 should be fixed, P3 minor) and a file location, plus '
                  'any verification limits. Do not change the implementation.')
SOURCES = ('review-comment', 'escaped')
SEVERITIES = ('P1', 'P2')
FIX_KINDS = ('revert', 'hotfix', 'follow-up')
SHA = re.compile(r'^[0-9a-f]{40}$')
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
CORRECTIVE = re.compile(r'^revert|hotfix|rollback|regression|^fix\b', re.I)
TRAILING_PR = re.compile(r'\(#(\d+)\)\s*$')
REVERTS_COMMIT = re.compile(r'This reverts commit ([0-9a-f]{7,40})')
REVERT_SUBJECT = re.compile(r'^Revert "(.*)"$')
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@')
BLAME_HEADER = re.compile(r'^([0-9a-f]{40}) \d+ \d+(?: \d+)?$')
MAX_HUNKS_PER_FILE = 20
GIT_IDENTITY = ['-c', 'user.name=review-corpus', '-c', 'user.email=review-corpus@example.invalid',
                '-c', 'commit.gpgsign=false']


def run(args, git_dir=None, cwd=None, check=True, stdin=None):
    command = ['git']
    if git_dir is not None:
        command += ['--git-dir', str(git_dir)]
    result = subprocess.run(command + list(args), cwd=cwd, input=stdin, capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
    if check and result.returncode:
        raise ValueError('git ' + ' '.join(args[:3]) + ' failed: ' + result.stderr.strip())
    return result


def git(args, git_dir=None, cwd=None):
    return run(args, git_dir=git_dir, cwd=cwd).stdout.strip()


def inside(path, parent):
    return path == parent or parent in path.parents


def refuse_inside_checkout(path, what):
    resolved = Path(path).expanduser().resolve()
    if inside(resolved, ROOT):
        raise ValueError(what + ' must not be inside the tree of this checkout (' + str(ROOT)
                         + '); case data is private: ' + str(resolved))
    return resolved


def resolve_corpus(argument):
    chosen = argument or os.environ.get(ENV_CORPUS) or DEFAULT_CORPUS
    return refuse_inside_checkout(chosen, 'Corpus root')


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise ValueError(str(path) + ' is not valid JSON: ' + str(error))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def load_corpus(corpus):
    path = corpus / 'corpus.json'
    if not path.exists():
        return {'version': 1, 'repos': {}}
    data = read_json(path)
    if data.get('version') != 1 or not isinstance(data.get('repos'), dict):
        raise ValueError('Unsupported corpus.json in ' + str(corpus))
    return data


def mirror_path(corpus, repo):
    return corpus / 'mirrors' / (repo + '.git')


def require_repo(corpus, name):
    data = load_corpus(corpus)
    if name not in data['repos']:
        raise ValueError('Unknown repo ' + repr(name) + '; run add-repo first')
    return data['repos'][name]


def init_corpus_repo(corpus):
    corpus.mkdir(parents=True, exist_ok=True)
    if not (corpus / '.git').exists():
        git(['init', '-b', 'main'], cwd=corpus)
        (corpus / '.gitignore').write_text('mirrors/\n', encoding='utf-8')


def commit_corpus(corpus, message):
    init_corpus_repo(corpus)
    paths = [name for name in ('.gitignore', 'corpus.json', 'cases') if (corpus / name).exists()]
    git(['add', '--all', '--', *paths], cwd=corpus)
    if run(['diff', '--cached', '--quiet'], cwd=corpus, check=False).returncode == 0:
        return
    git([*GIT_IDENTITY, 'commit', '-m', message], cwd=corpus)


def case_files(corpus):
    return sorted((corpus / 'cases').glob('*.json')) if (corpus / 'cases').is_dir() else []


def load_cases(corpus):
    return [read_json(path) for path in case_files(corpus)]


# --- repositories and mirrors -------------------------------------------------------------------

def has_commit(mirror, sha):
    return run(['cat-file', '-e', sha + '^{commit}'], git_dir=mirror, check=False).returncode == 0


def ensure_commit(mirror, sha):
    if has_commit(mirror, sha):
        return
    result = run(['fetch', '--quiet', 'origin', sha], git_dir=mirror, check=False)
    if not has_commit(mirror, sha):
        raise ValueError('Commit ' + sha + ' is not in ' + str(mirror) + ' and could not be fetched: '
                         + result.stderr.strip())


def add_repo(corpus, name, remote):
    if not NAME.match(name):
        raise ValueError('Invalid repo name: ' + name)
    init_corpus_repo(corpus)
    data = load_corpus(corpus)
    data['repos'][name] = {'remote': remote}
    write_json(corpus / 'corpus.json', data)
    mirror = mirror_path(corpus, name)
    if not mirror.exists():
        mirror.parent.mkdir(parents=True, exist_ok=True)
        git(['init', '--bare', str(mirror)])
    if run(['remote', 'get-url', 'origin'], git_dir=mirror, check=False).returncode:
        git(['remote', 'add', 'origin', remote], git_dir=mirror)
    else:
        git(['remote', 'set-url', 'origin', remote], git_dir=mirror)
    commit_corpus(corpus, 'add-repo ' + name)


def owner_and_name(remote):
    match = re.search(r'[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$', remote)
    if not match:
        raise ValueError('Cannot parse owner/name from remote ' + remote)
    return match.group(1), match.group(2)


def fetch_all(corpus):
    data = load_corpus(corpus)
    for name in sorted(data['repos']):
        mirror = mirror_path(corpus, name)
        if not mirror.exists():
            raise ValueError('Mirror missing for ' + name + '; re-run add-repo')
        git(['fetch', '--quiet', 'origin', '+refs/heads/*:refs/heads/*'], git_dir=mirror)
    for case in load_cases(corpus):
        mirror = mirror_path(corpus, case['repo'])
        for key in ('base_sha', 'head_sha'):
            ensure_commit(mirror, case[key])


def resolve_pull(corpus, repo, pr, head):
    remote = require_repo(corpus, repo)['remote']
    owner, name = owner_and_name(remote)
    try:
        result = subprocess.run(['gh', 'api', 'repos/%s/%s/pulls/%d' % (owner, name, pr)],
                                capture_output=True, text=True)
    except OSError as error:
        raise ValueError('gh is required for resolve: ' + str(error))
    if result.returncode:
        raise ValueError('gh api failed: ' + result.stderr.strip())
    pull = json.loads(result.stdout)
    mirror = mirror_path(corpus, repo)
    if not mirror.exists():
        raise ValueError('Mirror missing for ' + repo + '; re-run add-repo')
    head_sha = head or pull['head']['sha']
    base_tip = pull['base']['sha']
    ensure_commit(mirror, head_sha)
    ensure_commit(mirror, base_tip)
    return {
        'id': '%s-%d' % (repo, pr), 'repo': repo, 'pr': pr, 'title': pull['title'], 'url': pull['html_url'],
        'base_sha': git(['merge-base', base_tip, head_sha], git_dir=mirror), 'head_sha': head_sha,
        'control': False, 'notes': '', 'findings': [],
    }


# --- cases --------------------------------------------------------------------------------------

def require_text(owner, key):
    value = owner.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError('%s: %r must be a non-empty string' % (owner.get('id', '?'), key))
    return value


def normalize_finding(raw, case_id):
    if not isinstance(raw, dict):
        raise ValueError(case_id + ': finding must be an object')
    label = case_id + ' finding ' + str(raw.get('id') or raw.get('path') or '?')
    source = raw.get('source', 'review-comment')
    if source not in SOURCES:
        raise ValueError(label + ': source must be one of ' + ', '.join(SOURCES))
    if raw.get('severity') not in SEVERITIES:
        raise ValueError(label + ': severity must be one of ' + ', '.join(SEVERITIES))
    line = raw.get('line')
    if line is not None and (not isinstance(line, int) or isinstance(line, bool)):
        raise ValueError(label + ': line must be an integer or null')
    finding = {'id': raw.get('id'), 'source': source, 'severity': raw['severity']}
    for key in ('path', 'summary', 'confirmation', 'how_discoverable'):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(label + ': ' + key + ' must be a non-empty string')
    finding.update(path=raw['path'], line=line, summary=raw['summary'], confirmation=raw['confirmation'],
                   how_discoverable=raw['how_discoverable'])
    if source == 'review-comment':
        for key in ('reviewer', 'comment_url'):
            if not isinstance(raw.get(key), str) or not raw[key].strip():
                raise ValueError(label + ': ' + key + ' must be a non-empty string')
        if not isinstance(raw.get('reviewer_is_bot'), bool):
            raise ValueError(label + ': reviewer_is_bot must be true or false')
        finding.update(reviewer=raw['reviewer'], reviewer_is_bot=raw['reviewer_is_bot'],
                       comment_url=raw['comment_url'])
    else:
        fix = raw.get('fix')
        if not isinstance(fix, dict):
            raise ValueError(label + ': an escaped finding needs a fix object')
        days = fix.get('days_after_merge')
        if (not isinstance(fix.get('pr'), int) or not isinstance(fix.get('sha'), str)
                or not SHA.match(fix['sha']) or fix.get('kind') not in FIX_KINDS
                or not isinstance(fix.get('url'), str) or not fix['url']
                or not isinstance(days, (int, float)) or isinstance(days, bool)):
            raise ValueError(label + ': fix needs pr, url, a 40-hex sha, kind (' + '|'.join(FIX_KINDS)
                             + ') and days_after_merge')
        finding['fix'] = {key: fix[key] for key in ('pr', 'url', 'sha', 'kind', 'days_after_merge')}
        finding['review_at_the_time'] = require_text(raw, 'review_at_the_time')
        raised = raw.get('raised_in_review', False)
        if not isinstance(raised, bool):
            raise ValueError(label + ': raised_in_review must be true or false')
        if raised:
            finding['raised_in_review'] = True
    return finding


def normalize_case(raw):
    if not isinstance(raw, dict):
        raise ValueError('A case must be a JSON object')
    raw = dict(raw)
    if 'reviewed_sha' in raw:
        raw.setdefault('head_sha', raw.pop('reviewed_sha'))
    repo = raw.get('repo')
    if not isinstance(repo, str) or not NAME.match(repo):
        raise ValueError('A case needs a valid repo name')
    if not isinstance(raw.get('pr'), int) or isinstance(raw.get('pr'), bool):
        raise ValueError(repo + ': pr must be an integer')
    case_id = raw.get('id') or '%s-%d' % (repo, raw['pr'])
    raw['id'] = case_id
    for key in ('title', 'url'):
        require_text(raw, key)
    for key in ('base_sha', 'head_sha'):
        if not isinstance(raw.get(key), str) or not SHA.match(raw[key]):
            raise ValueError(case_id + ': ' + key + ' must be a 40-hex sha')
    if not isinstance(raw.get('control'), bool):
        raise ValueError(case_id + ': control must be true or false')
    findings = raw.get('findings')
    if not isinstance(findings, list):
        raise ValueError(case_id + ': findings must be a list')
    if raw['control'] and findings:
        raise ValueError(case_id + ': a control has no findings')
    if not raw['control'] and not findings:
        raise ValueError(case_id + ': a non-control case needs at least one finding')
    return {
        'id': case_id, 'repo': repo, 'pr': raw['pr'], 'title': raw['title'], 'url': raw['url'],
        'base_sha': raw['base_sha'], 'head_sha': raw['head_sha'], 'control': raw['control'],
        'notes': raw.get('notes') or '', 'added_at': raw.get('added_at'),
        'findings': [normalize_finding(finding, case_id) for finding in findings],
    }


def validate_stored_case(case):
    ids = [finding['id'] for finding in case['findings']]
    if ids != ['F%d' % number for number in range(1, len(ids) + 1)]:
        raise ValueError(case['id'] + ': finding ids must be F1..Fn without gaps or duplicates')


def diff_stats(mirror, base, head):
    text = git(['diff', '--shortstat', base, head], git_dir=mirror)
    count = lambda pattern: int((re.search(pattern, text) or [0, 0])[1])
    return (count(r'(\d+) files? changed'),
            count(r'(\d+) insertions?') + count(r'(\d+) deletions?'))


def same_finding(known, new):
    if new.get('comment_url') and new.get('comment_url') == known.get('comment_url'):
        return True
    fix, known_fix = new.get('fix'), known.get('fix')
    return bool(fix and known_fix and fix['pr'] == known_fix['pr'] and new['path'] == known['path'])


def add_case(corpus, raw):
    case = normalize_case(raw)
    name = case['repo']
    require_repo(corpus, name)
    mirror = mirror_path(corpus, name)
    if not mirror.exists():
        raise ValueError('Mirror missing for ' + name + '; re-run add-repo')
    for key in ('base_sha', 'head_sha'):
        ensure_commit(mirror, case[key])
    merge_base = git(['merge-base', case['base_sha'], case['head_sha']], git_dir=mirror)
    if merge_base != case['base_sha']:
        raise ValueError('%s: base_sha %s is not the merge base of base and head (%s)'
                         % (case['id'], case['base_sha'], merge_base))
    path = corpus / 'cases' / (case['id'] + '.json')
    existing = read_json(path) if path.exists() else None
    if existing:
        if (existing['base_sha'], existing['head_sha']) != (case['base_sha'], case['head_sha']):
            raise ValueError(case['id'] + ': exists with different base/head; refusing to merge')
        result = existing
    else:
        result = case
        result['added_at'] = result['added_at'] or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    result['changed_files'], result['changed_lines'] = diff_stats(mirror, case['base_sha'], case['head_sha'])
    added = 0
    if existing:
        for finding in case['findings']:
            if any(same_finding(known, finding) for known in result['findings']):
                continue
            finding['id'] = 'F%d' % (len(result['findings']) + 1)
            result['findings'].append(finding)
            added += 1
    else:
        for number, finding in enumerate(result['findings'], 1):
            finding['id'] = 'F%d' % number
        added = len(result['findings'])
    validate_stored_case(result)
    ordered = {key: result[key] for key in (
        'id', 'repo', 'pr', 'title', 'url', 'base_sha', 'head_sha', 'changed_files', 'changed_lines',
        'control', 'notes', 'added_at', 'findings')}
    write_json(path, ordered)
    return case['id'], existing is None, added


def add_cases(corpus, raw):
    cases = raw if isinstance(raw, list) else [raw]
    init_corpus_repo(corpus)
    outcomes = [add_case(corpus, case) for case in cases]
    changed = [case_id for case_id, created, added in outcomes if created or added]
    if changed:
        shown = ', '.join(changed[:4]) + (' +%d more' % (len(changed) - 4) if len(changed) > 4 else '')
        commit_corpus(corpus, 'add cases: ' + shown)
    return outcomes


def list_cases(corpus):
    lines = []
    for case in load_cases(corpus):
        findings = case['findings']
        counts = {source: sum(1 for item in findings if item['source'] == source) for source in SOURCES}
        raised = sum(1 for item in findings if item.get('raised_in_review'))
        lines.append('%s control=%s review-comment=%d escaped=%d raised=%d changed_lines=%d' % (
            case['id'], str(case['control']).lower(), counts['review-comment'], counts['escaped'], raised,
            case['changed_lines']))
    return lines


# --- build --------------------------------------------------------------------------------------

def build(corpus, out, prompt, ids, source):
    out = refuse_inside_checkout(out, 'Build output directory')
    if out.exists():
        raise ValueError('Output directory already exists: ' + str(out))
    cases = load_cases(corpus)
    known = {case['id'] for case in cases}
    for case_id in ids:
        if case_id not in known:
            raise ValueError('Unknown case ' + case_id)
    selected = []
    for case in cases:
        if ids and case['id'] not in ids:
            continue
        if source:
            case = dict(case, findings=[item for item in case['findings'] if item['source'] == source])
            if not case['control'] and not case['findings']:
                continue
        selected.append(case)
    if not selected:
        raise ValueError('No cases selected')
    cases_json, workspaces = [], {}
    for case in selected:
        mirror = mirror_path(corpus, case['repo'])
        if not mirror.exists():
            raise ValueError('Mirror missing for ' + case['repo'] + '; run add-repo')
        cases_json.append({'id': case['id'], 'prompt': prompt.replace('{title}', case['title']),
                           'expectedSkills': ['reviewing-code'],
                           'forbiddenSkills': [], 'expectedReferences': [], 'rubric': []})
        workspaces[case['id']] = {'repository': {'path': str(mirror.resolve()), 'base': case['base_sha'],
                                                 'head': case['head_sha']}}
        if case['control']:
            criteria = [{'id': 'C1', 'criterion': 'The report raises no P1 or merge-blocking finding.'}]
        else:
            criteria = []
            for item in case['findings']:
                criterion = {'id': item['id'], 'criterion': (
                    'The report identifies this defect (in its own words is fine; it must be recognizably '
                    'the same problem, at or near ' + item['path'] + '): ' + item['summary']),
                    'source': item['source'], 'severity': item['severity']}
                if item['source'] == 'escaped':
                    criterion['raised_in_review'] = bool(item.get('raised_in_review'))
                criteria.append(criterion)
        write_json(out / 'criteria' / (case['id'] + '.json'), criteria)
    write_json(out / 'cases.json', cases_json)
    write_json(out / 'workspaces.json', workspaces)
    return len(selected)


# --- candidates ---------------------------------------------------------------------------------

def parse_day(text):
    try:
        return datetime.strptime(text, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError('Dates must be YYYY-MM-DD: ' + text)


def iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def default_branch(mirror, requested):
    names = [requested] if requested else [
        run(['symbolic-ref', '--quiet', '--short', 'HEAD'], git_dir=mirror, check=False).stdout.strip(),
        'main', 'master']
    for name in names:
        if name and run(['rev-parse', '--verify', '--quiet', 'refs/heads/' + name], git_dir=mirror,
                        check=False).returncode == 0:
            return name
    raise ValueError('No default branch found in %s; pass --branch' % mirror)


def first_parent_history(mirror, branch):
    text = run(['log', '--first-parent', '--format=%H%x1f%ct%x1f%P%x1f%s%x1f%b%x1e', 'refs/heads/' + branch],
               git_dir=mirror).stdout
    history = {}
    for record in text.split('\x1e'):
        record = record.lstrip('\n')
        if not record:
            continue
        sha, committed, parents, subject, body = record.split('\x1f', 4)
        history[sha] = {'sha': sha, 'ct': int(committed), 'parents': parents.split(), 'subject': subject,
                        'body': body}
    return history


def pull_number(subject):
    match = TRAILING_PR.search(subject)
    return int(match.group(1)) if match else None


def describe(commit):
    return {'sha': commit['sha'], 'pr': pull_number(commit['subject']), 'subject': commit['subject'],
            'date': iso(commit['ct'])}


def old_side_ranges(mirror, commit):
    """Return {path: [(first, last)]} of old-side line ranges, skipping additions, binaries, huge files."""
    text = run(['-c', 'core.quotepath=off', 'diff', '-U0', '--no-renames', '--no-color',
                commit['parents'][0], commit['sha']], git_dir=mirror).stdout
    files, path, header, binary, hunks, ranges = {}, None, False, False, 0, []

    def close():
        if path and not binary and ranges and hunks <= MAX_HUNKS_PER_FILE:
            files[path] = list(ranges)

    for line in text.split('\n'):
        if line.startswith('diff --git '):
            close()
            path, header, binary, hunks, ranges = None, True, False, 0, []
        elif header and line.startswith('--- '):
            path = line[6:] if line.startswith('--- a/') else None
        elif header and line.startswith('Binary files'):
            binary = True
        elif line.startswith('@@'):
            header = False
            match = HUNK.match(line)
            if match:
                hunks += 1
                start, length = int(match.group(1)), int(match.group(2) if match.group(2) is not None else 1)
                if length:
                    ranges.append((start, start + length - 1))
    close()
    return files


def blame_counts(mirror, commit, path, ranges):
    args = ['blame', '--porcelain']
    for first, last in ranges:
        args += ['-L', '%d,%d' % (first, last)]
    result = run(args + [commit['parents'][0], '--', path], git_dir=mirror, check=False)
    counts = {}
    for line in result.stdout.split('\n'):
        match = BLAME_HEADER.match(line)
        if match:
            counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    return counts


def reverted_commit(mirror, history, commit):
    match = REVERTS_COMMIT.search(commit['body'])
    if match:
        result = run(['rev-parse', '--verify', '--quiet', match.group(1) + '^{commit}'], git_dir=mirror,
                     check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    quoted = REVERT_SUBJECT.match(TRAILING_PR.sub('', commit['subject']).strip())
    if quoted:
        for other in history.values():
            if other['subject'] == quoted.group(1) and other['ct'] <= commit['ct']:
                return other['sha']
    return None


def commit_record(mirror, history, sha):
    if sha in history:
        return history[sha]
    committed, subject = git(['show', '-s', '--format=%ct%x1f%s', sha], git_dir=mirror).split('\x1f', 1)
    return {'sha': sha, 'ct': int(committed), 'subject': subject, 'body': '', 'parents': []}


def corrections(mirror, history, fixes, window):
    """Yield (fix, origin sha, blame entry, explicit) for each earlier PR commit a corrective commit rewrote."""
    for fix in fixes:
        found = {}
        for path, ranges in old_side_ranges(mirror, fix).items():
            for sha, lines in blame_counts(mirror, fix, path, ranges).items():
                entry = found.setdefault(sha, {'lines': 0, 'files': set()})
                entry['lines'] += lines
                entry['files'].add(path)
        fix_pr = pull_number(fix['subject'])
        kept = {}
        for sha, entry in found.items():
            origin = history.get(sha)
            if (origin is None or sha == fix['sha'] or not 0 <= fix['ct'] - origin['ct'] <= window
                    or pull_number(origin['subject']) is None or pull_number(origin['subject']) == fix_pr):
                continue
            kept[sha] = entry
        explicit_sha = reverted_commit(mirror, history, fix) if (
            REVERTS_COMMIT.search(fix['body']) or REVERT_SUBJECT.match(fix['subject'])) else None
        if explicit_sha and explicit_sha != fix['sha']:
            kept.setdefault(explicit_sha, found.get(explicit_sha) or {'lines': 0, 'files': set()})
        for sha, entry in kept.items():
            yield fix, sha, entry, sha == explicit_sha


def is_corrective(commit):
    return bool(CORRECTIVE.search(commit['subject']) or REVERTS_COMMIT.search(commit['body']))


def open_mirror(corpus, repo):
    require_repo(corpus, repo)
    mirror = mirror_path(corpus, repo)
    if not mirror.exists():
        raise ValueError('Mirror missing for ' + repo + '; run add-repo')
    return mirror


def find_candidates(corpus, repo, since, until, window_days, branch):
    mirror = open_mirror(corpus, repo)
    start = int(parse_day(since).timestamp())
    end = int((parse_day(until) + timedelta(days=1)).timestamp()) if until else None
    history = first_parent_history(mirror, default_branch(mirror, branch))
    window = window_days * 86400
    corrective = [commit for commit in history.values()
                  if commit['parents'] and start <= commit['ct'] and (end is None or commit['ct'] < end)
                  and is_corrective(commit)]
    pairs = []
    for fix, sha, entry, explicit in corrections(mirror, history, corrective, window):
        origin = commit_record(mirror, history, sha)
        pairs.append({'repo': repo, 'fix': describe(fix), 'origin': describe(origin),
                      'days': round((fix['ct'] - origin['ct']) / 86400, 2), 'lines': entry['lines'],
                      'files': sorted(entry['files']), 'explicit': explicit})
    pairs.sort(key=lambda pair: (not pair['explicit'], -pair['lines']))
    return len(corrective), pairs


# --- controls -----------------------------------------------------------------------------------

def find_controls(corpus, repo, since, until, window_days, min_lines, max_lines, max_files, branch):
    mirror = open_mirror(corpus, repo)
    start = int(parse_day(since).timestamp())
    end = int((parse_day(until) + timedelta(days=1)).timestamp())
    history = first_parent_history(mirror, default_branch(mirror, branch))
    window = window_days * 86400
    newest = max((commit['ct'] for commit in history.values()), default=0)
    latest = (datetime.fromtimestamp(newest - window, timezone.utc)).strftime('%Y-%m-%d')
    if parse_day(until).strftime('%Y-%m-%d') > latest:
        raise ValueError('--until %s is too recent: PRs need %s days to be corrected; the latest allowed is %s'
                         % (until, window_days, latest))
    leads = {}
    for commit in history.values():
        if (not commit['parents'] or not start <= commit['ct'] < end or pull_number(commit['subject']) is None
                or is_corrective(commit)):
            continue
        files, lines = diff_stats(mirror, commit['parents'][0], commit['sha'])
        if min_lines <= lines <= max_lines and 0 < files <= max_files:
            leads[commit['sha']] = (files, lines)
    fixes = [commit for commit in history.values()
             if commit['parents'] and start <= commit['ct'] < end + window and is_corrective(commit)]
    for fix, sha, entry, explicit in corrections(mirror, history, fixes, window):
        origin = history.get(sha)
        if origin is not None and 0 <= fix['ct'] - origin['ct'] <= window and (explicit or entry['lines'] >= 1):
            leads.pop(sha, None)
    controls = []
    for sha, (files, lines) in leads.items():
        commit = history[sha]
        controls.append({'repo': repo, 'pr': pull_number(commit['subject']), 'sha': sha,
                         'subject': commit['subject'], 'date': iso(commit['ct']), 'changed_lines': lines,
                         'changed_files': files})
    controls.sort(key=lambda control: control['date'])
    return controls


# --- command line -------------------------------------------------------------------------------

def read_source(name):
    text = sys.stdin.read() if name == '-' else Path(name).read_text(encoding='utf-8')
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError('Input is not valid JSON: ' + str(error))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    corpus_help = 'corpus root (default: $%s, else %s)' % (ENV_CORPUS, DEFAULT_CORPUS)
    parser.add_argument('--corpus', help=corpus_help)
    commands = parser.add_subparsers(dest='command', required=True)

    def command(name, help_text):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument('--corpus', default=argparse.SUPPRESS, help=corpus_help)
        return sub

    sub = command('add-repo', 'record a repo remote and create its bare mirror')
    sub.add_argument('name')
    sub.add_argument('remote')
    sub = command('add', 'add or extend cases from a JSON file (- for stdin)')
    sub.add_argument('file')
    sub = command('resolve', 'print a case skeleton for a pull request')
    sub.add_argument('--repo', required=True)
    sub.add_argument('--pr', type=int, required=True)
    sub.add_argument('--head', help='reviewed head sha (default: the pull request head)')
    command('fetch', 'update mirrors and make sure every case commit is present')
    command('list', 'one line per case')
    sub = command('build', 'write evaluate-skills.py inputs')
    sub.add_argument('--out', required=True)
    group = sub.add_mutually_exclusive_group()
    group.add_argument('--prompt', help='"{title}" becomes the PR title, the stated intent a reviewer would have')
    group.add_argument('--prompt-file', type=Path)
    sub.add_argument('--case', action='append', default=[])
    sub.add_argument('--source', choices=SOURCES)
    sub = command('candidates', 'print JSONL of possible escaped defects found in a mirror')
    sub.add_argument('--repo', required=True)
    sub.add_argument('--since', required=True)
    sub.add_argument('--until')
    sub.add_argument('--window-days', type=float, default=7)
    sub.add_argument('--branch')
    sub = command('controls', 'print JSONL of merged PRs that look clean: no corrective commit rewrote them')
    sub.add_argument('--repo', required=True)
    sub.add_argument('--since', required=True)
    sub.add_argument('--until', required=True)
    sub.add_argument('--window-days', type=float, default=14)
    sub.add_argument('--min-lines', type=int, default=40)
    sub.add_argument('--max-lines', type=int, default=800)
    sub.add_argument('--max-files', type=int, default=25)
    sub.add_argument('--branch')
    return parser


def execute(args):
    corpus = resolve_corpus(args.corpus)
    if args.command == 'add-repo':
        add_repo(corpus, args.name, args.remote)
    elif args.command == 'add':
        for case_id, created, added in add_cases(corpus, read_source(args.file)):
            print('%s: %s, %d finding(s) added' % (case_id, 'created' if created else 'existing', added))
    elif args.command == 'resolve':
        print(json.dumps(resolve_pull(corpus, args.repo, args.pr, args.head), indent=2))
    elif args.command == 'fetch':
        fetch_all(corpus)
    elif args.command == 'list':
        for line in list_cases(corpus):
            print(line)
    elif args.command == 'build':
        prompt = args.prompt_file.read_text(encoding='utf-8').strip() if args.prompt_file else (
            args.prompt or DEFAULT_PROMPT)
        build(corpus, args.out, prompt, args.case, args.source)
    elif args.command == 'candidates':
        examined, pairs = find_candidates(corpus, args.repo, args.since, args.until, args.window_days,
                                          args.branch)
        for pair in pairs:
            print(json.dumps(pair))
        print('review-corpus: %d corrective commit(s) examined, %d pair(s), %d explicit'
              % (examined, len(pairs), sum(1 for pair in pairs if pair['explicit'])), file=sys.stderr)
    elif args.command == 'controls':
        controls = find_controls(corpus, args.repo, args.since, args.until, args.window_days,
                                 args.min_lines, args.max_lines, args.max_files, args.branch)
        for control in controls:
            print(json.dumps(control))
        print('review-corpus: %d control lead(s)' % len(controls), file=sys.stderr)
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return execute(args)
    except (OSError, ValueError) as error:
        print('review-corpus: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
