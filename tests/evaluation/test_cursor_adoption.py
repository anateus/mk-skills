"""Ground-truth checks for bounded, synthetic Cursor adoption evaluations."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/cursor-adoption'
SPEC = importlib.util.spec_from_file_location('evaluate_skills', ROOT / 'scripts/evaluate-skills.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class CursorAdoptionFixtures(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        self.fixtures = json.loads((FIXTURES / 'workspaces.json').read_text())

    def prepare(self, name):
        runner.prepare_workspace(self.workspace, self.fixtures[name])
        self.assertEqual(runner.git(self.workspace, 'rev-parse', 'BASE'),
                         runner.git(self.workspace, 'rev-parse', 'HEAD^'))
        self.assertTrue(runner.git(self.workspace, 'diff', '--name-only', 'BASE..HEAD'))
        self.run_command('-m', 'unittest', 'discover', '-s', 'tests', '-v')

    def run_command(self, *args, success=True, input_text=''):
        result = subprocess.run([sys.executable, '-B', *args], cwd=self.workspace,
                                input=input_text, capture_output=True, text=True, timeout=5,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_cases_discoverable_and_rubrics_withheld(self):
        cases = json.loads((FIXTURES / 'cases.json').read_text())
        self.assertEqual({case['id'] for case in cases}, set(self.fixtures))
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/evaluate-skills.py'),
                                 '--cases', str(FIXTURES / 'cases.json'), '--list'],
                                capture_output=True, text=True, check=True)
        self.assertEqual(set(result.stdout.splitlines()), set(self.fixtures))
        for case in cases:
            self.assertTrue(case['prompt'] and case['rubric'])
            for criterion in case['rubric']:
                self.assertNotIn(criterion, case['prompt'])
                self.assertNotIn(criterion, json.dumps(self.fixtures[case['id']]))

    def test_cli_non_tty_preview_and_retry(self):
        self.prepare('cli-headless-contract')
        store = str(self.workspace / 'markers.json')
        self.assertIn('usage:', self.run_command('marker.py', '--help').stdout)
        missing = self.run_command('marker.py', 'add', '--store', store, success=False)
        self.assertIn('EOFError', missing.stderr)
        self.assertFalse(Path(store).exists())
        preview = json.loads(self.run_command('marker.py', 'add', '--name', 'v1', '--store', store,
                                              '--dry-run').stdout)
        self.assertEqual(preview['markers'], [])
        self.assertFalse(Path(store).exists())
        self.run_command('marker.py', 'add', '--name', 'v1', '--store', store)
        self.run_command('marker.py', 'add', '--name', 'v1', '--store', store)
        self.assertEqual(json.loads(Path(store).read_text()), ['v1', 'v1'])
        listed = json.loads(self.run_command('marker.py', 'list', '--store', store).stdout)
        self.assertEqual(listed['markers'], ['v1', 'v1'])

    def test_cli_specification_case_preserves_existing_contract(self):
        self.prepare('cli-specification-contract')
        store = self.workspace / 'markers.json'
        self.assertIn('usage:', self.run_command('marker.py', '--help').stdout)
        self.assertIn('--name required', self.run_command('marker.py', 'add', '--store',
                                                        str(store), success=False).stderr)
        self.assertFalse(store.exists())
        self.assertEqual(json.loads(self.run_command('marker.py', 'add', '--name', 'v1',
                                                     '--store', str(store)).stdout), ['v1'])
        self.assertEqual(json.loads(self.run_command('marker.py', 'add', '--name', 'v1',
                                                     '--store', str(store)).stdout), ['v1'])
        self.assertEqual(json.loads(self.run_command('marker.py', 'list', '--store',
                                                     str(store)).stdout), ['v1'])
        self.assertNotIn('dry-run', self.run_command('marker.py', '--help').stdout)

    def test_pr_draft_inventory_and_public_behavior(self):
        self.prepare('author-pr-draft')
        changed = set(runner.git(self.workspace, 'diff', '--name-only', 'BASE..HEAD').splitlines())
        self.assertTrue({'serializer.py', 'catalog.py', 'generate.py', 'README.md'} <= changed)
        result = self.run_command('-c', 'from serializer import encode; from consumer import visible; '
                                  'print(visible(encode({"name":"a"})))')
        self.assertEqual(result.stdout.strip(), 'True')
        generated = (self.workspace / 'catalog.py').read_text()
        self.run_command('generate.py')
        self.assertEqual(generated, (self.workspace / 'catalog.py').read_text())
        self.assertIn('ITEM_2', generated)

    def test_synthetic_provider_statuses_are_head_scoped(self):
        self.prepare('ci-external-check')
        receipts = [json.loads(line) for line in self.run_command('checks.py').stdout.splitlines()]
        self.assertEqual([row['head'] for row in receipts], ['a1b2c3', 'd4e5f6'])
        self.assertEqual([(c['provider'], c['status']) for c in receipts[0]['checks']],
                         [('actions', 'success'), ('external', 'failure')])
        self.assertEqual({c['status'] for c in receipts[1]['checks']}, {'pending'})

    def test_cold_start_documentation_drift_and_targeted_check(self):
        self.prepare('cold-start-readiness')
        self.assertIn('server.py', self.run_command('server.py', '--help', success=False).stderr)
        self.assertIn('usage:', self.run_command('app.py', '--help').stdout)
        self.assertEqual(self.run_command('app.py', '2').stdout.strip(), '4')
        self.run_command('-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_app.py')

    def test_harness_public_journey_and_owned_cleanup(self):
        self.prepare('harness-miniapp')
        store = self.workspace / 'owned.json'
        self.assertIn('usage:', self.run_command('notebook.py', '--help').stdout)
        self.assertEqual(json.loads(self.run_command('notebook.py', 'create', '--title', 'one',
                                                    '--store', str(store)).stdout), [{'title': 'one'}])
        self.assertEqual(json.loads(self.run_command('notebook.py', 'list', '--store', str(store)).stdout),
                         [{'title': 'one'}])
        self.assertEqual(json.loads(store.read_text()), [{'title': 'one'}])
        store.unlink()
        self.assertFalse(store.exists())


if __name__ == '__main__':
    unittest.main()
