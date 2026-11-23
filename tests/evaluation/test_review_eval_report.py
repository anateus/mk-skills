import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/review-eval-report.py'
SPEC = importlib.util.spec_from_file_location('review_eval_report', SCRIPT)
report_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report_tool)


class ReviewEvalReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def test_packets_shuffle_repetitions_and_keep_arm_mapping_in_separate_key(self):
        run = self.root / 'existing'
        (run / 'workspace').mkdir(parents=True)
        (run / 'workspace' / 'assessment.md').write_text('Verdict: merge\n')
        self.put(run / 'result.json', {'exit_code': 0, 'timed_out': False, 'elapsed_seconds': 4})
        blank = self.root / 'blank'
        (blank / 'workspace').mkdir(parents=True)
        (blank / 'workspace' / 'assessment.md').write_text('  \n')
        self.put(blank / 'result.json', {'exit_code': 0, 'timed_out': False, 'elapsed_seconds': 3})
        self.put(self.root / 'criteria' / 'case.json', [{'id': 'F1', 'criterion': 'known finding'}])
        self.put(self.root / 'runs.json', [
            {'model': 'model', 'arm': 'arm-a', 'case': 'case', 'path': 'existing', 'repetition': 1},
            {'model': 'model', 'arm': 'arm-a', 'case': 'case', 'path': 'blank', 'repetition': 2},
            {'model': 'model', 'arm': 'arm-b', 'case': 'case', 'path': 'absent'}])
        args = argparse.Namespace(runs=str(self.root / 'runs.json'), criteria=str(self.root / 'criteria'),
                                  out=str(self.root / 'packets'), key=str(self.root / 'key.json'), seed=17)

        report_tool.packets(args)

        packet = self.root / 'packets' / 'model' / 'case'
        key = json.loads((self.root / 'key.json').read_text())
        self.assertEqual(len(key['runs']), 3)
        visible = '\n'.join(path.read_text() for path in packet.rglob('*') if path.is_file())
        self.assertNotIn('arm-a', visible)
        self.assertNotIn('arm-b', visible)
        self.assertEqual(sum('No usable assessment' in path.read_text()
                             for path in (packet / ('r%d' % n) / 'assessment.md' for n in (1, 2, 3))), 2)
        self.assertEqual(sorted(row['repetition'] for row in key['runs'] if row['arm'] == 'arm-a'), [1, 2])
        self.assertEqual(sum(row['effort']['status'] == 'missing_result' for row in key['runs']), 1)
        self.assertEqual(sum(row['effort']['status'] == 'missing_report' for row in key['runs']), 1)

    def test_tally_excludes_missing_grade_and_uses_case_level_cutoff_intervals(self):
        self.put(self.root / 'key.json', {'version': 1, 'runs': [
            {'model': 'model', 'case': 'defect', 'arm': 'arm', 'label': 'r1',
             'effort': {'status': 'ok', 'seconds': 8, 'trace_present': False}},
            {'model': 'model', 'case': 'other', 'arm': 'arm', 'label': 'r2',
             'effort': {'status': 'ok', 'seconds': 6, 'trace_present': False}}]})
        self.put(self.root / 'cases' / 'defect.json', {'control': False, 'changed_lines': 10,
                 'findings': [{'severity': 'P1', 'source': 'escaped'}]})
        self.put(self.root / 'cases' / 'other.json', {'control': False, 'changed_lines': 10,
                 'findings': [{'severity': 'P1', 'source': 'escaped'}]})
        self.put(self.root / 'grades' / 'model' / 'batch.json', {'defect': {
            'r1': {'F1': {'pass': True}, 'p1': 0, 'p2': 1}}})
        args = argparse.Namespace(key=str(self.root / 'key.json'), grades=str(self.root / 'grades'),
                                  cases=str(self.root / 'cases'), out=str(self.root / 'summary.json'),
                                  p2_cutoff=[0, 1])

        report_tool.tally(args)

        group = json.loads((self.root / 'summary.json').read_text())['groups']['model']['arm']
        self.assertEqual(group['graded'], 1)
        self.assertEqual(group['status']['missing_grade'], 1)
        self.assertEqual(group['repetitions']['distinct_cases'], 2)
        self.assertEqual(group['cutoffs']['0']['serious_cases_merged']['case_all_repetitions_merged']['count'], 0)
        metric = group['cutoffs']['1']['serious_cases_merged']['case_all_repetitions_merged']
        self.assertEqual((metric['count'], metric['total'], metric['rate']), (1, 1, 1.0))
        self.assertIsNotNone(metric['wilson_95'])
        self.assertEqual(group['effort']['mean_seconds'], 7)


    def test_wilson_interval_is_absent_for_empty_denominator(self):
        self.assertIsNone(report_tool.interval(0, 0))
        self.assertEqual(report_tool.interval(4, 4)[1], 1.0)


if __name__ == '__main__':
    unittest.main()
