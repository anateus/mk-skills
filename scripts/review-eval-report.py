#!/usr/bin/env python3
"""Create blind review packets and tally graded results.

The runs manifest is a JSON array of {model, arm, case, path, repetition}; path names one
case output directory from evaluate-skills.py, relative to the manifest or
absolute. Include expected runs even when their directories do not exist.
Repetition is an optional positive integer, defaulting to 1. Criteria are the JSON files
created by review-corpus.py build. The private key records run-to-arm mappings and must
not be sent to graders. Grades live at GRADES/model/*.json, with each file
mapping case -> blind label -> {criterion id: {pass: bool}, p1: int, p2: int}.
Wilson intervals use distinct cases; a case succeeds only if every expected repetition
is graded and merged. Missing/incomplete cases are not counted as clean; pooled trial
counts are shown separately without intervals.

Example:
  review-eval-report.py packets --runs runs.json --criteria criteria --out packets --key key.json --seed 42
  review-eval-report.py tally --key key.json --grades grades --cases cases --out summary.json --p2-cutoff 0 --p2-cutoff 2

Outputs can contain private case data; keep them outside the public checkout.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')


def private(path):
    path = Path(path).expanduser().resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Output must be outside the checkout: ' + str(path))
    return path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value) or value in ('.', '..'):
        raise ValueError('Invalid model, arm, or case name: ' + repr(value))
    return value


def effort(run):
    result_path = run / 'result.json'
    if not result_path.is_file():
        return {'status': 'missing_result'}
    result = load(result_path)
    elapsed = result.get('elapsed_seconds')
    data = {'status': 'failed' if result.get('exit_code') != 0 or result.get('timed_out') is not False
            else 'ok', 'seconds': elapsed, 'trace_present': (run / 'trace.jsonl').is_file(),
            'tasks': 0, 'bash': 0, 'reads': 0, 'turns': 0, 'cost': 0.0}
    if data['trace_present']:
        with (run / 'trace.jsonl').open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get('type') == 'tool_execution_start':
                    tool, args = event.get('toolName'), event.get('args') or {}
                    if tool == 'task':
                        data['tasks'] += len(args.get('tasks') or [None])
                    elif tool in ('bash', 'read'):
                        data['bash' if tool == 'bash' else 'reads'] += 1
                elif event.get('type') == 'message_end':
                    message = event.get('message') or {}
                    if message.get('role') == 'assistant':
                        data['turns'] += 1
                        data['cost'] += ((message.get('usage') or {}).get('cost') or {}).get('total') or 0
    if data['status'] == 'ok':
        report_path = run / 'workspace' / 'assessment.md'
        if not report_path.is_file():
            data['status'] = 'missing_report'
        else:
            text = report_path.read_text(encoding='utf-8', errors='replace')
            if not text.strip():
                data['status'] = 'missing_report'
            else:
                verdicts = re.findall(r'(?im)^\W*verdict\W+(merge|block|human)', text)
                risks = re.findall(r'(?im)^\W*risk\W+(low|medium|high)', text)
                data['verdict'] = verdicts[-1].lower() if verdicts else None
                data['risk'] = risks[-1].lower() if risks else None
    return data


def packets(args):
    out, key_path = private(args.out), private(args.key)
    if out == key_path or out in key_path.parents or key_path in out.parents:
        raise ValueError('Key must be outside the packet directory')
    if out.exists() or key_path.exists():
        raise ValueError('Packet directory and key must not already exist')
    manifest_path = Path(args.runs).resolve()
    manifest = load(manifest_path)
    if not isinstance(manifest, list) or not manifest:
        raise ValueError('Runs manifest must be a nonempty array')
    groups, seen = defaultdict(list), set()
    for row in manifest:
        model, arm, case = (name(row[k]) for k in ('model', 'arm', 'case'))
        repetition = row.get('repetition', 1)
        if not valid_count(repetition) or repetition < 1:
            raise ValueError('Repetition must be a positive integer')
        identity = (model, case, arm, repetition)
        if identity in seen:
            raise ValueError('Duplicate run: ' + '/'.join(map(str, identity)))
        seen.add(identity)
        run = Path(row['path']).expanduser()
        run = (manifest_path.parent / run).resolve()
        groups[model, case].append((arm, repetition, run))
    rng, entries = random.Random(args.seed), []
    # Validate all inputs before writing packets.
    criteria = {}
    for model, case in sorted(groups):
        raw = load(Path(args.criteria) / (case + '.json'))
        criteria[model, case] = [{'id': c['id'], 'criterion': c['criterion']} for c in raw]
    for model, case in sorted(groups):
        items = sorted(groups[model, case])
        rng.shuffle(items)
        dest = out / model / case
        save(dest / 'criteria.json', criteria[model, case])
        for index, (arm, repetition, run) in enumerate(items, 1):
            label = 'r%d' % index
            metrics = effort(run)
            target = dest / label / 'assessment.md'
            target.parent.mkdir(parents=True, exist_ok=True)
            if metrics['status'] == 'ok':
                shutil.copyfile(run / 'workspace' / 'assessment.md', target)
            else:
                target.write_text('[No usable assessment was produced.]\n', encoding='utf-8')
            entries.append({'model': model, 'case': case, 'arm': arm, 'repetition': repetition,
                            'label': label, 'effort': metrics})
    save(key_path, {'version': 1, 'runs': entries})


def interval(success, total):
    """Two-sided 95% Wilson score interval for a binomial proportion."""
    if not total:
        return None
    z = 1.959963984540054
    p = success / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def ratio(success, total):
    return {'count': success, 'total': total, 'rate': success / total if total else None}


def proportion(success, total):
    return {**ratio(success, total), 'wilson_95': interval(success, total)}


def grades_for(root, model):
    grades = {}
    for path in sorted((root / model).glob('*.json')):
        for case, runs in load(path).items():
            for label, grade in runs.items():
                identity = (case, label)
                if identity in grades:
                    raise ValueError('Duplicate grade for ' + model + '/' + case + '/' + label)
                grades[identity] = grade
    return grades


def valid_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def tally(args):
    output = private(args.out)
    if output.exists():
        raise ValueError('Output already exists: ' + str(output))
    key = load(args.key)
    if key.get('version') != 1 or not isinstance(key.get('runs'), list):
        raise ValueError('Unsupported packet key')
    cutoffs = sorted(set(args.p2_cutoff))
    if any(n < 0 for n in cutoffs):
        raise ValueError('P2 cutoffs must be nonnegative')
    cache, cases, groups, identities = {}, {}, defaultdict(list), set()
    for run in key['runs']:
        model, case, arm, label = (name(run[k]) for k in ('model', 'case', 'arm', 'label'))
        identity = (model, case, label)
        if identity in identities:
            raise ValueError('Duplicate packet key: ' + '/'.join(identity))
        identities.add(identity)
        if model not in cache:
            cache[model] = grades_for(Path(args.grades), model)
        if case not in cases:
            cases[case] = load(Path(args.cases) / (case + '.json'))
        groups[model, arm].append((run, cases[case], cache[model].get((case, label))))
    report = {'version': 1, 'p2_cutoffs': cutoffs, 'groups': {}}
    for (model, arm), rows in sorted(groups.items()):
        statuses = defaultdict(int)
        effort_rows, eligible = [], []
        case_repetitions = defaultdict(int)
        for run, case, _ in rows:
            case_repetitions[run['case']] += 1
        found = known = 0
        by_source = defaultdict(lambda: [0, 0])
        for run, case, grade in rows:
            metrics = run['effort']
            status = metrics['status']
            statuses[status] += 1
            if status != 'missing_result':
                effort_rows.append((metrics, case))
            if status != 'ok':
                continue
            if not isinstance(grade, dict):
                statuses['missing_grade'] += 1
                continue
            findings = case.get('findings', [])
            required_criteria = [('F%d' % (i + 1), finding) for i, finding in enumerate(findings)]
            if case.get('control') is True:
                required_criteria.append(('C1', None))
            if (not valid_count(grade.get('p1')) or not valid_count(grade.get('p2')) or
                any(not isinstance(grade.get(k), dict) or type(grade[k].get('pass')) is not bool
                    for k, _ in required_criteria)):
                statuses['incomplete_grade'] += 1
                continue
            criteria = [(k, finding) for k, finding in required_criteria if finding is not None]
            for criterion, finding in criteria:
                passed = int(grade[criterion]['pass'])
                known += 1
                found += passed
                source = finding.get('source', 'unknown')
                by_source[source][0] += passed
                by_source[source][1] += 1
            serious = any(f.get('severity') == 'P1' and
                          (f.get('source') == 'escaped' or not f.get('reviewer_is_bot', False))
                          for f in findings)
            eligible.append((run['case'], case, grade, serious))
        def mean(values):
            return sum(values) / len(values) if values else None
        seconds = [m['seconds'] for m, _ in effort_rows if isinstance(m.get('seconds'), (int, float))]
        small = [m['seconds'] for m, c in effort_rows if isinstance(c.get('changed_lines'), (int, float))
                 and c['changed_lines'] < 200 and isinstance(m.get('seconds'), (int, float))]
        traced = [m for m, _ in effort_rows if m.get('trace_present')]
        verdicts = defaultdict(int)
        risks = defaultdict(int)
        for metrics, _ in effort_rows:
            verdicts[metrics.get('verdict') or 'none'] += 1
            risks[metrics.get('risk') or 'none'] += 1
        repetition_counts = defaultdict(int)
        for count in case_repetitions.values():
            repetition_counts[str(count)] += 1
        result = {'expected': len(rows), 'status': dict(statuses), 'graded': len(eligible),
                  'repetitions': {'distinct_cases': len(case_repetitions),
                                  'per_case': dict(repetition_counts)},
                  'recall': ratio(found, known),
                  'recall_by_source': {s: ratio(*counts) for s, counts in sorted(by_source.items())},
                  'effort': {'runs': len(effort_rows), 'seconds_n': len(seconds), 'mean_seconds': mean(seconds),
                             'small_runs': len(small), 'small_mean_seconds': mean(small),
                             'traced_runs': len(traced), 'total_cost': sum(m['cost'] for m in traced),
                             'mean_tasks': mean([m['tasks'] for m in traced]),
                             'mean_reads': mean([m['reads'] for m in traced]),
                             'mean_bash': mean([m['bash'] for m in traced]),
                             'mean_turns': mean([m['turns'] for m in traced])}, 'cutoffs': {}}
        for cutoff in cutoffs:
            def cutoff_result(predicate):
                by_case = defaultdict(list)
                for case_id, case, grade, serious in eligible:
                    if predicate(case, serious):
                        by_case[case_id].append(grade)
                case_success = sum(
                    len(grades) == case_repetitions[case_id] and all(merges(g) for g in grades)
                    for case_id, grades in by_case.items())
                trial_total = sum(map(len, by_case.values()))
                trial_success = sum(merges(g) for grades in by_case.values() for g in grades)
                return {'case_all_repetitions_merged': proportion(case_success, len(by_case)),
                        'trial_merged': {'count': trial_success, 'total': trial_total,
                                         'rate': trial_success / trial_total if trial_total else None}}
            merges = lambda g: g['p1'] == 0 and g['p2'] <= cutoff
            result['cutoffs'][str(cutoff)] = {
                'controls_merged': cutoff_result(lambda c, _: c.get('control') is True),
                'serious_cases_merged': cutoff_result(lambda c, serious: serious),
                'other_defects_merged': cutoff_result(
                    lambda c, serious: c.get('control') is False and not serious)}
        report['groups'].setdefault(model, {})[arm] = result
    save(output, report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('packets', help='Build blinded packets and separate private key')
    for flag in ('runs', 'criteria', 'out', 'key'):
        p.add_argument('--' + flag, required=True)
    p.add_argument('--seed', type=int, required=True)
    p.set_defaults(func=packets)
    t = subs.add_parser('tally', help='Aggregate grades and effort by model and arm')
    for flag in ('key', 'grades', 'cases', 'out'):
        t.add_argument('--' + flag, required=True)
    t.add_argument('--p2-cutoff', type=int, action='append', required=True,
                   help='Merge only with no P1 and at most this many P2 findings; repeat for alternatives')
    t.set_defaults(func=tally)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('review-eval-report: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
