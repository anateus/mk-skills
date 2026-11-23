#!/usr/bin/env python3
"""Evolve review guidance against an external review corpus.

Inputs are produced by review-corpus.py build. Supply a JSON split with nonempty,
disjoint train, val and test ID arrays covering the corpus. All run artifacts,
including model prompts and reports, contain private data and must stay outside
this checkout. Models receive corpus evidence; use only authorized providers.

Run with: uv run --with 'gepa==0.1.4' python scripts/evolve-review-skill.py --help
"""
from __future__ import annotations

import argparse
import atexit
import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / 'scripts/evaluate-skills.py'
SKILL_REL = Path('skills/reviewing-code/SKILL.md')
GATE_REL = Path('skills/reviewing-code/references/merge-decisions.md')
COMPONENT_SETS = {'skill': ('skill',), 'skill,gate': ('skill', 'gate')}
JUDGE_PROMPT_VERSION = 'v1'
MAX_CHARS = 9000
GATE_MAX_CHARS = 7000
OMP_ROLES = ('default', 'smol', 'slow', 'plan', 'task', 'tiny', 'judge')
TASK_TEXT = ('Review the change BASE..HEAD in an unseen repository and decide whether it can merge without a human looking '
             'at it. Write assessment.md: findings with severity (P1 blocks the merge, P2 should be fixed, P3 minor) and '
             'file location, verification limits, then Risk / Outcome / Verdict (merge|block|human) lines.')

# ----------------------------------------------------------------------------------------------- logging, processes

_log_lock = threading.Lock()
_log_file: Path | None = None


def log(message: str) -> None:
    line = time.strftime('%H:%M:%S ') + message
    with _log_lock:
        print(line, file=sys.stderr, flush=True)
        if _log_file is not None:
            with _log_file.open('a') as handle:
                handle.write(line + '\n')


_children: set[subprocess.Popen] = set()
_children_lock = threading.Lock()


