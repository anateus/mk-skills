import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/evaluate-skills.py'
SPEC = importlib.util.spec_from_file_location('evaluate_skills', SCRIPT)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class EvaluationTests(unittest.TestCase):
    def test_fresh_workspaces_raw_prompts_rubric_separation_and_pinned_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = {'id': 'sample', 'prompt': 'Fix the typo.', 'rubric': ['SECRET_EXPECTATION'],
                    'expectedSkills': ['implementing-work'], 'forbiddenSkills': [], 'expectedReferences': []}
            (root / 'cases.json').write_text(json.dumps([case]))
            (root / 'fixtures.json').write_text(json.dumps({'sample': {'commits': [{'README.md': 'teh'}]}}))
            fake = root / 'fake.py'
            fake.write_text('''import json, pathlib, sys
p = pathlib.Path.cwd()
prompt = sys.stdin.read()
assert prompt == "Fix the typo."
assert (p / "README.md").read_text() == "teh"
assert not any("SECRET_EXPECTATION" in f.read_text(errors="replace") for f in p.rglob("*") if f.is_file() and ".git" not in f.parts)
assert ".skill-catalog" in sys.argv[1]
(p / "README.md").write_text("the")
print(json.dumps({"prompt": prompt, "workspace": str(p)}))
''')
            (root / 'command.json').write_text(json.dumps([sys.executable, str(fake), '{context}']))
            hashes, workspaces = [], []
            for name in ('first', 'second'):
                output = root / name
                result = subprocess.run([sys.executable, str(SCRIPT), '--host', 'custom',
                    '--command-json', str(root / 'command.json'), '--cases', str(root / 'cases.json'),
                    '--fixtures', str(root / 'fixtures.json'), '--case', 'sample', '--output', str(output)],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                record = json.loads((output / 'sample/result.json').read_text())
                self.assertEqual(record['grading'], 'pending')
                self.assertNotEqual(record['before']['sha256'], record['after']['sha256'])
                self.assertEqual((output / 'sample/workspace/README.md').read_text(), 'the')
                self.assertIn('SECRET_EXPECTATION', (output / 'sample/rubric.json').read_text())
                hashes.append(record['snapshot_sha256'])
                workspaces.append(json.loads((output / 'sample/trace.jsonl').read_text())['workspace'])
            self.assertEqual(hashes[0], hashes[1])
            self.assertNotEqual(workspaces[0], workspaces[1])
            self.assertTrue(all(not Path(p).exists() for p in workspaces))

    def test_fixture_paths_cannot_escape_or_replace_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ['../escape', '/tmp/escape', '.git/config', '.skill-catalog/context.txt']:
                with self.assertRaises(ValueError):
                    runner.write_files(Path(directory), {name: 'bad'})

    def test_nonzero_and_timeout_are_recorded_without_success_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failed = runner.run_process([sys.executable, '-c', 'raise SystemExit(7)'], '', root, root, 5)
            self.assertEqual(failed['exit_code'], 7)
            timed = runner.run_process([sys.executable, '-c', 'import time; time.sleep(30)'], '', root, root, 0.1)
            self.assertTrue(timed['timed_out'])
            self.assertNotEqual(timed['exit_code'], 0)

    def test_output_cannot_recurse_into_source_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'skills').mkdir()
            result = subprocess.run([sys.executable, str(SCRIPT), '--source', str(source),
                '--case', 'trivial-local-typo', '--output', str(source / 'skills/results')],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('outside the source skills tree', result.stderr)
            self.assertFalse((source / 'skills/results').exists())


if __name__ == '__main__':
    unittest.main()
