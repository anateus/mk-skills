"""Execute standalone maintainability review fixtures through the public evaluator workspace API."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/maintainability-review'
SPEC = importlib.util.spec_from_file_location('evaluate_skills', ROOT / 'scripts/evaluate-skills.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class MaintainabilityReviewFixtures(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.workspace = Path(self.directory.name)
        self.fixtures = json.loads((FIXTURES / 'workspaces.json').read_text())

    def prepare(self, name):
        runner.prepare_workspace(self.workspace, self.fixtures[name])
        self.assertEqual(runner.git(self.workspace, 'rev-parse', '--verify', 'BASE^{commit}'),
                         runner.git(self.workspace, 'rev-parse', 'HEAD^'))
        self.assertTrue(runner.git(self.workspace, 'diff', '--name-only', 'BASE..HEAD'))
        tests = self.command('-m', 'unittest', 'discover', '-s', 'tests', '-v')
        self.assertIn('OK', tests.stderr)

    def command(self, *args, succeeds=True):
        result = subprocess.run([sys.executable, '-B', *args], cwd=self.workspace,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_cases_are_runner_discoverable_and_rubrics_withheld(self):
        cases = json.loads((FIXTURES / 'cases.json').read_text())
        self.assertEqual({case['id'] for case in cases}, set(self.fixtures))
        listing = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/evaluate-skills.py'),
                                  '--cases', str(FIXTURES / 'cases.json'), '--list'],
                                 capture_output=True, text=True, check=True)
        self.assertEqual(set(listing.stdout.splitlines()), set(self.fixtures))
        for case in cases:
            self.assertTrue(case['rubric'])
            self.assertTrue(case['prompt'])
            contents = json.dumps(self.fixtures[case['id']])
            for criterion in case['rubric']:
                self.assertNotIn(criterion, contents)
                self.assertNotIn(criterion, case['prompt'])

    def test_scattered_policy_disagrees_on_team_canada(self):
        self.prepare('maintainability-scattered-policy')
        receipt = json.loads(self.command('simulate.py', 'team', 'CA').stdout)
        self.assertEqual(receipt, {'policy': True, 'checkout': False, 'renewal': False})
        runner.git(self.workspace, 'checkout', 'BASE', '--', 'checkout.py', 'renewal.py')
        repaired = json.loads(self.command('simulate.py', 'team', 'CA').stdout)
        self.assertEqual(set(repaired.values()), {True})

    def test_optional_amount_is_silently_committed_and_wrapper_is_passthrough(self):
        self.prepare('maintainability-cast-fallback')
        self.assertEqual(json.loads(self.command('invoice.py', '{}').stdout), {'saved_amount': 0})
        self.assertEqual(json.loads(self.command('invoice.py', '{"amount": 42}').stdout),
                         {'saved_amount': 42})
        self.command('invoice.py', '{"amount": "bad"}', succeeds=False)
        runner.git(self.workspace, 'checkout', 'BASE', '--', 'invoice.py')
        self.command('invoice.py', '{}', succeeds=False)

    def test_failed_dependent_credit_keeps_debit_only_after_change(self):
        self.prepare('maintainability-atomic-dependency')
        receipts = [json.loads(line) for line in self.command('transfer.py').stdout.splitlines()]
        self.assertEqual(receipts[0]['balances'], {'source': 80, 'target': 20})
        self.assertEqual(receipts[1]['balances'], {'source': 80, 'target': 0})
        self.assertEqual(receipts[1]['error'], 'credit rejected')
        runner.git(self.workspace, 'checkout', 'BASE', '--', 'transfer.py')
        historical = [json.loads(line) for line in self.command('transfer.py').stdout.splitlines()]
        self.assertEqual(historical[1]['balances'], {'source': 100, 'target': 0})

    def test_correct_but_overbuilt_preserves_receipt_contract(self):
        self.prepare('maintainability-correct-overbuilt')
        inputs = ('{"item":"book","cents":1200}', '{"item":"pen","cents":0}')
        changed = [json.loads(self.command('receipt.py', raw).stdout) for raw in inputs]
        for bad in ('{"item":"book","cents":-1}', '{"item":"book"}', '[]'):
            self.command('receipt.py', bad, succeeds=False)
        runner.git(self.workspace, 'checkout', 'BASE', '--', 'receipt.py')
        original = [json.loads(self.command('receipt.py', raw).stdout) for raw in inputs]
        self.assertEqual(changed, original)
        for bad in ('{"item":"book","cents":-1}', '{"item":"book"}', '[]'):
            self.command('receipt.py', bad, succeeds=False)

    def test_clean_control_is_generated_validated_and_ordered(self):
        self.prepare('maintainability-clean-control')
        generated = (self.workspace / 'generated_table.py').read_text()
        self.assertGreater(len(generated.splitlines()), 1000)
        self.command('generate.py')
        self.assertEqual(generated, (self.workspace / 'generated_table.py').read_text())
        self.assertEqual(json.loads(self.command('app.py', '{"count": 2}').stdout)['audit'],
                         {'receipt_id': 'receipt-2'})
        for bad in ('{"count": "2"}', '{"count": -1}', '[]'):
            self.command('app.py', bad, succeeds=False)


if __name__ == '__main__':
    unittest.main()
