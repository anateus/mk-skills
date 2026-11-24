import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'skills/humanizer/scripts/prose-check.py'


@unittest.skipUnless(shutil.which('vale'), 'Vale required for the real Markdown/rule integration')
class ProseCheckTests(unittest.TestCase):
    def run_check(self, source, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '-', '--json', *args],
                              input=source, text=True, capture_output=True)

    def report(self, source, *args):
        result = self.run_check(source, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_strong_details_weak_counts_and_drilldown(self):
        source = 'Let that sink in. Robust systems are robust.\n'
        report = self.report(source)
        self.assertEqual(report['counts']['Humanizer.StageOpeners'], 1)
        self.assertEqual(report['counts']['Humanizer.StockWords'], 2)
        self.assertEqual([f['match'] for f in report['findings']], ['Let that sink in'])
        expanded = self.report(source, '--details', 'StockWords')
        self.assertEqual([f['match'] for f in expanded['findings']], ['Robust', 'robust'])
        self.assertEqual(expanded['counts'], report['counts'])

    def test_markdown_protected_regions_and_visible_link_text(self):
        source = '''---
title: robust
---
`robust` and [ordinary link](https://robust.test).

> robust quoted source

```
robust
```

```python
robust = True
```

    robust indented code

[robust](https://example.test) prose.
'''
        report = self.report(source, '--details', 'all')
        self.assertEqual(report['counts'], {'Humanizer.StockWords': 1})
        self.assertEqual(report['findings'][0]['line'], 18)

    def test_word_boundaries_case_and_unicode(self):
        report = self.report('Undelved, robustly. DELVE into café systems.\n')
        self.assertEqual(report['counts'], {'Humanizer.StockPhrases': 1})
        self.assertEqual(report['findings'][0]['match'], 'DELVE')

    def test_fostering_is_not_a_standalone_stock_word(self):
        self.assertEqual(self.report('Fostering cooperation.\n')['counts'], {})
        report = self.report('Fostering cooperation needs robust systems.\n',
                             '--details', 'StockWords')
        self.assertEqual(report['counts'], {'Humanizer.StockWords': 1})
        self.assertEqual([finding['match'] for finding in report['findings']], ['robust'])

    def test_every_rule_detects_a_known_positive(self):
        source = ('Here is the revised version. Let that sink in. Delve.\n\n'
                  'Not only faster, but cheaper. Robust systems, perhaps. This \u2014 that \u2013 other.\n\n'
                  '**Strong label**\n\nWhat this does is reduce delay.\n')
        self.assertEqual(self.report(source)['counts'], {
            'Humanizer.ChatResidue': 1, 'Humanizer.StageOpeners': 1,
            'Humanizer.StockPhrases': 1, 'Humanizer.Contrasts': 1,
            'Humanizer.StockWords': 1, 'Humanizer.Hedges': 1,
            'Humanizer.Dashes': 2, 'Humanizer.Bold': 1,
            'Humanizer.SetupReveals': 1,
        })

    def test_requested_setup_reveals_are_weak_and_expandable(self):
        sources = [
            "What's missing is what you said: ...",
            "What this does is ...",
            "What matters here is ...",
            "What I'd do is ...",
            "One catch I need to test: ...",
            "One catch: ...",
            "The catch is ...",
            "The good news: ...",
            "I checked BetterStack, and there's something odd.",
        ]
        for source in sources:
            with self.subTest(source=source):
                report = self.report(source)
                self.assertEqual(report['weak'].get('Humanizer.SetupReveals'), 1)
                self.assertNotIn('Humanizer.SetupReveals', report['strong'])
                self.assertFalse(any(f['rule'] == 'Humanizer.SetupReveals'
                                     for f in report['findings']))
                expanded = self.report(source, '--details', 'SetupReveals')
                findings = [f for f in expanded['findings']
                            if f['rule'] == 'Humanizer.SetupReveals']
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0]['section'], 4)

    def test_setup_reveals_cover_variants_and_sentence_boundaries(self):
        sources = [
            "What is missing is the retry limit.",
            "What was missing was the retry limit.",
            "WHAT'S MISSING HERE IS the retry limit.",
            "I checked the logs. What this does is clear the cache.",
            "One catch we haven't tested yet: whether the request times out.",
            "The thing is that the cache expires early.",
            "The problem: the callback failed.",
            "The twist is that the queue is empty.",
            "The kicker: the callback never ran.",
            "There is something interesting. The queue is empty.",
        ]
        for apostrophe in ("'", '’', '‘', 'ʼ'):
            sources.extend([
                f"What{apostrophe}s missing is the retry limit.",
                f"What I{apostrophe}d do is retry the call.",
                f"I checked the logs, and there{apostrophe}s something interesting.",
            ])
        for source in sources:
            with self.subTest(source=source):
                report = self.report(source)
                self.assertEqual(report['weak'].get('Humanizer.SetupReveals'), 1)

    def test_setup_reveals_leave_legitimate_uses_alone(self):
        sources = [
            "What changed is the schema, not the data.",
            "What is missing is the schema, not the data.",
            "What is the timeout?",
            "What this does is encrypt the payload, not the headers.",
            "What I'd do is preserve the schema rather than delete it.",
            "They explained that what this does is reduce latency.",
            "There is something odd about that request.",
            "The catch is a safety cable, not a fishing hook.",
            "The good news: the schema changed, not the data.",
            "One catcher: the player behind home plate.",
        ]
        for source in sources:
            with self.subTest(source=source):
                report = self.report(source, '--details', 'SetupReveals')
                self.assertNotIn('Humanizer.SetupReveals', report['counts'])

    def test_setup_reveals_respect_protected_markdown(self):
        source = '''---
title: "What's missing is the retry limit."
---
`What this does is clear the cache.`

> The catch is the retry limit.

```
I checked BetterStack, and there's something odd.
```

What this does is clear the cache.
'''
        report = self.report(source, '--details', 'SetupReveals')
        self.assertEqual(report['counts'].get('Humanizer.SetupReveals'), 1)
        self.assertEqual([f['line'] for f in report['findings']], [12])

    def test_plain_text_mode_scans_literal_markup(self):
        self.assertEqual(self.report('> robust\n', '--format', 'txt')['counts'],
                         {'Humanizer.StockWords': 1})

    def test_bounded_details_keep_full_counts(self):
        report = self.report('Let that sink in.\n' * 12, '--max-findings', '2')
        self.assertEqual(report['counts']['Humanizer.StageOpeners'], 12)
        self.assertEqual(len(report['findings']), 2)
        self.assertEqual(report['omitted_findings'], 10)

    def test_clean_input_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'draft with spaces.md'
            source = 'The retry limit is 3.\n'
            path.write_text(source)
            result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--json'],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['counts'], {})
            self.assertEqual(path.read_text(), source)

    def test_bad_path_rule_and_engine_failures_are_not_clean_reports(self):
        for args in [('/no/such/draft.md',), ('-', '--details', 'Missing'),
                     ('-', '--vale', '/no/such/vale')]:
            result = subprocess.run([sys.executable, str(SCRIPT), *args, '--json'],
                                    input='robust', text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertTrue(result.stderr)

    def test_explanation_reads_only_the_selected_catalog_section(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--explain', 'StockWords'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('### 12.', result.stdout)
        self.assertNotIn('### 13.', result.stdout)

    def test_engine_garbage_and_nonzero_exit_are_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'vale'
            for body in ['echo not-json', 'echo "[]"', 'echo "{}"; exit 1']:
                fake.write_text('#!/bin/sh\n' + body + '\n')
                fake.chmod(0o755)
                result = self.run_check('robust', '--vale', str(fake))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')

    def test_rule_catalog_and_actual_rules_cover_each_other(self):
        skill = SCRIPT.parents[1]
        rules = json.loads((skill / 'rules.json').read_text())
        self.assertEqual(set(rules), {'Humanizer.' + p.stem
                                     for p in (skill / 'styles/Humanizer').glob('*.yml')})
        for name in rules:
            result = subprocess.run([sys.executable, str(SCRIPT), '--explain', name],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
