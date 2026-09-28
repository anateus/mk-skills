import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse


SCRIPT = Path(__file__).resolve().parents[2] / 'skills/learning-from-mistakes/scripts/collect_pr_comments.py'
spec = importlib.util.spec_from_file_location('collector', SCRIPT)
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


def comment(number, when, body='Comment'):
    return dict(id=number, created_at=when, updated_at=when, body=body,
                html_url=f'https://example.invalid/comment/{number}', user={'login': 'reviewer'})


def fixture():
    pr = dict(id=42, number=1, title='Synthetic PR', body='unneeded PR description',
              repository_url='https://api.github.com/repos/example/repo',
              html_url='https://github.com/example/repo/pull/1',
              created_at='2025-01-01T00:00:00Z', updated_at='2026-01-14T00:00:00Z')
    return {
        'user': {'login': 'author'},
        'search/issues': dict(total_count=1, incomplete_results=False, items=[pr]),
        'repos/example/repo/issues/1/comments': [
            comment(1, '2025-12-31T23:59:59Z'),
            comment(2, '2026-01-01T00:00:00Z', '[P2] Reported issue'),
            comment(3, '2026-01-15T00:00:00Z'),
            comment(4, '2026-01-02T00:00:00Z', '')],
        'repos/example/repo/pulls/1/comments': [
            comment(5, '2026-01-02T00:00:00Z', '<img alt="P1"> Finding')],
        'repos/example/repo/pulls/1/reviews': [
            dict(comment(6, '2025-12-01T00:00:00Z', 'P0: None'), submitted_at='2026-01-03T00:00:00Z'),
            dict(comment(7, '2026-01-03T00:00:00Z'), submitted_at=None)],
    }


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'output'

    def invoke(self, data=None, extra=()):
        data = fixture() if data is None else data
        argv = [str(SCRIPT), '--start', '2026-01-01T00:00:00Z',
                '--end', '2026-01-15T00:00:00Z', '--out', str(self.out), *extra]
        with patch('sys.argv', argv), patch.object(collector, 'api', side_effect=lambda ep: data[ep.split('?')[0]]) as api:
            with contextlib.redirect_stdout(io.StringIO()):
                collector.main()
        return api

    def test_all_surfaces_timestamp_boundaries_and_review_submission(self):
        self.invoke()
        rows = json.loads((self.out / 'comments.json').read_text())
        self.assertEqual([r['id'] for r in rows], [2, 5, 6])
        self.assertEqual([r['kind'] for r in rows], ['conversation', 'inline', 'review'])
        self.assertEqual(json.loads((self.out / 'manifest.json').read_text())['comments'], 3)

    def test_existing_output_is_never_overwritten(self):
        self.out.mkdir()
        (self.out / 'comments.json').write_text('preserve this snapshot')
        with self.assertRaises((FileExistsError, SystemExit)):
            self.invoke()
        self.assertEqual((self.out / 'comments.json').read_text(), 'preserve this snapshot')

    def test_pr_descriptions_are_not_collected(self):
        self.invoke()
        prs = json.loads((self.out / 'prs.json').read_text())
        self.assertNotIn('body', prs[0])

    def test_timezone_normalization_preserves_search_population(self):
        api = self.invoke(extra=['--start', '2026-01-01T01:00:00+02:00'])
        endpoint = next(call.args[0] for call in api.call_args_list if call.args[0].startswith('search/issues?'))
        self.assertIn('updated:>=2025-12-31', parse_qs(urlparse(endpoint).query)['q'][0])

    def test_pagination_reads_past_a_full_page_and_propagates_errors(self):
        with patch.object(collector, 'api', side_effect=[list(range(100)), [100]]) as api:
            self.assertEqual(collector.pages('endpoint'), list(range(101)))
            self.assertEqual(api.call_args_list[-1].args, ('endpoint?per_page=100&page=2',))
        with patch.object(collector, 'api', side_effect=[list(range(100)), RuntimeError('failed')]):
            with self.assertRaisesRegex(RuntimeError, 'failed'):
                collector.pages('endpoint')

    def test_incomplete_capped_and_duplicate_searches_fail_without_manifest(self):
        for changes in [dict(incomplete_results=True), dict(total_count=1001),
                        dict(total_count=2, items=fixture()['search/issues']['items'] * 2)]:
            data = fixture()
            data['search/issues'].update(changes)
            with self.subTest(changes=changes), self.assertRaises((RuntimeError, AssertionError, SystemExit)):
                self.invoke(data)
            self.assertFalse((self.out / 'manifest.json').exists())

    def test_comment_failure_never_publishes_complete_snapshot(self):
        data = fixture()
        del data['repos/example/repo/pulls/1/reviews']
        with self.assertRaises(KeyError):
            self.invoke(data)
        self.assertFalse((self.out / 'manifest.json').exists())

    def test_search_pagination_and_changing_population(self):
        original = fixture()['search/issues']['items'][0]
        first = dict(total_count=101, incomplete_results=False,
                     items=[dict(original, id=i, number=i) for i in range(100)])
        second = dict(total_count=101, incomplete_results=False, items=[dict(original, id=100, number=100)])
        with patch.object(collector, 'api', side_effect=[first, second]) as api:
            self.assertEqual(len(collector.search_prs('query')), 101)
            self.assertEqual(parse_qs(urlparse(api.call_args_list[-1].args[0]).query)['page'], ['2'])
        second['total_count'] = 102
        with patch.object(collector, 'api', side_effect=[first, second]):
            with self.assertRaisesRegex(RuntimeError, 'totals changed'):
                collector.search_prs('query')

    def test_empty_search_writes_explicit_zero_counts(self):
        data = fixture()
        data['search/issues'].update(total_count=0, items=[])
        self.invoke(data)
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual((manifest['candidate_prs'], manifest['comments']), (0, 0))
        self.assertEqual(json.loads((self.out / 'coverage.json').read_text()), [])

    def test_duplicate_inline_comments_fail_and_null_body_is_omitted(self):
        data = fixture()
        endpoint = 'repos/example/repo/pulls/1/comments'
        data[endpoint] *= 2
        with self.assertRaisesRegex(RuntimeError, 'Duplicate inline'):
            self.invoke(data)
        self.assertFalse(self.out.exists())
        data[endpoint] = [comment(5, '2026-01-02T00:00:00Z', None)]
        self.invoke(data)
        self.assertEqual([r['id'] for r in json.loads((self.out / 'comments.json').read_text())], [2, 6])

    def test_failed_api_does_not_expose_command_output(self):
        result = subprocess.CompletedProcess([], 1, stdout='private response body', stderr='secret diagnostic')
        with patch.object(collector.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError) as caught:
                collector.api('user')
        self.assertNotIn('private', str(caught.exception))
        self.assertNotIn('secret', str(caught.exception))
        self.assertIn('exit 1', str(caught.exception))

    def test_bad_timestamp_or_search_qualifiers_fail_before_requests(self):
        for extra in [('--start', '2026-01-01'), ('--end', '2025-12-01T00:00:00Z'),
                      ('--author', 'author is:issue'), ('--repo', 'example/repo is:issue')]:
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.invoke(extra=extra)
            self.assertFalse(self.out.exists())

    def test_write_failure_leaves_no_completion_marker(self):
        with patch.object(Path, 'write_bytes', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.invoke()
        self.assertFalse((self.out / 'manifest.json').exists())

    def test_real_cli_with_synthetic_gh_keeps_priority_headings_as_candidates(self):
        data = self.root / 'responses.json'
        data.write_text(json.dumps(fixture()))
        gh = self.root / 'gh'
        gh.write_text(f'#!{sys.executable}\nimport json,os,sys\n'
                      'with open(os.environ["COLLECTOR_RESPONSES"]) as f: data=json.load(f)\n'
                      'print(json.dumps(data[sys.argv[2].split("?")[0]]))\n')
        gh.chmod(0o755)
        result = subprocess.run([sys.executable, str(SCRIPT), '--start', '2026-01-01T00:00:00Z',
                                 '--end', '2026-01-15T00:00:00Z', '--repo', 'example/repo', '--out', str(self.out)],
                                env={**os.environ, 'PATH': str(self.root) + os.pathsep + os.environ['PATH'],
                                     'COLLECTOR_RESPONSES': str(data)}, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        self.assertIn('repo:example/repo', manifest['query'])
        self.assertNotIn('Reported issue', result.stdout)
        candidates = json.loads((self.out / 'priority-candidates.json').read_text())
        self.assertEqual([x['candidate_priorities'] for x in candidates], [['P2'], ['P1'], ['P0']])
        self.assertEqual(candidates[-1]['body'], 'P0: None')
        self.assertNotIn('severity', candidates[-1])
        import hashlib
        for name, digest in manifest['sha256'].items():
            self.assertEqual(hashlib.sha256((self.out / name).read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