def kill_children() -> None:
    with _children_lock:
        live = list(_children)
    for proc in live:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
    deadline = time.monotonic() + 20
    for proc in live:
        try:
            proc.wait(max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass


atexit.register(kill_children)


def run_group(command, *, stdin_text=None, cwd=None, timeout, env=None):
    """Run a command in its own process group; on timeout, SIGTERM the group (the evaluator cleans up its temp tree)."""
    proc = subprocess.Popen([str(part) for part in command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, cwd=cwd, env=env, start_new_session=True)
    with _children_lock:
        _children.add(proc)
    try:
        try:
            out, err = proc.communicate(stdin_text, timeout=timeout)
            return proc.returncode, out, err, False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
            try:
                out, err = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                out, err = proc.communicate()
            return proc.returncode, out, err, True
    finally:
        with _children_lock:
            _children.discard(proc)


def omp_text(prompt: str, model: str, *, neutral: Path, timeout: float = 900, attempts: int = 2) -> str:
    """One isolated no-tools omp call; prompt on stdin, assistant text on stdout."""
    neutral.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^A-Za-z0-9]+', '-', model)
    config = neutral / f'omp-{slug}.json'
    if not config.exists():
        overlay = {'memory': {'backend': 'off'}, 'autolearn': {'enabled': False}, 'advisor': {'enabled': False},
                   'retry': {'modelFallback': False}, 'prewalk': {'enabled': False, 'auto': 'off'},
                   'modelRoles': {role: model for role in OMP_ROLES}}
        config.write_text(json.dumps(overlay, indent=2) + '\n')
    executable = shutil.which('omp')
    if not executable:
        raise RuntimeError('omp CLI is unavailable')
    command = [executable, '-p', '--no-tools', '--no-session', '--no-skills', '--no-rules', '--no-context-files',
               '--no-extensions', '--no-lsp', '--no-title', '--offline', '--model', model, '--config', config]
    last = ''
    for attempt in range(attempts):
        code, out, err, timed_out = run_group(command, stdin_text=prompt, cwd=neutral, timeout=timeout)
        if code == 0 and not timed_out and out.strip():
            return out
        last = f'exit={code} timed_out={timed_out} stderr={err.strip()[-300:]}'
        log(f'omp_text({model}) attempt {attempt + 1} failed: {last}')
    raise RuntimeError(f'omp_text({model}) failed: {last}')


# ----------------------------------------------------------------------------------------------- corpus and split

class Case:
    def __init__(self, cid, corpus, criteria, repository):
        self.id = cid
        self.control = bool(corpus['control'])
        self.title = corpus.get('title', '')
        self.criteria = criteria
        self.findings = {f['id']: f for f in corpus.get('findings', [])}
        self.repository = repository
        self.known = [c for c in criteria if c['id'].startswith('F')]
        self.kind = 'control' if self.control else 'defect'
        known_findings = [self.findings[c['id']] for c in self.known]
        self.has_p1 = any(f['severity'] == 'P1' and (f['source'] == 'escaped' or f.get('reviewer_is_bot') is False)
                          for f in known_findings)


def load_cases(corpus: Path, inputs: Path) -> dict[str, Case]:
    fixtures = json.loads((inputs / 'workspaces.json').read_text())
    evaluator_ids = {case['id'] for case in json.loads((inputs / 'cases.json').read_text())}
    if set(fixtures) != evaluator_ids:
        raise ValueError('evaluator cases and fixtures contain different case IDs')
    corpus_cases = {}
    for path in sorted((corpus / 'cases').glob('*.json')):
        corpus_case = json.loads(path.read_text())
        corpus_cases[corpus_case['id']] = corpus_case
    missing = evaluator_ids - corpus_cases.keys()
    if missing:
        raise ValueError(f'evaluator inputs reference case IDs missing from corpus: {sorted(missing)}')
    cases = {}
    for cid in sorted(evaluator_ids):
        corpus_case = corpus_cases[cid]
        criteria = json.loads((inputs / 'criteria' / f'{cid}.json').read_text())
        case = Case(cid, corpus_case, criteria, fixtures[cid]['repository'])
        if case.control != (not case.known):
            raise ValueError(f'{cid}: control flag and criteria disagree')
        cases[cid] = case
    return cases



def load_split(path: Path, cases: dict[str, Case]) -> dict[str, list[str]]:
    """Require a complete, disjoint, externally specified split."""
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError('split must be a JSON object')
    split = {}
    for name in ('train', 'val', 'test'):
        ids = data.get(name)
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
            raise ValueError(f'{name} must be a nonempty array of case IDs')
        split[name] = ids
    ids = sum(split.values(), [])
    if len(ids) != len(set(ids)) or set(ids) != set(cases):
        raise ValueError('split must contain each corpus case exactly once')
    return split



# ----------------------------------------------------------------------------------------------- denylist, validation

GENERIC_ACRONYMS = set('''HTTP HTTPS JSON YAML TOML HTML URL URI API SQL CSV XML DNS TLS SSL TCP UDP SSH CLI CPU RAM IAM
UTC UUID NULL TRUE FALSE GET POST PUT DELETE PATCH HEAD SHA MD5 ASCII UTF EOF TODO NOTE README LICENSE FIXME MUST NEVER
ALWAYS SHOULD MAY AND NOT THE FOR ANY ALL BASE DIFF PASS FAIL WARN INFO ERROR DEBUG LLM GIT GPG PGP CRUD REST RPC SDK URN
ORM CSS DOM TCP UI UX OOM EOL SLA SLO'''.split())
ALLOWED_WORDS: set[str] = set()
FILE_EXT = r'ya?ml|json|py|ts|tsx|js|jsx|go|md|tf|sh|toml|sql|ini|cfg|lock|conf|env|txt|rb|rs|java|kt|html|css'


def seed_vocabulary(seed_tree: Path) -> tuple[set[str], str]:
    text = []
    for path in sorted((seed_tree / 'skills').rglob('*')):
        if path.is_file():
            try:
                text.append(path.read_text(encoding='utf-8'))
            except (UnicodeDecodeError, OSError):
                pass
    blob = '\n'.join(text).lower()
    return set(re.findall(r'[a-z0-9_]+', blob)), blob


def codeish(token: str) -> bool:
    return '_' in token or any(ch.isdigit() for ch in token) or re.search(r'[a-z][A-Z]', token) is not None


def extract_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for match in re.finditer(r'(?<![\w/])\.?[\w\-]+(?:/[\w.\-]+)+', text):
        path = match.group(0).rstrip('.')
        terms.add(path)
        terms.add(path.rsplit('/', 1)[-1])
    for match in re.finditer(rf'(?<![\w/])[\w\-]+\.(?:{FILE_EXT})\b', text):
        terms.add(match.group(0))
    for span in re.findall(r'`([^`\n]+)`', text):
        for token in span.split():
            if len(token) >= 6 and not token.startswith('-'):
                terms.add(token.strip('.,:;()[]{}'))
    for token in re.findall(r'\b[A-Za-z_][A-Za-z0-9_]{5,}\b', text):
        if codeish(token):
            terms.add(token)
    for token in re.findall(r'\b[A-Z][A-Z0-9]{2,}\b', text):
        if token not in GENERIC_ACRONYMS and not re.fullmatch(r'[A-Z]\d+', token):
            terms.add(token)
    for token in re.findall(r'(?<=[a-z0-9,;:)\]] )[A-Z][a-z]{4,}\b', text):
        terms.add(token)
    return {t for t in terms if len(t) >= 4}


def build_denylist(cases: dict[str, Case], seed_tree: Path) -> list[str]:
    """Terms from the corpus that a skill must not contain, minus anything already in the seed skill tree."""
    corpus_text = []
    for case in cases.values():
        corpus_text.append(case.title)
        corpus_text.extend(c['criterion'] for c in case.criteria)
        for finding in case.findings.values():
            corpus_text.extend(str(finding.get(k, '')) for k in ('path', 'summary', 'how_discoverable'))
    terms = extract_terms('\n'.join(corpus_text))
    words, blob = seed_vocabulary(seed_tree)
    keep = []
    for term in sorted(terms, key=str.lower):
        low = term.lower()
        if low in ALLOWED_WORDS:
            continue
        if re.fullmatch(r'[a-z0-9_]+', low):
            in_seed = low in words
        else:
            in_seed = low in blob
        if not in_seed:
            keep.append(term)
    return keep


def find_denied(text: str, denylist: list[str]) -> list[str]:
    hits = []
    for term in denylist:
        if re.search(r'(?<![A-Za-z0-9_])' + re.escape(term) + r'(?![A-Za-z0-9_])', text, re.IGNORECASE):
            hits.append(term)
    return hits


def frontmatter(text: str) -> str | None:
    match = re.match(r'---\n(.*?)\n---(?:\n|$)', text, re.DOTALL)
    return match.group(1) if match else None


def validate_candidate(text: str, seed_text: str, denylist: list[str], component: str = 'skill') -> list[str]:
    """Frontmatter rules apply to `skill` only; the length limit is per component; the denylist applies to all."""
    problems = []
    if component == 'skill':
        seed_front = frontmatter(seed_text)
        front = frontmatter(text)
        if front is None:
            problems.append('missing YAML frontmatter')
        elif front != seed_front:
            problems.append('frontmatter changed: the lines between the --- markers (name, description) must stay exactly as in the current skill')
    limit = MAX_CHARS if component == 'skill' else GATE_MAX_CHARS
    if len(text) > limit:
        problems.append(f'too long: {len(text)} characters, limit {limit}')
    hits = find_denied(text, denylist)
    if hits:
        problems.append('contains terms taken from specific repositories/reviews, which must not appear in the text: '
                        + ', '.join(sorted(hits)[:20]))
    return problems


def validate_set(candidate: dict, seed: dict, denylist: list[str]) -> list[str]:
    out = []
    for name in candidate:
        found = validate_candidate(candidate[name], seed[name], denylist, name)
        out.extend(found if len(candidate) == 1 else [f'{name}: {p}' for p in found])
    return out


# ----------------------------------------------------------------------------------------------- scoring

class NotRunError(RuntimeError):
    pass


def parse_report(text: str) -> dict:
    def last(label, values):
        found = re.findall(rf'(?im)^[\s>*_`-]*{label}\s*:\s*[*_`\s]*({values})\b', text)
        return found[-1].lower() if found else None
    return {'risk': last('Risk', 'low|medium|high'), 'outcome': last('Outcome', 'clean|defect|unsure'),
            'verdict': last('Verdict', 'merge|block|human')}


def derive_verdict(p1_in_report: int) -> str:
    """The merge decision is read off the findings, not off the Verdict word: merge when the report labels no finding P1."""
    return 'merge' if p1_in_report == 0 else 'block'


def score_outcome(control: bool, has_p1: bool, derived: str, found: int, known: int) -> tuple[float, dict]:
    """`derived` is derive_verdict(). Control: merge 1.0, block 0.2. Defect case with a P1 (`has_p1` = a known P1 that a person
    raised or that escaped review; a case whose only P1s were raised by a bot is scored as P2-only): merge 0, else
    0.4 + 0.6*recall. P2-only defect case: merge 0.5 + 0.5*recall, else 0.4 + 0.6*recall."""
    if control:
        score = {'merge': 1.0, 'block': 0.2}[derived]
        return score, {'verdict_term': score, 'control_not_merged': int(derived != 'merge')}
    recall = found / known
    if derived == 'merge':
        score = 0.0 if has_p1 else 0.5 + 0.5 * recall
    else:
        score = 0.4 + 0.6 * recall
    return score, {'recall': recall, 'merged_p1': int(has_p1 and derived == 'merge')}


def flag_totals(records: list[dict]) -> dict:
    ran = [r for r in records if r.get('status') == 'ok']
    return {'n': len(ran), 'merged_p1': sum(r['merged_p1'] for r in ran),
            'control_not_merged': sum(r['control_not_merged'] for r in ran),
            'controls': sum(1 for r in ran if r['kind'] == 'control'),
            'p1_cases': sum(1 for r in ran if r['kind'] == 'defect' and r['has_p1'])}


def candidate_totals(run_dir: Path) -> dict:
    """Per candidate over every example run so far: mean score and the two approval counters."""
    grouped: dict[str, list[dict]] = {}
    path = Path(run_dir) / 'records.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            record = json.loads(line)
            grouped.setdefault(record['cand'], []).append(record)
    out = {}
    for cand, records in grouped.items():
        totals = flag_totals(records)
        ran = [r['score'] for r in records if r.get('status') == 'ok']
        out[cand] = {'runs': len(records), 'mean_score': sum(ran) / len(ran) if ran else None, **totals}
    return out


def aggregate(scores: list[float | None], reasons: list[str | None] | None = None) -> tuple[list[float], list[int]]:
    """Not-run examples (None) leave the batch mean unchanged: they get the mean of the ones that ran.
    More than a quarter not run raises instead of scoring."""
    missing = [i for i, s in enumerate(scores) if s is None]
    if len(missing) * 4 > len(scores):
        detail = '; '.join(f'#{i}: {reasons[i]}' for i in missing) if reasons else ''
        raise NotRunError(f'{len(missing)} of {len(scores)} examples did not run. {detail}')
    ran = [s for s in scores if s is not None]
    if not ran:
        raise NotRunError('no examples ran')
    fill = sum(ran) / len(ran)
    return [fill if s is None else s for s in scores], missing


# ----------------------------------------------------------------------------------------------- judge

def judge_prompt(report: str, criteria: list[dict]) -> str:
    ids = [c['id'] for c in criteria]
    listed = '\n'.join(f'- {c["id"]}: {c["criterion"]}' for c in criteria)
    example = '{' + ', '.join(f'"{i}": {{"pass": true, "note": "one sentence"}}' for i in ids) + ', "p1": 0}'
    return f'''You grade one code-review report against known criteria. Be strict and literal.

For each criterion decide "pass". A defect criterion (F...) passes only if the report raises recognizably the same defect at
or near the same place (file and area): the same problem described in different words is fine; a generic remark that merely
touches the topic, flags a different problem in the same file, or hedges without committing to the defect does not pass. A
control criterion (C1, "raises no P1 or merge-blocking finding") passes only if the report lists no finding it labels P1 and
does not block the merge on a substantive finding.

Also count "p1": the number of distinct findings in the report that the report itself labels P1 (merge-blocking). Count what
the report says, regardless of whether the finding is correct.

Criteria:
{listed}

Report (assessment.md):
<report>
{report}
</report>

Reply with one JSON object and nothing else, exactly this shape (one key per criterion id, plus "p1"):
{example}
'''


def parse_judge(reply: str, ids: list[str]) -> dict | None:
    text = reply.strip()
    fence = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or set(data) != set(ids) | {'p1'}:
        return None
    if not isinstance(data['p1'], int) or isinstance(data['p1'], bool) or data['p1'] < 0:
        return None
    for i in ids:
        entry = data[i]
        if (not isinstance(entry, dict) or set(entry) != {'pass', 'note'} or not isinstance(entry['pass'], bool)
                or not isinstance(entry['note'], str)):
            return None
    return data


def judge_key(report: str, criteria: list[dict], judge_model: str) -> str:
    blob = report + '\0' + json.dumps(criteria, sort_keys=True) + '\0' + JUDGE_PROMPT_VERSION + '\0' + judge_model
    return hashlib.sha256(blob.encode()).hexdigest()


def judge_report(report: str, criteria: list[dict], cache_dir: Path, model: str, neutral: Path) -> tuple[dict | None, str]:
    """Judge one report; replies are cached by report, criteria, prompt version and model."""
    key = judge_key(report, criteria, model)
    path = cache_dir / f'{key}.json'
    if path.exists():
        stored = json.loads(path.read_text())
        return stored.get('parsed'), key
    ids = [c['id'] for c in criteria]
    prompt = judge_prompt(report, criteria)
    attempts = []
    parsed = None
    for _ in range(2):
        reply = omp_text(prompt, model, neutral=neutral)
        parsed = parse_judge(reply, ids)
        attempts.append(reply)
        if parsed is not None:
            break
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f'.tmp{os.getpid()}-{threading.get_ident()}')
    tmp.write_text(json.dumps({'model': model, 'prompt_version': JUDGE_PROMPT_VERSION, 'criteria': criteria,
                               'replies': attempts, 'parsed': parsed}, indent=1) + '\n')
    tmp.replace(path)
    return parsed, key


