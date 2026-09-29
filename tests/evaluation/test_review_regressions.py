"""Check executable fixture ground truth, not LLM instruction effectiveness."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/review-regressions'
SPEC = importlib.util.spec_from_file_location('evaluate_skills', ROOT / 'scripts/evaluate-skills.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ReviewRegressionFixtures(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.workspace = Path(self.directory.name)
        self.fixtures = json.loads((FIXTURES / 'workspaces.json').read_text())

    def command(self, *args):
        result = subprocess.run([sys.executable, '-B', *args], cwd=self.workspace,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def receipt(self, *args):
        return json.loads(self.command(*args).stdout)

    def test_cases_have_runnable_workspaces_and_withheld_rubrics(self):
        cases = json.loads((FIXTURES / 'cases.json').read_text())
        self.assertEqual({case['id'] for case in cases}, set(self.fixtures))
        for case in cases:
            contents = json.dumps(self.fixtures[case['id']])
            self.assertTrue(case['rubric'])
            for criterion in case['rubric']:
                self.assertNotIn(criterion, contents)
                self.assertNotIn(criterion, case['prompt'])

    def test_successful_producer_does_not_establish_consumer_acceptance(self):
        runner.prepare_workspace(self.workspace, self.fixtures['gate-consumer-handoff'])
        tests = self.command('-m', 'unittest', 'discover', '-s', 'tests', '-v')
        self.assertIn('Ran 2 tests', tests.stderr)
        events = ('opened', 'body', 'invalid', 'restored')
        receipts = self.receipt('simulate.py', *events)
        self.assertEqual([r['mergeable'] for r in receipts], [True, False, False, True])
        self.assertEqual(len({r['sha'] for r in receipts}), 1)
        self.assertTrue(all(v == 'success' for v in receipts[1]['checks'].values()))
        self.assertNotIn('tests', receipts[1]['checks'])
        # The same consumer exercise distinguishes the working historical producer.
        runner.git(self.workspace, 'checkout', 'BASE', '--', 'producer.py')
        receipts = self.receipt('simulate.py', *events)
        self.assertEqual([r['mergeable'] for r in receipts], [True, True, False, True])

    def test_byte_restoration_retains_entries_but_skips_enforcement(self):
        runner.prepare_workspace(self.workspace, self.fixtures['rollback-retained-selection'])
        self.assertEqual(runner.git(self.workspace, 'show', 'BASE:integration_filter.py'),
                         runner.git(self.workspace, 'show', 'HEAD:integration_filter.py'))
        self.assertEqual(runner.git(self.workspace, 'show', 'HEAD^:manifest.json'),
                         runner.git(self.workspace, 'show', 'HEAD:manifest.json'))
        tests = self.command('-m', 'unittest', 'discover', '-s', 'tests', '-v')
        self.assertIn('Ran 1 test', tests.stderr)
        entries = json.loads((self.workspace / 'manifest.json').read_text())
        excluded = []
        for entry in entries:
            receipt = self.receipt('pipeline.py', entry['target'], '--survives')
            self.assertIn(entry['id'], receipt['discovered'])
            if not receipt['scheduled']:
                excluded.append(entry['id'])
                self.assertEqual(receipt['enforced'], [])
                self.assertTrue(receipt['gate_passed'])
            else:
                self.assertEqual(receipt['scheduled'], [entry['id']])
                self.assertEqual(receipt['enforced'], [entry['id']])
                self.assertFalse(receipt['gate_passed'])
                self.assertTrue(self.receipt('pipeline.py', entry['target'])['gate_passed'])
        self.assertEqual(excluded, ['plugin-boundary'])
        # A core change in the same batch hides the target-only scheduling defect.
        mixed = self.receipt('pipeline.py', 'src/core/rules.py', 'src/plugins/widget.py', '--survives')
        self.assertEqual(mixed['enforced'], ['core-boundary', 'plugin-boundary'])
        self.assertFalse(mixed['gate_passed'])
        unrelated = self.receipt('pipeline.py', 'docs/usage.md', '--survives')
        self.assertEqual(unrelated['scheduled'], [])
        self.assertTrue(unrelated['gate_passed'])
        # Before rollback, every retained target reaches enforcement on its own.
        runner.git(self.workspace, 'checkout', 'HEAD^', '--', 'integration_filter.py')
        for entry in entries:
            receipt = self.receipt('pipeline.py', entry['target'], '--survives')
            self.assertEqual(receipt['enforced'], [entry['id']])
            self.assertFalse(receipt['gate_passed'])


if __name__ == '__main__':
    unittest.main()
