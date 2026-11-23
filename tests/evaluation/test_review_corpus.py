import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/review-corpus.py'
SPEC = importlib.util.spec_from_file_location('review_corpus', SCRIPT)
corpus_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(corpus_tool)


def git(repo, *args, date=None):
    env = dict(os.environ, GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
               GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')
    if date:
        env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = date + 'T12:00:00+0000'
    result = subprocess.run(['git', '-c', 'commit.gpgsign=false', *args], cwd=repo, env=env,
                            capture_output=True, text=True)
    if result.returncode:
        raise AssertionError('git ' + ' '.join(args) + ': ' + result.stderr)
    return result.stdout.strip()


def commit(repo, message, date, files):
    for name, lines in files.items():
        (repo / name).write_text(''.join(line + '\n' for line in lines))
    git(repo, 'add', '--all')
    git(repo, 'commit', '-m', message, date=date)
    return git(repo, 'rev-parse', 'HEAD')


def run_tool(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = corpus_tool.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class ReviewCorpusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name).resolve()
        self.corpus = self.tmp / 'corpus'
        self.source = self.tmp / 'source'
        self.source.mkdir()
        git(self.source, 'init', '-b', 'main')

    def tool(self, *argv):
        code, out, err = run_tool('--corpus', str(self.corpus), *argv)
        self.assertEqual(code, 0, err)
        return out

    def register(self):
        self.tool('add-repo', 'sample', str(self.source))
        self.tool('fetch')

    def history(self):
        app = ['line%d' % number for number in range(1, 21)]
        shas = {'init': commit(self.source, 'Initial import', '2026-01-01', {'app.py': app})}
        app[11:13] = ['tweak12', 'tweak13']
        shas['old'] = commit(self.source, 'Tweak limits (#9)', '2026-01-20', {'app.py': app})
        app[4:9] = ['feat%d' % number for number in range(5, 10)]
        shas['origin'] = commit(self.source, 'Add feature (#11)', '2026-03-10', {'app.py': app})
        app[5:7] = ['fixed6', 'fixed7']
        app[11:13] = ['fixed12', 'fixed13']
        shas['fix'] = commit(self.source, 'Fix crash on empty input (#12)', '2026-03-12', {'app.py': app})
        shas['adder'] = commit(self.source, 'Fix docs (#13)', '2026-03-13', {'app.py': app + ['extra']})
        shas['module'] = commit(self.source, 'Add b module (#14)', '2026-03-20', {'b.py': ['b1', 'b2', 'b3']})
        git(self.source, 'revert', '--no-edit', shas['module'], date='2026-05-01')
        shas['revert'] = git(self.source, 'rev-parse', 'HEAD')
        return shas

    def candidates(self):
        out = self.tool('candidates', '--repo', 'sample', '--since', '2026-03-01')
        return [json.loads(line) for line in out.splitlines()]

    def test_candidates_pair_fix_with_recent_origin_and_skip_old_origin_and_additions(self):
        shas = self.history()
        self.register()
        pairs = [pair for pair in self.candidates() if not pair['explicit']]
        self.assertEqual(len(pairs), 1, pairs)
        pair = pairs[0]
        self.assertEqual((pair['fix']['sha'], pair['fix']['pr']), (shas['fix'], 12))
        self.assertEqual((pair['origin']['sha'], pair['origin']['pr']), (shas['origin'], 11))
        self.assertEqual((pair['repo'], pair['lines'], pair['days'], pair['files']), ('sample', 2, 2.0, ['app.py']))
        self.assertNotIn(shas['old'], [item['origin']['sha'] for item in self.candidates()])
        self.assertNotIn(shas['adder'], [item['fix']['sha'] for item in self.candidates()])

    def test_revert_is_reported_as_explicit_even_outside_the_window(self):
        shas = self.history()
        self.register()
        pairs = self.candidates()
        explicit = [pair for pair in pairs if pair['explicit']]
        self.assertEqual(len(explicit), 1, pairs)
        self.assertEqual((explicit[0]['fix']['sha'], explicit[0]['origin']['sha'], explicit[0]['origin']['pr']),
                         (shas['revert'], shas['module'], 14))
        self.assertGreater(explicit[0]['days'], 7)
        self.assertTrue(pairs[0]['explicit'], 'explicit pairs sort first')

    def test_controls_list_prs_no_later_fix_rewrote_and_refuse_a_too_recent_until(self):
        base = ['line%d' % number for number in range(1, 21)]
        commit(self.source, 'Initial import', '2026-01-01', {'a.py': base, 'b.py': base})
        a = list(base)
        a[4:7] = ['a5', 'a6', 'a7']
        clean = commit(self.source, 'Edit a (#21)', '2026-02-01', {'a.py': a})
        b = list(base)
        b[4:7] = ['b5', 'b6', 'b7']
        commit(self.source, 'Edit b (#22)', '2026-02-02', {'b.py': b})
        b[4:6] = ['fixed5', 'fixed6']
        commit(self.source, 'Fix b crash (#23)', '2026-02-05', {'b.py': b})
        a[14] = 'later'
        commit(self.source, 'Later work (#24)', '2026-04-01', {'a.py': a})
        self.register()
        out = self.tool('controls', '--repo', 'sample', '--since', '2026-01-15', '--until', '2026-02-10',
                        '--min-lines', '1')
        leads = [json.loads(line) for line in out.splitlines()]
        self.assertEqual([(lead['pr'], lead['sha'], lead['changed_lines'], lead['changed_files'])
                          for lead in leads], [(21, clean, 6, 1)])
        code, _, err = run_tool('--corpus', str(self.corpus), 'controls', '--repo', 'sample',
                                '--since', '2026-01-15', '--until', '2026-03-30')
        self.assertEqual(code, 2)
        self.assertIn('latest allowed is 2026-03-18', err)

    def feature_branch(self):
        commit(self.source, 'Base work', '2026-02-01', {'a.txt': ['a']})
        git(self.source, 'checkout', '-b', 'feature')
        base = git(self.source, 'rev-parse', 'HEAD')
        head = commit(self.source, 'Feature', '2026-02-02', {'f.txt': ['one', 'two', 'three']})
        git(self.source, 'checkout', 'main')
        moved = commit(self.source, 'Main moves on', '2026-02-03', {'a.txt': ['a', 'b']})
        return base, head, moved

    def case(self, base, head, findings, pr=7, control=False):
        return {'repo': 'sample', 'pr': pr, 'title': 'Feature', 'url': 'https://example.invalid/pull/%d' % pr,
                'base_sha': base, 'reviewed_sha': head, 'control': control, 'notes': '',
                'changed_files': 99, 'changed_lines': 999, 'findings': findings}

    def finding(self, number):
        return {'severity': 'P1', 'path': 'f.txt', 'line': number, 'summary': 'Defect %d' % number,
                'confirmation': 'Reproduced', 'how_discoverable': 'Reading the diff', 'reviewer': 'person',
                'reviewer_is_bot': False, 'comment_url': 'https://example.invalid/comment/%d' % number}

    def add(self, case):
        path = self.tmp / 'input.json'
        path.write_text(json.dumps(case))
        return self.tool('add', str(path))

    def stored(self, case_id):
        return json.loads((self.corpus / 'cases' / (case_id + '.json')).read_text())

    def test_add_rejects_a_base_that_is_not_the_merge_base(self):
        base, head, moved = self.feature_branch()
        self.register()
        path = self.tmp / 'bad.json'
        path.write_text(json.dumps(self.case(moved, head, [self.finding(1)])))
        code, _, err = run_tool('--corpus', str(self.corpus), 'add', str(path))
        self.assertEqual(code, 2)
        self.assertIn('review-corpus: ', err)
        self.assertIn('merge base', err)
        self.assertFalse((self.corpus / 'cases' / 'sample-7.json').exists())

    def test_add_merges_new_findings_into_existing_case_without_renumbering(self):
        base, head, _ = self.feature_branch()
        self.register()
        self.add(self.case(base, head, [self.finding(1)]))
        first = self.stored('sample-7')
        self.assertEqual((first['head_sha'], first['changed_files'], first['changed_lines']), (head, 1, 3))
        self.assertEqual([item['id'] for item in first['findings']], ['F1'])
        self.assertEqual(first['findings'][0]['source'], 'review-comment')
        self.add(self.case(base, head, [self.finding(1), self.finding(2)]))
        merged = self.stored('sample-7')
        self.assertEqual([(item['id'], item['comment_url'][-1]) for item in merged['findings']],
                         [('F1', '1'), ('F2', '2')])
        self.assertEqual(merged['findings'][0], first['findings'][0])
        log = git(self.corpus, 'log', '--format=%s')
        self.assertIn('add cases: sample-7', log)

    def test_build_writes_evaluator_inputs_with_fixture_shape_and_control_criterion(self):
        base, head, _ = self.feature_branch()
        self.register()
        escaped = dict(self.finding(2), source='escaped', review_at_the_time='Nobody commented',
                       fix={'pr': 9, 'url': 'https://example.invalid/pull/9', 'sha': 'a' * 40,
                            'kind': 'hotfix', 'days_after_merge': 1.5})
        for key in ('reviewer', 'reviewer_is_bot', 'comment_url'):
            del escaped[key]
        self.add([self.case(base, head, [self.finding(1), escaped]),
                  self.case(base, head, [], pr=8, control=True)])
        out = self.tmp / 'out'
        self.tool('build', '--out', str(out))
        cases = json.loads((out / 'cases.json').read_text())
        self.assertEqual([item['id'] for item in cases], ['sample-7', 'sample-8'])
        self.assertEqual(set(cases[0]), {'id', 'prompt', 'expectedSkills', 'forbiddenSkills',
                                         'expectedReferences', 'rubric'})
        self.assertEqual((cases[0]['expectedSkills'], cases[0]['rubric']), (['reviewing-code'], []))
        self.assertEqual(cases[0]['prompt'], corpus_tool.DEFAULT_PROMPT)
        workspaces = json.loads((out / 'workspaces.json').read_text())
        self.assertEqual(workspaces['sample-7'], {'repository': {
            'path': str((self.corpus / 'mirrors/sample.git').resolve()), 'base': base, 'head': head}})
        criteria = json.loads((out / 'criteria/sample-7.json').read_text())
        self.assertEqual([(item['id'], item['source'], item['severity']) for item in criteria],
                         [('F1', 'review-comment', 'P1'), ('F2', 'escaped', 'P1')])
        self.assertEqual(criteria[0]['criterion'],
                         'The report identifies this defect (in its own words is fine; it must be '
                         'recognizably the same problem, at or near f.txt): Defect 1')
        self.assertEqual(json.loads((out / 'criteria/sample-8.json').read_text()), [
            {'id': 'C1', 'criterion': 'The report raises no P1 or merge-blocking finding.'}])
        self.tool('build', '--out', str(self.tmp / 'escaped-only'), '--source', 'escaped')
        kept = json.loads((self.tmp / 'escaped-only/criteria/sample-7.json').read_text())
        self.assertEqual([item['id'] for item in kept], ['F2'])
        code, _, err = run_tool('--corpus', str(self.corpus), 'build', '--out', str(out))
        self.assertEqual(code, 2)
        self.assertIn('already exists', err)

    def test_paths_inside_this_checkout_are_refused(self):
        inside = ROOT / 'private-corpus-should-not-exist'
        code, _, err = run_tool('--corpus', str(inside), 'list')
        self.assertEqual(code, 2)
        self.assertIn('review-corpus: Corpus root must not be inside', err)
        self.assertFalse(inside.exists())
        out = ROOT / 'private-build-should-not-exist'
        code, _, err = run_tool('--corpus', str(self.corpus), 'build', '--out', str(out))
        self.assertEqual(code, 2)
        self.assertIn('Build output directory must not be inside', err)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