# ----------------------------------------------------------------------------------------------- trace summary

READONLY = set('''git ls cat sed head tail grep rg find wc nl jq awk cut sort uniq diff file stat tree echo pwd printf test
true cd tr xargs basename dirname realpath which env date column fold paste comm expand tac od strings cmp'''.split())
READONLY_GIT = {'diff', 'log', 'show', 'status', 'rev-parse', 'ls-files', 'grep', 'blame', 'cat-file', 'merge-base',
                'rev-list', 'branch', 'describe', 'shortlog', 'ls-tree', 'name-rev', 'diff-tree', 'for-each-ref', 'config'}


def command_executes(command: str) -> bool:
    for segment in re.split(r'&&|\|\||[;|\n]', command):
        words = segment.strip().split()
        while words and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=\S*', words[0]):
            words = words[1:]
        if not words:
            continue
        head = os.path.basename(words[0])
        if head == 'git':
            sub = next((w for w in words[1:] if not w.startswith('-')), '')
            if sub not in READONLY_GIT:
                return True
        elif head not in READONLY:
            return True
    return False


def summarize_trace(trace: Path, changed: set[str]) -> dict:
    reads_outside, skill_reads, bash_calls, executed, subagents, tools = set(), 0, 0, 0, 0, 0
    with trace.open() as handle:
        for line in handle:
            if 'tool_execution_start' not in line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('type') != 'tool_execution_start':
                continue
            tools += 1
            name, args = event.get('toolName'), event.get('args') or {}
            if name == 'read':
                path = str(args.get('path', ''))
                if path.startswith(('skill://', 'local://', 'agent://', 'history://', 'omp://', 'help://')):
                    skill_reads += path.startswith('skill://')
                    continue
                path = re.sub(r'^.*mk-skills-eval-[^/]+/', '', path)
                path = re.sub(r':[-\d,+]+(?::raw)?$', '', path).removeprefix('./')
                if path not in changed:
                    reads_outside.add(path)
            elif name == 'bash':
                bash_calls += 1
                executed += command_executes(str(args.get('command', '')))
            elif name == 'task':
                subagents += 1
    return {'tool_calls': tools, 'files_read_outside_diff': len(reads_outside), 'skill_docs_read': skill_reads,
            'bash_calls': bash_calls, 'bash_calls_that_execute_something': executed, 'subagents_started': subagents}


# ----------------------------------------------------------------------------------------------- adapter

def cand_hash(candidate: dict) -> str:
    """A skill-only candidate hashes to its SKILL.md text; with more components all texts are hashed in name order."""
    blob = candidate['skill'] if set(candidate) == {'skill'} else '\n\x00'.join(f'{k}\n{candidate[k]}' for k in sorted(candidate))
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f'\n[... {len(text) - limit} characters cut]'


def generic_line(line: str) -> str:
    """Strip code spans, paths and file names from a quoted report line so feedback describes a kind of finding."""
    line = re.sub(r'`[^`]*`', '<code>', line)
    line = re.sub(r'[\w.@~-]*/[\w./@~-]+(?::\d+)?', '<path>', line)
    return re.sub(r'\b[\w-]+\.(?:tsx?|jsx?|py|go|sql|ya?ml|json|md|rs|java|sh|kt|rb|tf|toml)\b(?::\d+)?', '<file>', line)


def p1_lines(report: str, limit: int = 5, width: int = 200) -> list[str]:
    """Report lines that carry a P1 label, made generic and clipped; lines that only say there is no P1 are skipped."""
    negated = re.compile(r'(?i)\b(?:no|zero|0|none|without|not any)\b[^.\n]{0,40}\bP1\b|\bP1\b[^.\n]{0,20}\b(?:none|0|zero)\b')
    found = [generic_line(ln.strip()) for ln in report.splitlines() if re.search(r'\bP1\b', ln) and not negated.search(ln)]
    return [ln if len(ln) <= width else ln[:width] + '...' for ln in found[:limit]]


