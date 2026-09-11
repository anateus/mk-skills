import importlib.util
import json
import os
from pathlib import Path
import shutil
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
    def test_optional_plugin_is_frozen_with_relative_resources_and_namespaced_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / 'plugin'
            (plugin / '.codex-plugin').mkdir(parents=True)
            (plugin / '.codex-plugin/plugin.json').write_text(json.dumps({'name': 'sample-plugin'}))
            (plugin / 'skills/reasoning').mkdir(parents=True)
            (plugin / 'skills/reasoning/SKILL.md').write_text(
                '---\nname: reasoning\ndescription: Assess uncertain inputs.\n---\nRead ../../scripts/check.py\n')
            (plugin / 'scripts').mkdir()
            helper = plugin / 'scripts/check.py'
            helper.write_text('print("FROZEN_PLUGIN_RESOURCE")\n')
            (root / 'cases.json').write_text(json.dumps([{'id': 'sample', 'prompt': 'Assess this.'}]))
            (root / 'fixtures.json').write_text(json.dumps({'sample': {'commits': [{'README.md': 'fixture'}]}}))
            fake = root / 'fake.py'
            fake.write_text('''import pathlib, subprocess, sys
p = pathlib.Path.cwd()
context = pathlib.Path(sys.argv[1]).read_text()
entry = p / '.skill-catalog/plugins/sample-plugin/skills/reasoning/SKILL.md'
line = next(line for line in context.splitlines() if line.startswith('- sample-plugin:reasoning:'))
assert pathlib.Path(line.rsplit('(', 1)[1][:-1]).resolve() == entry.resolve()
helper = entry.parent / '../../scripts/check.py'
assert subprocess.check_output([sys.executable, str(helper)], text=True).strip() == 'FROZEN_PLUGIN_RESOURCE'
pathlib.Path(sys.argv[2]).write_text('raise RuntimeError("MUTATED_PLUGIN")')
print('fixture answer')
''')
            (root / 'command.json').write_text(json.dumps([sys.executable, str(fake), '{context}', str(helper)]))
            output = root / 'output'
            result = subprocess.run([sys.executable, str(SCRIPT), '--host', 'custom',
                '--command-json', str(root / 'command.json'), '--plugin', str(plugin), '--repetitions', '2',
                '--cases', str(root / 'cases.json'), '--fixtures', str(root / 'fixtures.json'), '--case', 'sample',
                '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout + ''.join(
                p.read_text() for p in output.glob('sample/repeat-*/stderr.log')))
            self.assertIn('FROZEN_PLUGIN_RESOURCE',
                          (output / 'snapshot/plugins/sample-plugin/scripts/check.py').read_text())
            execution = json.loads((output / 'snapshot/evaluation/execution.json').read_text())
            self.assertEqual(execution['plugins'], ['sample-plugin'])
            with self.assertRaisesRegex(ValueError, 'unique simple names'):
                runner.plugin_sources([plugin, plugin])
            invalid = subprocess.run([sys.executable, str(SCRIPT), '--plugin', str(plugin),
                '--cases', str(root / 'cases.json'), '--fixtures', str(root / 'fixtures.json'),
                '--case', 'sample', '--output', str(plugin / 'output')], capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn('outside plugin source trees', invalid.stderr)
            self.assertFalse((plugin / 'output').exists())

    def test_both_hosts_receive_frozen_guidance_candidate_and_explicit_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            shutil.copytree(ROOT / 'skills', source / 'skills')
            (source / 'config').mkdir()
            shutil.copyfile(ROOT / 'config/mode-policy.json', source / 'config/mode-policy.json')
            guidance = source / 'skills/mk-skills-setup/assets/agents-guidance.md'
            original = guidance.read_text()
            instructions = root / 'candidate.md'
            instructions.write_text('CANDIDATE_SENTINEL: preserve quantity scope.')
            audit = root / 'audit.md'
            audit.write_text('AUDIT_SENTINEL: inspect material claims.')
            cases = [{'id': 'sample', 'prompt': 'Assess this.', 'rubric': ['WITHHELD_RUBRIC']}]
            (root / 'cases.json').write_text(json.dumps(cases))
            (root / 'fixtures.json').write_text(json.dumps({'sample': {'commits': [{'README.md': 'fixture'}]}}))
            fake = '''#!{python}
import json, pathlib, subprocess, sys
if '--version' in sys.argv:
    print('fixture-host 1.0')
    raise SystemExit()
assert sys.stdin.read() == 'Assess this.'
assert sys.argv[sys.argv.index('--model') + 1] == 'test-model'
if '--append-system-prompt' in sys.argv:
    context = sys.argv[sys.argv.index('--append-system-prompt') + 1]
else:
    context = json.loads(next(s.split('=', 1)[1] for s in sys.argv if s.startswith('developer_instructions=')))
assert 'CANDIDATE_SENTINEL' in context
assert 'AUDIT_SENTINEL' in context
assert 'MUTATED_INPUT' not in context
assert 'WITHHELD_RUBRIC' not in context
p = pathlib.Path.cwd()
assert (p / '.skill-catalog/skills/mk-skills-setup/assets/agents-guidance.md').read_text() in context
assert 'WITHHELD_RUBRIC' not in ''.join(f.read_text(errors='replace') for f in p.rglob('*') if f.is_file() and '.git' not in f.parts)
coordination = subprocess.run(['agentplan', 'status'], capture_output=True, text=True)
assert coordination.returncode == 1 and 'Fixture: external coordination' in coordination.stderr
pathlib.Path({guidance}).write_text('MUTATED_INPUT')
pathlib.Path({instructions}).write_text('MUTATED_INPUT')
print(json.dumps({{'type': 'result', 'is_error': False, 'result': 'fixture answer'}}))
'''.format(python=sys.executable, guidance=repr(str(guidance)), instructions=repr(str(instructions)))
            binary = root / 'bin'
            binary.mkdir()
            for host in ('codex', 'claude'):
                executable = binary / host
                executable.write_text(fake)
                executable.chmod(0o755)
                guidance.write_text(original)
                instructions.write_text('CANDIDATE_SENTINEL: preserve quantity scope.')
                output = root / host
                result = subprocess.run([sys.executable, str(SCRIPT), '--source', str(source),
                    '--host', host, '--model', 'test-model', '--instructions', str(instructions),
                    '--instructions', str(audit),
                    '--repetitions', '2', '--cases', str(root / 'cases.json'),
                    '--fixtures', str(root / 'fixtures.json'), '--case', 'sample', '--output', str(output)],
                    env={**os.environ, 'PATH': str(binary) + os.pathsep + os.environ.get('PATH', '')},
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                for repetition in (1, 2):
                    case_output = output / 'sample' / 'repeat-{:03d}'.format(repetition)
                    record = json.loads((case_output / 'result.json').read_text())
                    self.assertEqual(record['model_requested'], 'test-model')
                    self.assertEqual(record['repetition'], repetition)
                    self.assertIn('CANDIDATE_SENTINEL', (case_output / 'context.txt').read_text())
                self.assertEqual((output / 'snapshot/evaluation/cases.json').read_text(),
                                 (root / 'cases.json').read_text())
                self.assertIn('CANDIDATE_SENTINEL', (output / 'snapshot/evaluation/instructions.md').read_text())
                self.assertTrue((output / 'snapshot/evaluate-skills.py').exists())

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
context = pathlib.Path(sys.argv[1]).read_text()
guidance = (p / ".skill-catalog/skills/mk-skills-setup/assets/agents-guidance.md").read_text()
assert guidance in context, "shared guidance was snapshotted but never injected"
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
                self.assertEqual(result.returncode, 0,
                                 result.stderr + (output / 'sample/stderr.log').read_text())
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

    def test_case_ids_cannot_escape_output_or_alias_repetitions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for ids in (['../escape'], ['/tmp/escape'], ['same', 'same']):
                (root / 'cases.json').write_text(json.dumps([{'id': name} for name in ids]))
                result = subprocess.run([sys.executable, str(SCRIPT), '--cases', str(root / 'cases.json'),
                    '--case', ids[0], '--output', str(root / 'output')], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn('Case IDs must be unique simple names', result.stderr)
                self.assertFalse((root / 'output').exists())

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
