#!/usr/bin/env python3
"""Tiered, read-only reports over bundled Vale rules. Python 3.9+, Vale 3.20+."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys


SKILL = Path(__file__).resolve().parents[1]


def rule_name(value, rules):
    name = value if value.startswith('Humanizer.') else 'Humanizer.' + value
    if name not in rules:
        raise ValueError('Unknown rule: {}. Choose: {}'.format(value, ', '.join(rules)))
    return name


def explain(name, rules):
    section = rules[name]['section']
    catalog = (SKILL / 'references/signs-of-ai-writing.md').read_text(encoding='utf-8')
    match = re.search(r'^### {}\. .*?(?=^## |^### |\Z)'.format(section),
                      catalog, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError('Catalog section {} is missing'.format(section))
    return match.group().strip()


def scan(source, extension, vale):
    # stdin avoids Vale interpreting a missing path as literal prose. Explicit
    # config and --no-global keep the report independent of a host's house style.
    command = [vale, '--no-global', '--config', str(SKILL / '.vale.ini'),
               '--output=JSON', '--minAlertLevel=suggestion', '--no-exit',
               '--ext=' + extension]
    result = subprocess.run(command, input=source, text=True, encoding='utf-8',
                            capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('Vale failed ({}): {}'.format(
            result.returncode, (result.stderr or result.stdout).strip()[:2000]))
    try:
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise ValueError('expected an object')
        alerts = []
        for records in payload.values():
            if not isinstance(records, list):
                raise ValueError('expected alert lists')
            for item in records:
                if (not isinstance(item, dict)
                        or not isinstance(item.get('Check'), str)
                        or item.get('Severity') not in ('suggestion', 'warning', 'error')
                        or not isinstance(item.get('Match'), str)
                        or not isinstance(item.get('Line'), int)
                        or not isinstance(item.get('Span'), list)
                        or len(item['Span']) != 2
                        or not all(isinstance(n, int) for n in item['Span'])):
                    raise ValueError('invalid alert')
                alerts.append(item)
        return alerts
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid Vale JSON: {}'.format(error)) from error


def report(alerts, source_name, details, limit, rules):
    alerts.sort(key=lambda a: (a['Line'], a['Span'][0], a['Check']))
    unknown = {a['Check'] for a in alerts} - rules.keys()
    if unknown:
        raise ValueError('Unindexed Vale rules: ' + ', '.join(sorted(unknown)))
    counts = dict(sorted(Counter(a['Check'] for a in alerts).items()))
    strong = dict(sorted(Counter(a['Check'] for a in alerts
                                 if a['Severity'] != 'suggestion').items()))
    weak = dict(sorted(Counter(a['Check'] for a in alerts
                               if a['Severity'] == 'suggestion').items()))
    selected = [a for a in alerts if details == 'all' or a['Check'] == details
                or (details is None and a['Severity'] != 'suggestion')]
    findings = [{'rule': a['Check'], 'line': a['Line'], 'columns': a['Span'],
                 'match': a['Match'][:240], 'match_truncated': len(a['Match']) > 240,
                 'section': rules[a['Check']]['section']} for a in selected[:limit]]
    return {'schema_version': 1, 'source': source_name, 'engine': 'Vale',
            'counts': counts, 'strong': strong, 'weak': weak, 'findings': findings,
            'omitted_findings': max(0, len(selected) - limit)}


def render(result):
    lines = ['Humanizer cues: {} strong, {} weak. Matches need context.'.format(
        sum(result['strong'].values()), sum(result['weak'].values()))]
    for finding in result['findings']:
        lines.append('{}:{}:{} {} {}'.format(
            result['source'], finding['line'], finding['columns'][0],
            finding['rule'], json.dumps(finding['match'], ensure_ascii=False)))
    if result['weak']:
        lines.append('Weak counts: ' + ', '.join(
            '{}={}'.format(rule, count) for rule, count in result['weak'].items()))
    if result['omitted_findings']:
        lines.append('{} selected matches omitted; raise --max-findings to see more.'.format(
            result['omitted_findings']))
    lines.append('Use --details RULE for matches, --explain RULE for catalog guidance.')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', help='Markdown/text file, or - for stdin')
    parser.add_argument('--format', choices=('md', 'txt'), default='md',
                        help='input format, default md (also accepts plain prose)')
    parser.add_argument('--details', metavar='RULE', help='one rule or all; default strong cues only')
    parser.add_argument('--explain', metavar='RULE', help='print only this rule\'s catalog section')
    parser.add_argument('--max-findings', type=int, default=20)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--vale', default='vale', help='Vale executable path')
    args = parser.parse_args(argv)
    try:
        rules = json.loads((SKILL / 'rules.json').read_text(encoding='utf-8'))
        if args.explain:
            print(explain(rule_name(args.explain, rules), rules))
            return 0
        if not args.file:
            parser.error('provide a file or - for stdin')
        if args.max_findings < 1:
            parser.error('--max-findings must be positive')
        details = args.details
        if details and details != 'all':
            details = rule_name(details, rules)
        source = sys.stdin.read() if args.file == '-' else Path(args.file).read_text(encoding='utf-8')
        result = report(scan(source, '.' + args.format, args.vale), args.file,
                        details, args.max_findings, rules)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
        return 0
    except FileNotFoundError as error:
        print('prose-check: file or Vale executable missing: {}. Install Vale 3.20+ to scan.'.format(
            error.filename), file=sys.stderr)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('prose-check: {}'.format(error), file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