def tree_mismatches(tree: Path, seed_tree: Path, cand: dict) -> list[str]:
    """Differences between an evaluated tree and the tree this run would build for `cand` from `seed_tree`."""
    own = {SKILL_REL: cand['skill'], **({GATE_REL: cand['gate']} if 'gate' in cand else {})}

    def listing(root: Path, prefix: str) -> set[Path]:
        return {Path(prefix) / p.relative_to(root) for p in root.rglob('*')
                if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    old_files = listing(tree / 'skills', 'skills') | listing(tree / 'config', 'config')
    new_files = listing(seed_tree / 'skills', 'skills') | {Path('config/mode-policy.json')}
    out = [f'file set differs: {sorted(map(str, old_files ^ new_files))[:4]}'] if old_files != new_files else []
    for rel in sorted(old_files & new_files):
        expected = own[rel].encode() if rel in own else (seed_tree / rel).read_bytes()
        if (tree / rel).read_bytes() != expected:
            out.append(f'{rel} differs')
    return out


def load_reusable(reuse_dir: Path, model: str, judge_model: str, seed_tree: Path, cases: dict,
                  corpus: Path, inputs: Path, evaluator: Path) -> tuple[dict, dict]:
    """Index only completed, hash-verified evaluations from compatible prior runs."""
    notes: list[str] = []
    source = reuse_dir.resolve()
    lines = [json.loads(x) for x in (source / 'records.jsonl').read_text().splitlines()] if (source / 'records.jsonl').exists() else []
    started = (source / 'run.json').stat().st_mtime if (source / 'run.json').exists() else None
    if started is None:
        return {}, {'notes': [f'{source} has no run.json to date the run by; nothing reused'], 'dropped': len(lines)}
    for path in (*((corpus / 'cases').glob('*.json')), inputs / 'cases.json', inputs / 'workspaces.json', evaluator):
        if path.stat().st_mtime > started:
            return {}, {'notes': [f'{path} changed after that run started; nothing reused'], 'dropped': len(lines)}
    expected_prompts = {case['id']: case['prompt'] for case in json.loads((inputs / 'cases.json').read_text())}
    expected_fixtures = json.loads((inputs / 'workspaces.json').read_text())
    evaluator_bytes = evaluator.read_bytes()
    trusted: dict[str, bool] = {}
    index: dict[tuple[str, str], list[dict]] = {}
    dropped = 0
    for record in lines:
        c8, cid = record.get('cand'), record.get('case')
        if record.get('status') != 'ok' or cid not in cases:
            dropped += 1
            continue
        if c8 not in trusted:
            problems = []
            skill_path, gate_path = source / 'cands' / f'{c8}.md', source / 'cands' / f'{c8}.gate.md'
            cand = {}
            if skill_path.exists():
                cand['skill'] = skill_path.read_text()
                if gate_path.exists():
                    cand['gate'] = gate_path.read_text()
                if cand_hash(cand) != c8:
                    problems.append('stored candidate text does not hash to its name')
                tree = source / 'trees' / c8
                problems += tree_mismatches(tree, seed_tree, cand) if tree.exists() else ['evaluated tree missing']
            else:
                problems.append('candidate text missing')
            trusted[c8] = not problems
            notes.append(f'candidate {c8}: ' + ('matches this run seed tree' if not problems else 'NOT reusable: ' + '; '.join(problems)))
        if not trusted[c8] or record.get('model') != model or record.get('judge_model') != judge_model:
            dropped += 1
            continue
        out = Path(record['eval_dir'])
        report_path, result_path = out / cid / 'workspace/assessment.md', out / cid / 'result.json'
        judge_path = source / 'judge' / f'{record.get("judge_key")}.json'
        try:
            result = json.loads(result_path.read_text())
            report = report_path.read_text()
            criteria = [{'id': c['id'], 'criterion': c['criterion']} for c in cases[cid].criteria]
            stored = json.loads(judge_path.read_text())
            frozen = out / 'snapshot/evaluation'
            prompts = json.loads((frozen / 'cases.json').read_text())
            fixtures = json.loads((frozen / 'fixtures.json').read_text())
            if (not any(case['id'] == cid and case['prompt'] == expected_prompts[cid] for case in prompts)
                    or fixtures.get(cid) != expected_fixtures.get(cid)
                    or (out / 'snapshot/evaluate-skills.py').read_bytes() != evaluator_bytes):
                dropped += 1
                continue
            ok = (not result.get('timed_out') and result.get('exit_code') == 0
                  and judge_key(report, criteria, judge_model) == record['judge_key']
                  and stored.get('parsed') == record['judge']
                  and parse_judge(json.dumps(stored['parsed']), [c['id'] for c in criteria]) is not None)
        except (OSError, ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            dropped += 1
            continue
        index.setdefault((c8, cid), []).append({**{k: record.get(k) for k in ('eval_dir', 'judge_key', 'elapsed_seconds')},
                                                'source_run': str(source)})
    for runs in index.values():
        runs.sort(key=lambda r: r['eval_dir'])
    return index, {'notes': notes, 'dropped': dropped}


class SkillAdapter:
    """GEPA adapter: examples are corpus cases; candidates contain skill and optional reference text."""

    def __init__(self, *, model, judge_model, reflection_model, run_dir, inputs, corpus, evaluator, cases, denylist, seed,
                 seed_tree, parallel, timeout=1800, reuse_dir=None):
        self.model, self.judge_model, self.reflection_model = model, judge_model, reflection_model
        self.dir, self.inputs, self.corpus, self.evaluator, self.cases = Path(run_dir), Path(inputs), Path(corpus), Path(evaluator), cases
        self.denylist, self.seed, self.seed_tree, self.parallel, self.timeout = denylist, seed, Path(seed_tree), parallel, timeout
        self.components = tuple(seed)
        self.lock = threading.Lock()
        self.changed_cache: dict[str, set[str]] = {}
        self.reflections = 0
        self.reused: dict[tuple[str, str], list[dict]] = {}
        self.reuse_report: dict = {}
        if reuse_dir:
            self.reused, self.reuse_report = load_reusable(Path(reuse_dir), model, judge_model, self.seed_tree, cases,
                                                            self.corpus, self.inputs, self.evaluator)
            for line in self.reuse_report['notes']:
                log(f'reuse: {line}')
            log(f'reuse: {sum(len(v) for v in self.reused.values())} evaluated run(s) from {reuse_dir} available '
                f'({len({k[0] for k in self.reused})} candidate(s))')
        for sub in ('cands', 'trees', 'evals', 'judge', 'reflection'):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.neutral = self.dir / '_neutral'

    # -- plumbing
    def append(self, name: str, record: dict) -> None:
        with self.lock, (self.dir / name).open('a') as handle:
            handle.write(json.dumps(record, sort_keys=True) + '\n')

    def tree_for(self, cand: dict) -> Path:
        c8 = cand_hash(cand)
        with self.lock:
            tree = self.dir / 'trees' / c8
            if not tree.exists():
                tmp = tree.with_suffix('.partial')
                shutil.rmtree(tmp, ignore_errors=True)
                shutil.copytree(self.seed_tree / 'skills', tmp / 'skills', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                (tmp / 'config').mkdir()
                shutil.copyfile(self.seed_tree / 'config/mode-policy.json', tmp / 'config/mode-policy.json')
                (tmp / SKILL_REL).write_text(cand['skill'])
                if 'gate' in cand:
                    (tmp / GATE_REL).write_text(cand['gate'])
                tmp.rename(tree)
            for name, text in cand.items():
                path = self.dir / 'cands' / (f'{c8}.md' if name == 'skill' else f'{c8}.{name}.md')
                if not path.exists():
                    path.write_text(text)
        return tree

    def next_dir(self, c8: str, cid: str) -> Path:
        with self.lock:
            n = 1
            while (self.dir / 'evals' / f'{c8}-{cid}-{n}').exists():
                n += 1
            path = self.dir / 'evals' / f'{c8}-{cid}-{n}'
            path.with_suffix('.reserved').touch()
        return path

    def changed_files(self, case: Case) -> set[str]:
        with self.lock:
            if case.id in self.changed_cache:
                return self.changed_cache[case.id]
        repo = case.repository
        code, out, _err, _ = run_group(['git', '--git-dir', repo['path'], 'diff', '--name-only', repo['base'], repo['head']],
                                       timeout=60)
        files = set(out.split()) if code == 0 else set()
        with self.lock:
            self.changed_cache[case.id] = files
        return files

    def take_reused(self, c8: str, cid: str) -> dict | None:
        """Hand out each previously evaluated run at most once, so repeat evaluations of a candidate/case still run fresh."""
        with self.lock:
            runs = self.reused.get((c8, cid))
            return runs.pop(0) if runs else None

    # -- one example
    def run_case(self, cand: dict, cid: str) -> dict:
        case = self.cases[cid]
        c8 = cand_hash(cand)
        started = time.monotonic()
        record = {'case': cid, 'kind': case.kind, 'cand': c8, 'status': 'not_run', 'reason': None, 'model': self.model}
        try:
            tree = self.tree_for(cand)
            old = self.take_reused(c8, cid)
            if old:
                out = Path(old['eval_dir'])
                record['eval_dir'], record['reused_from'] = str(out), old['source_run']
                shutil.copyfile(Path(old['source_run']) / 'judge' / f'{old["judge_key"]}.json',
                                self.dir / 'judge' / f'{old["judge_key"]}.json')
                record['elapsed_seconds'] = old.get('elapsed_seconds')
            else:
                out = self.next_dir(c8, cid)
                record['eval_dir'] = str(out)
                command = ['python3', '-B', self.evaluator, '--host', 'omp', '--model', self.model, '--source', tree,
                           '--cases', self.inputs / 'cases.json', '--fixtures', self.inputs / 'workspaces.json', '--case', cid,
                           '--timeout', str(self.timeout), '--output', out]
                code, stdout, stderr, timed_out = run_group(command, timeout=self.timeout + 300)
                out.with_suffix('.log').write_text(f'exit={code} timed_out={timed_out}\n--- stdout\n{stdout}\n--- stderr\n{stderr}\n')
                result_path = out / cid / 'result.json'
                if not result_path.exists():
                    record['reason'] = f'evaluator produced no result.json (exit {code}, timed_out {timed_out})'
                    return record
                result = json.loads(result_path.read_text())
                record['elapsed_seconds'] = result.get('elapsed_seconds')
                if result.get('timed_out') or result.get('exit_code') != 0:
                    record['reason'] = f'host run failed: exit_code={result.get("exit_code")} timed_out={result.get("timed_out")}'
                    return record
            report_path = out / cid / 'workspace/assessment.md'
            if not report_path.exists():
                record['reason'] = 'no assessment.md written'
                return record
            report = report_path.read_text()
            parsed = parse_report(report)
            record['stated_verdict'] = parsed['verdict']
            record['risk'], record['outcome'] = parsed['risk'], parsed['outcome']
            judged, key = judge_report(report, [{'id': c['id'], 'criterion': c['criterion']} for c in case.criteria],
                                       self.dir / 'judge', self.judge_model, self.neutral)
            record['judge_key'] = key
            if judged is None:
                record['reason'] = 'judge reply malformed twice'
                return record
            record['judge'] = judged
            found = sum(1 for c in case.known if judged[c['id']]['pass'])
            record['found'], record['known'], record['p1_in_report'] = found, len(case.known), judged['p1']
            record['has_p1'] = case.has_p1
            record['derived'] = derive_verdict(judged['p1'])
            if case.control:
                record['control_passed'] = judged['C1']['pass']
            record['score'], record['parts'] = score_outcome(case.control, case.has_p1, record['derived'], found,
                                                              max(len(case.known), 1))
            record['merged_p1'] = record['parts'].get('merged_p1', 0)
            record['control_not_merged'] = record['parts'].get('control_not_merged', 0)
            trace = out / cid / 'trace.jsonl'
            record['trace'] = summarize_trace(trace, self.changed_files(case)) if trace.exists() else {}
            record['judge_model'] = self.judge_model
            return record
        except Exception as error:  # a driver or transport failure is a not-run example, never a score
            record['reason'] = f'driver error: {error!r}'
            log(f'{cid}: {traceback.format_exc()}')
            return record
        finally:
            record['wall_seconds'] = round(time.monotonic() - started, 1)
            self.append('records.jsonl', record)
            score = record.get('score')
            log(f'{cid} cand={c8} -> ' + (f'score={score:.3f} derived={record.get("derived")} stated={record.get("stated_verdict")} '
                                          f'p1={record.get("p1_in_report")} found={record.get("found")}/'
                                          f'{record.get("known")} ({record["wall_seconds"]}s'
                                          f'{", reused" if record.get("reused_from") else ""})' if score is not None
                                          else f'NOT RUN: {record["reason"]}'))
    def run_batch(self, cand: dict, ids: list[str]) -> list[dict]:
        return self.pmap(lambda cid: self.run_case(cand, cid), ids)

    def pmap(self, fn, items):
        executor = cf.ThreadPoolExecutor(self.parallel)
        futures = [executor.submit(fn, item) for item in items]
        try:
            return [f.result() for f in futures]
        except BaseException:
            for f in futures:
                f.cancel()
            kill_children()
            raise
        finally:
            executor.shutdown(wait=True)

    # -- GEPA protocol
    def evaluate(self, batch, candidate, capture_traces=False):
        from gepa.core.adapter import EvaluationBatch
        ids = [item['id'] for item in batch]
        c8 = cand_hash(candidate)
        problems = validate_set(candidate, self.seed, self.denylist)
        if problems:
            log(f'invalid candidate {c8}: {problems}')
            records = [{'case': cid, 'kind': self.cases[cid].kind, 'status': 'invalid', 'score': 0.0,
                        'reason': '; '.join(problems)} for cid in ids]
            self.append('batches.jsonl', {'cand': c8, 'cases': ids, 'scores': [0.0] * len(ids), 'invalid': problems})
            trajectories = [{'record': r, 'report': ''} for r in records] if capture_traces else None
            return EvaluationBatch(outputs=records, scores=[0.0] * len(ids), trajectories=trajectories)
        records = self.run_batch(candidate, ids)
        scores, missing = aggregate([r.get('score') for r in records], [r.get('reason') for r in records])
        self.append('batches.jsonl', {'cand': c8, 'cases': ids, 'scores': scores, 'not_run': missing,
                                      'mean': sum(scores) / len(scores), **{k: v for k, v in flag_totals(records).items()}})
        log(f'batch cand={c8} mean={sum(scores) / len(scores):.3f} not_run={len(missing)} flags={flag_totals(records)}')
        trajectories = None
        if capture_traces:
            trajectories = []
            for r in records:
                report = Path(r['report_path']).read_text() if r.get('report_path') else ''
                trajectories.append({'record': r, 'report': report})
        return EvaluationBatch(outputs=records, scores=scores, trajectories=trajectories)

    def feedback_for(self, record: dict, report: str) -> str:
        case = self.cases[record['case']]
        trace = record.get('trace') or {}
        lines = []
        judged = record['judge']
        stated = record.get('stated_verdict') or 'none written'
        rule = (f'(Derived verdict: any finding the report labels P1 blocks the merge; here the report labelled '
                f'{record["p1_in_report"]} finding(s) P1, so the verdict is {record["derived"]}. The Verdict line the report '
                f'wrote, "{stated}", is not scored.)')
        if case.control:
            lines.append('This change has no known defect, so the right outcome is merge: no finding labelled P1.')
            if record['derived'] == 'merge':
                lines.append(f'Correctly merged: the report labelled no finding P1. Score {record["score"]:.2f}. {rule}')
            else:
                lines.append(f'WRONGLY BLOCKED: a clean change was stopped because the report labelled a finding P1. Score '
                             f'{record["score"]:.2f} (a merged clean change scores 1.0). {rule}')
                blocking = p1_lines(report)
                lines.append('The findings the report labelled P1, quoted briefly (work out what kind of finding this was and '
                             'why it should not have been blocking; describe that kind generically in your guidance, never '
                             'copy names from these lines):')
                lines.extend(f'  - {b}' for b in blocking) if blocking else lines.append(
                    '  - (no single line carries a P1 label; the judge counted the findings from the report text)')
                lines.append(f'Judge on "no P1 / merge-blocking finding": {judged["C1"]["note"]}')
        else:
            if case.has_p1:
                lines.append(f'This change contains {len(case.known)} known defect(s), at least one a blocking-severity (P1) '
                             'defect that a person raised or that escaped review: the report must label a finding P1 so the '
                             'change does not merge.')
                if record['derived'] == 'merge':
                    lines.append(f'WRONGLY MERGED: the report labelled no finding P1, so the change merges. Score 0 whatever '
                                 f'was found (found {record["found"]}/{record["known"]}). {rule}')
                else:
                    lines.append(f'Correctly blocked. Score {record["score"]:.2f} = 0.4 + 0.6 * recall (found '
                                 f'{record["found"]}/{record["known"]}). {rule}')
            else:
                lines.append(f'This change contains {len(case.known)} known defect(s); none is a P1 that a person raised or '
                             'that escaped review (any P1 below was raised only by an automated reviewer), so it may merge, '
                             'but the review should still report the defects.')
                if record['derived'] == 'merge':
                    lines.append(f'Merged. Score {record["score"]:.2f} = 0.5 + 0.5 * recall (found '
                                 f'{record["found"]}/{record["known"]}). {rule}')
                else:
                    lines.append(f'Blocked. Score {record["score"]:.2f} = 0.4 + 0.6 * recall (found '
                                 f'{record["found"]}/{record["known"]}), never better than merging with the same findings. {rule}')
            for criterion in case.known:
                verdict = judged[criterion['id']]
                severity = criterion.get('severity')
                lines.append(f'{criterion["id"]} ({severity}): {"FOUND" if verdict["pass"] else "MISSED"}. Judge: {verdict["note"]}')
                if not verdict['pass']:
                    lines.append(f'  Defect that was missed: {criterion["criterion"]}')
                    how = case.findings.get(criterion['id'], {}).get('how_discoverable')
                    if how:
                        lines.append(f'  What a reviewer would have had to do to see it: {how}')
            if case.has_p1 and record['derived'] == 'merge':
                lines.append('A change with a serious defect must carry a P1 finding. Look at why the report did not label one: '
                             'did it miss the defect, find it but rate it lower, or hedge?')
        lines.append('What the run did: read {files_read_outside_diff} file(s) outside the diff, {skill_docs_read} skill/reference '
                     'doc(s); {bash_calls} bash call(s), {bash_calls_that_execute_something} of which executed something '
                     'beyond reading; started {subagents_started} subagent(s); {tool_calls} tool calls in total.'.format(
                         **{k: trace.get(k, 'unknown') for k in ('files_read_outside_diff', 'skill_docs_read', 'bash_calls',
                                                                 'bash_calls_that_execute_something', 'subagents_started',
                                                                 'tool_calls')}))
        return '\n'.join(lines)

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        records = []
        for traj in eval_batch.trajectories or []:
            record = traj['record']
            if record.get('status') == 'ok':
                records.append({'Inputs': {'task': TASK_TEXT, 'case_kind': record['kind']},
                                'Generated Outputs': clip(traj['report'], 3500),
                                'Feedback': self.feedback_for(record, traj['report']),
                                'score': round(record['score'], 3)})
            elif record.get('status') == 'invalid':
                records.append({'Inputs': {'task': TASK_TEXT}, 'Generated Outputs': '', 'Feedback': record['reason'], 'score': 0.0})
        return {component: records for component in components_to_update}

    def reflection_prompt(self, component: str, candidate: dict, records, problems: list[str] | None) -> str:
        shown = []
        for n, rec in enumerate(records, 1):
            shown.append(f'### Run {n} ({rec["Inputs"].get("case_kind", "")}, score {rec.get("score")})\n'
                         f'Feedback:\n{rec["Feedback"]}\n\nThe reviewer\'s report:\n<report>\n{rec["Generated Outputs"]}\n</report>')
        retry = ''
        if problems:
            retry = ('\n## Your previous attempt was rejected\nProblems: ' + '; '.join(problems) +
                     '\nFix exactly these problems and return the full text again.\n')
        scoring = ('The reviewer writes a report listing findings with a severity: P1 blocks the merge, P2 should be fixed, P3 is '
                   'minor. The merge decision is DERIVED from those labels, not from any Verdict word the reviewer writes: if the '
                   'report labels at least one finding P1 the change is blocked, otherwise it merges. A clean change that gets a '
                   'P1 label is a wrongly blocked change; a change with a serious defect that gets no P1 label is a wrongly '
                   'merged change. Scores on real changes: clean change merged 1.0, blocked 0.2. Change with a known blocking '
                   'defect (P1): merged 0 whatever else was found; blocked 0.4 + 0.6 * the share of the known defects the '
                   'report raised. Change whose known defects are lesser: merged 0.5 + 0.5 * that share (such a change may '
                   'merge, but the defects should still be reported); blocked 0.4 + 0.6 * that share. So a reviewer should '
                   'label P1 exactly the findings that on their own justify stopping a merge, and should label such a '
                   'finding P1 whenever it finds one; severity labels are the decision.')
        common_rules = ('- Write guidance that applies to any repository. Never name a product, vendor, file, path, or identifier '
                        'from the evidence; describe kinds of behaviour and kinds of defect generically.\n'
                        '- Prefer changing what the reviewer does (what to read beyond the diff, what to run or construct to test a '
                        'claim, how to decide whether a finding deserves the P1 label) over adding checklists of specific bugs.\n'
                        '- Keep guidance that the evidence does not contradict. Do not add rules that make the reviewer label a '
                        'finding P1 when it would not justify stopping a clean change, and do not push it to rate a real serious '
                        'defect lower so that the change can merge.')
        if component == 'skill':
            gate = candidate.get('gate')
            gate_block = ('\n## Merge gate reference (read-only here; it is improved separately and the skill links to it)\n'
                          f'<reference>\n{gate}\n</reference>\n') if gate is not None else ''
            return f'''You are improving a skill file (SKILL.md) that an AI coding agent loads when it reviews a code change (a git
diff between BASE and HEAD in a repository it has never seen) and must decide whether it can merge without a human. {scoring}

## Current skill
<skill>
{candidate['skill']}
</skill>
{gate_block}
## Evidence from review runs that used this skill
{chr(10).join(shown)}
{retry}
## What to write
Study what the runs did and where they lost score, find the behavioural pattern behind it, and rewrite the skill to change
that behaviour.

Rules:
- Return the complete new SKILL.md inside one <skill>...</skill> block. Anything before the block is optional short reasoning.
- Keep the YAML frontmatter (the lines between the --- markers) byte-for-byte identical to the current skill.
- Keep the whole file under {MAX_CHARS} characters. The current text uses {len(candidate['skill'])}, leaving at most {MAX_CHARS - len(candidate['skill'])} characters for net additions. Replace or remove text rather than exceeding that budget. Keep the existing reference paths.
{common_rules}
'''
        return f'''You are improving a reference file at `{GATE_REL}` that a skill links to when an AI coding agent reviews a change
(a git diff between BASE and HEAD in a repository it has never seen) and decides whether it can merge without a human. The
reference shapes risk assessment, verification, and severity decisions. {scoring}

## Skill that links to the reference (read-only here; it is improved separately)
<reference>
{candidate['skill']}
</reference>

## Current reference
<gate>
{candidate['gate']}
</gate>

## Evidence from evaluation runs
{chr(10).join(shown)}
{retry}
## What to write
Study the observed behavior and score losses, identify the underlying behavioral pattern, and rewrite the reference to change
that behavior.

Rules:
- Return the complete new file inside one <gate>...</gate> block. Anything before the block is optional brief reasoning.
- Keep the whole file under {GATE_MAX_CHARS} characters and self-contained. The current text uses {len(candidate['gate'])}, leaving at most {GATE_MAX_CHARS - len(candidate['gate'])} characters for net additions. Replace or remove text rather than exceeding that budget.
{common_rules}
'''

    def propose_new_texts(self, candidate, reflective_dataset, components_to_update):
        out = {}
        for component in components_to_update:
            records = reflective_dataset.get(component) or []
            if not records:
                raise ValueError('no usable examples in the reflective dataset')
            problems, text = None, None
            for attempt in (1, 2):
                prompt = self.reflection_prompt(component, candidate, records, problems)
                with self.lock:
                    self.reflections += 1
                    n = self.reflections
                base = self.dir / 'reflection' / f'{int(time.time())}-{n:03d}-{component}-a{attempt}'
                base.with_suffix('.prompt.md').write_text(prompt)
                reply = omp_text(prompt, self.reflection_model, neutral=self.neutral)
                blocks = re.findall(rf'<{component}>\n?(.*?)\n?</{component}>', reply, re.DOTALL)
                if not blocks:
                    problems = [f'reply had no <{component}>...</{component}> block']
                    continue
                text = blocks[-1].strip('\n') + '\n'
                problems = validate_candidate(text, self.seed[component], self.denylist, component)
                self.append('proposals.jsonl', {'parent': cand_hash(candidate), 'component': component, 'attempt': attempt,
                                                'chars': len(text), 'problems': problems,
                                                'text_hash': cand_hash({**candidate, component: text}),
                                                'reply_file': str(base) + '.reply.md'})
                if not problems:
                    break
            if problems:
                raise ValueError(f'reflection produced no valid {component}: ' + '; '.join(problems))
            out[component] = text
        return out


# ----------------------------------------------------------------------------------------------- modes

def check_parallel(model: str, parallel: int) -> None:
    if parallel < 1:
        raise SystemExit('--parallel must be a positive integer')


def parse_components(value: str) -> tuple[str, ...]:
    if value not in COMPONENT_SETS:
        raise SystemExit(f'--components must be one of {", ".join(COMPONENT_SETS)}, got {value!r}')
    return COMPONENT_SETS[value]


def make_adapter(args, run_dir: Path):
    components = parse_components(args.components)
    seed_tree = Path(args.seed_tree).resolve()
    for need in (SKILL_REL, Path('config/mode-policy.json')):
        if not (seed_tree / need).is_file():
            raise SystemExit(f'seed tree {seed_tree} has no {need}')
    seed = {'skill': (seed_tree / SKILL_REL).read_text()}
    if 'gate' in components:
        if not (seed_tree / GATE_REL).is_file():
            raise SystemExit(f'--components skill,gate needs {seed_tree / GATE_REL}, which does not exist')
        seed['gate'] = (seed_tree / GATE_REL).read_text()
    cases = load_cases(args.corpus, args.inputs)
    split = load_split(args.split, cases)
    denylist = build_denylist(cases, seed_tree)
    problems = validate_set(seed, seed, denylist)
    if problems:
        raise SystemExit(f'seed fails its own validation: {problems}')
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / 'denylist.json').write_text(json.dumps(denylist, indent=1) + '\n')
    run = {'model': args.model, 'judge_model': args.judge_model, 'reflection_model': args.reflection_model,
           'seed_tree': str(seed_tree), 'corpus': str(Path(args.corpus).resolve()), 'inputs': str(Path(args.inputs).resolve()),
           'split': str(Path(args.split).resolve()), 'seed': args.seed}
    (run_dir / 'run.json').write_text(json.dumps(run, indent=1) + '\n')
    adapter = SkillAdapter(model=args.model, judge_model=args.judge_model, reflection_model=args.reflection_model,
                           run_dir=run_dir, inputs=args.inputs, corpus=args.corpus, evaluator=EVALUATOR, cases=cases,
                           denylist=denylist, seed=seed, seed_tree=seed_tree, parallel=args.parallel, timeout=args.timeout,
                           reuse_dir=args.reuse_evals)
    return adapter, cases, split, seed

def run_optimize(args, run_dir: Path) -> None:
    import gepa
    adapter, cases, split, seed = make_adapter(args, run_dir)
    data = lambda ids: [{'id': cid} for cid in ids]  # noqa: E731
    log(f'gepa {getattr(gepa, "__version__", "?")} model={args.model} components={",".join(seed)} seed_tree={adapter.seed_tree} '
        f'train={len(split["train"])} val={len(split["val"])} '
        f'budget={args.max_metric_calls} minibatch={args.minibatch} parallel={args.parallel}')
    result = gepa.optimize(seed_candidate=dict(seed), trainset=data(split['train']), valset=data(split['val']),
                           adapter=adapter, reflection_minibatch_size=args.minibatch, max_metric_calls=args.max_metric_calls,
                           run_dir=str(run_dir / 'gepa'), seed=args.seed, candidate_selection_strategy='pareto',
                           use_merge=False, skip_perfect_score=True, display_progress_bar=False, raise_on_exception=True)
    finish(result, run_dir, adapter)


def finish(result, run_dir: Path, adapter) -> None:
    candidates = [{name: c[name] for name in adapter.components} for c in result.candidates]
    for cand in candidates:
        adapter.tree_for(cand)
    summary = {'best_idx': result.best_idx, 'val_aggregate_scores': result.val_aggregate_scores, 'parents': result.parents,
               'components': list(adapter.components),
               'candidate_hashes': [cand_hash(c) for c in candidates], 'total_metric_calls': result.total_metric_calls,
               'discovery_eval_counts': result.discovery_eval_counts, 'per_candidate_totals': candidate_totals(run_dir)}
    (run_dir / 'result.json').write_text(json.dumps(summary, indent=1) + '\n')
    for name in adapter.components:
        (run_dir / f'best_{name}.md').write_text(candidates[result.best_idx][name])
        (run_dir / f'seed_{name}.md').write_text(candidates[0][name])
    for h, t in summary['per_candidate_totals'].items():
        log(f'candidate {h}: {t}')
    log(f'done: best candidate #{result.best_idx} ({cand_hash(candidates[result.best_idx])}) val={result.val_aggregate_scores}')




def test_metrics(records: list[dict], cases: dict[str, Case]) -> dict:
    ran = [r for r in records if r.get('status') == 'ok']
    defects = [r for r in ran if r['kind'] == 'defect']
    controls = [r for r in ran if r['kind'] == 'control']
    return {'mean': sum(r['score'] for r in ran) / len(ran) if ran else None, 'n_ran': len(ran),
            'n_not_run': len(records) - len(ran),
            'found': sum(r['found'] for r in defects), 'known': sum(r['known'] for r in defects),
            'p1_cases': sum(1 for r in defects if cases[r['case']].has_p1),
            'p1_cases_merged': sum(1 for r in defects if cases[r['case']].has_p1 and r['derived'] == 'merge'),
            'controls': len(controls), 'controls_merged': sum(1 for r in controls if r['derived'] == 'merge'),
            'controls_blocked': sum(1 for r in controls if r['derived'] == 'block')}


def run_test_report(args, run_dir: Path) -> None:
    adapter, cases, split, seed = make_adapter(args, run_dir)
    if args.candidate:
        best = {'skill': Path(args.candidate).read_text()}
        if 'gate' in seed:
            best['gate'] = Path(args.candidate_gate).read_text() if args.candidate_gate else seed['gate']
        best_label = f'file {args.candidate}' + (f' + {args.candidate_gate}' if args.candidate_gate else '')
    elif all((run_dir / f'best_{name}.md').exists() for name in seed):
        best = {name: (run_dir / f'best_{name}.md').read_text() for name in seed}
        best_label = 'best_*.md (best validation score)'
    else:
        from gepa.core.result import GEPAResult
        from gepa.core.state import GEPAState
        result = GEPAResult.from_state(GEPAState.load(str(run_dir / 'gepa')))
        best = {name: result.candidates[result.best_idx][name] for name in seed}
        best_label = f'GEPA state candidate #{result.best_idx}'
    problems = validate_set(best, seed, adapter.denylist)
    if problems:
        raise SystemExit(f'best candidate fails validation: {problems}')
    arms = {'seed': dict(seed), 'best': best}
    test_ids = split['test']
    jobs = [(arm, rep, cid) for rep in range(1, args.repeats + 1) for cid in test_ids for arm in arms]
    log(f'test report: {len(jobs)} runs ({len(arms)} arms x {args.repeats} repeats x {len(test_ids)} cases), parallel {args.parallel}')
    records = adapter.pmap(lambda job: {**adapter.run_case(arms[job[0]], job[2]), 'arm': job[0], 'rep': job[1]}, jobs)
    test_dir = run_dir / 'test'
    test_dir.mkdir(exist_ok=True)
    (test_dir / 'records.json').write_text(json.dumps(records, indent=1) + '\n')
    (run_dir / 'report.md').write_text(render_report(args, cases, arms, best_label, records))
    log(f'report written to {run_dir / "report.md"}')


def render_report(args, cases, arms, best_label, records) -> str:
    def sel(arm, rep=None):
        return [r for r in records if r['arm'] == arm and (rep is None or r['rep'] == rep)]
    repeats = sorted({r['rep'] for r in records})
    lines = [f'# Review-guidance optimization report: `{args.model}`', '',
             f'Test split: {len({r["case"] for r in records})} cases (never seen by the optimizer), {len(repeats)} runs per case per arm. '
             f'Seed = `{cand_hash(arms["seed"])}`, best = `{cand_hash(arms["best"])}` from {best_label}. '
             f'Judge `{args.judge_model}`. Not-run examples are excluded from means and listed.', '',
             '## Summary', '',
             '| arm | run | mean score | found / known | P1 cases merged | controls merged | controls blocked | not run |',
             '|---|---|---|---|---|---|---|---|']
    means: dict[str, list[float]] = {}
    for arm in arms:
        for rep in repeats:
            m = test_metrics(sel(arm, rep), cases)
            means.setdefault(arm, []).append(m['mean'])
            mean = 'n/a' if m['mean'] is None else f'{m["mean"]:.3f}'
            lines.append(f'| {arm} | {rep} | {mean} | {m["found"]}/{m["known"]} | {m["p1_cases_merged"]}/{m["p1_cases"]} | '
                         f'{m["controls_merged"]}/{m["controls"]} | {m["controls_blocked"]} | {m["n_not_run"]} |')
        m = test_metrics(sel(arm), cases)
        mean = 'n/a' if m['mean'] is None else f'{m["mean"]:.3f}'
        lines.append(f'| **{arm}** | all | **{mean}** | {m["found"]}/{m["known"]} | {m["p1_cases_merged"]}/{m["p1_cases"]} | '
                     f'{m["controls_merged"]}/{m["controls"]} | {m["controls_blocked"]} | {m["n_not_run"]} |')
    lines.append('')
    seed_all, best_all = test_metrics(sel('seed'), cases)['mean'], test_metrics(sel('best'), cases)['mean']
    seed_runs = [v for v in means['seed'] if v is not None]
    spread = max(seed_runs) - min(seed_runs) if len(seed_runs) > 1 else None
    lines.append('## Verdict')
    lines.append('')
    if seed_all is None or best_all is None or spread is None:
        lines.append('Not enough completed runs to compare.')
    else:
        delta = best_all - seed_all
        flips = sum(1 for cid in {r['case'] for r in records}
                    if len({round(r['score'], 3) for r in sel('seed') if r['case'] == cid and r.get('status') == 'ok'}) > 1)
        lines.append(f'Best minus seed: **{delta:+.3f}** mean score. Run-to-run spread of the seed (difference between its two '
                     f'run means): **{spread:.3f}**; {flips} of {len({r["case"] for r in records})} cases scored differently '
                     f'between the two seed runs.')
        lines.append('')
        if abs(delta) <= spread:
            lines.append('**The difference is inside the run-to-run spread: no demonstrated gain** (or loss) from the evolved skill.')
        else:
            lines.append(f'The difference is larger than the seed run-to-run spread ({abs(delta):.3f} > {spread:.3f}), with only '
                         f'{len(seed_runs)} runs per arm: treat as suggestive, not established.')
    lines += ['', '## Per case', '',
              '| case | kind | known | ' + ' | '.join(f'{arm} r{rep}' for arm in arms for rep in repeats) + ' |',
              '|---|---|---|' + '---|' * (len(arms) * len(repeats))]
    for cid in sorted({r['case'] for r in records}):
        case = cases[cid]
        known = ','.join(c.get('severity') or '' for c in case.known) or '-'
        cells = []
        for arm in arms:
            for rep in repeats:
                run = next((r for r in records if r['arm'] == arm and r['rep'] == rep and r['case'] == cid), None)
                if run is None or run.get('status') != 'ok':
                    cells.append('not run')
                elif case.control:
                    cells.append(f'{run["score"]:.2f} {run["derived"]}')
                else:
                    cells.append(f'{run["score"]:.2f} {run["found"]}/{run["known"]} {run["derived"]}')
        lines.append(f'| {cid} | {case.kind} | {known} | ' + ' | '.join(cells) + ' |')
    not_run = [r for r in records if r.get('status') != 'ok']
    if not_run:
        lines += ['', '## Not run', ''] + [f'- {r["arm"]} r{r["rep"]} {r["case"]}: {r["reason"]}' for r in not_run]
    return '\n'.join(lines) + '\n'


def outside_checkout(path: Path, name: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return resolved
    raise SystemExit(f'--{name} must resolve outside this checkout because it contains private corpus material: {resolved}')


def main() -> int:
    global _log_file, SKILL_REL, GATE_REL
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--corpus', type=Path, required=True, help='external review-corpus root containing cases/*.json')
    parser.add_argument('--inputs', type=Path, required=True, help='external evaluator build directory')
    parser.add_argument('--split', type=Path, required=True, help='JSON object with disjoint train, val and test case ID arrays')
    parser.add_argument('--seed-tree', type=Path, required=True, help='skill tree to evolve')
    parser.add_argument('--output', type=Path, required=True, help='external run output directory')
    parser.add_argument('--skill-path', type=Path, default=SKILL_REL, help='skill file path relative to seed tree')
    parser.add_argument('--gate-path', type=Path, default=GATE_REL, help='gate reference path relative to seed tree')
    parser.add_argument('--model', required=True, help='model under optimization')
    parser.add_argument('--judge-model', required=True, help='model used to score reports')
    parser.add_argument('--reflection-model', required=True, help='model used to propose guidance revisions')
    parser.add_argument('--max-metric-calls', type=int, default=400)
    parser.add_argument('--test-report', action='store_true', help='evaluate seed vs best candidate on held-out test split')
    parser.add_argument('--parallel', type=int, default=4)
    parser.add_argument('--minibatch', type=int, default=6)
    parser.add_argument('--timeout', type=float, default=1800, help='per-run host timeout in seconds')
    parser.add_argument('--seed', type=int, default=0, help='GEPA random seed')
    parser.add_argument('--repeats', type=int, default=2, help='runs per case per arm in --test-report')
    parser.add_argument('--candidate', type=Path, help='--test-report: skill candidate file')
    parser.add_argument('--candidate-gate', type=Path, help='--test-report: optional gate candidate file')
    parser.add_argument('--components', default='skill', choices=list(COMPONENT_SETS), metavar='skill|skill,gate')
    parser.add_argument('--reuse-evals', type=Path, metavar='RUN_DIR', help='reuse verified compatible prior evaluations')
    args = parser.parse_args()
    check_parallel(args.model, args.parallel)
    args.corpus = outside_checkout(args.corpus, 'corpus')
    args.inputs = outside_checkout(args.inputs, 'inputs')
    args.split = outside_checkout(args.split, 'split')
    args.seed_tree = args.seed_tree.expanduser().resolve()
    if args.skill_path.is_absolute() or args.gate_path.is_absolute() or '..' in args.skill_path.parts or '..' in args.gate_path.parts:
        raise SystemExit('--skill-path and --gate-path must be relative paths within the seed tree')
    SKILL_REL, GATE_REL = args.skill_path, args.gate_path
    run_dir = outside_checkout(args.output, 'output')
    if args.reuse_evals:
        args.reuse_evals = outside_checkout(args.reuse_evals, 'reuse-evals')
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    run_dir.mkdir(parents=True, exist_ok=True)
    _log_file = run_dir / 'driver.log'
    if args.test_report:
        run_test_report(args, run_dir)
    else:
        run_optimize(args, run_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
