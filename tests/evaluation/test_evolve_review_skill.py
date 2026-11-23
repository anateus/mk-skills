import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/evolve-review-skill.py'
SPEC = importlib.util.spec_from_file_location('evolve_review_skill', SCRIPT)
evolve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evolve)


class EvolveReviewSkillTests(unittest.TestCase):
    def test_score_and_derived_verdict(self):
        self.assertEqual([evolve.derive_verdict(count) for count in (0, 1, 2)], ['merge', 'block', 'block'])
        self.assertEqual(evolve.score_outcome(True, False, 'merge', 0, 1)[0], 1.0)
        self.assertEqual(evolve.score_outcome(True, False, 'block', 0, 1)[0], 0.2)
        self.assertEqual(evolve.score_outcome(False, True, 'merge', 1, 1)[0], 0.0)
        self.assertEqual(evolve.score_outcome(False, True, 'block', 1, 1)[0], 1.0)
        self.assertEqual(evolve.score_outcome(False, False, 'merge', 1, 2)[0], 0.75)

    def test_report_parsing_aggregation_and_model_scoped_judge_key(self):
        self.assertEqual(evolve.parse_report('Verdict: block\nRisk: medium\nOutcome: defect\nVerdict: merge\n'),
                         {'risk': 'medium', 'outcome': 'defect', 'verdict': 'merge'})
        scores, missing = evolve.aggregate([1.0, None, 0.0, 0.0])
        self.assertEqual(missing, [1])
        self.assertAlmostEqual(scores[1], 1.0 / 3)
        with self.assertRaises(evolve.NotRunError):
            evolve.aggregate([None, None])
        criteria = [{'id': 'F1', 'criterion': 'detect the issue'}]
        parsed = {'F1': {'pass': True, 'note': 'Found it'}, 'p1': 0}
        self.assertEqual(evolve.parse_judge(json.dumps(parsed), ['F1']), parsed)
        self.assertNotEqual(evolve.judge_key('report', criteria, 'model-a'),
                            evolve.judge_key('report', criteria, 'model-b'))
        self.assertEqual(evolve.generic_line('P1: `private.py:12` at src/module.py'), 'P1: <code> at <path>')
        self.assertEqual(evolve.p1_lines('P1: issue\nNo P1 findings\nP1 findings: none'), ['P1: issue'])

    def test_split_requires_exact_disjoint_nonempty_coverage(self):
        cases = {case_id: object() for case_id in ('case-a', 'case-b', 'case-c')}
        with tempfile.TemporaryDirectory() as directory:
            split_path = Path(directory) / 'split.json'
            split_path.write_text(json.dumps({'train': ['case-a'], 'val': ['case-b'], 'test': ['case-c']}))
            self.assertEqual(evolve.load_split(split_path, cases)['test'], ['case-c'])
            split_path.write_text(json.dumps({'train': ['case-a'], 'val': ['case-a'], 'test': ['case-c']}))
            with self.assertRaisesRegex(ValueError, 'exactly once'):
                evolve.load_split(split_path, cases)
            split_path.write_text(json.dumps({'train': ['case-a'], 'val': ['case-b'], 'test': []}))
            with self.assertRaisesRegex(ValueError, 'nonempty'):
                evolve.load_split(split_path, cases)

    def test_private_path_check_resolves_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / 'checkout-link'
            link.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaisesRegex(SystemExit, 'outside this checkout'):
                evolve.outside_checkout(link, 'output')

    def test_corpus_term_denylist_positive_and_seed_allowance(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            skill_dir = tree / 'skills' / 'sample'
            skill_dir.mkdir(parents=True)
            seed = '---\nname: sample\ndescription: Sample skill.\n---\n\nUse generic review guidance.\n'
            (skill_dir / 'SKILL.md').write_text(seed)
            case = SimpleNamespace(title='Investigate ZorblaxCache behavior', criteria=[], findings={})
            denied = evolve.build_denylist({'case-a': case}, tree)
            self.assertIn('ZorblaxCache', denied)
            self.assertEqual(evolve.validate_candidate(seed, seed, denied), [])
            changed_frontmatter = seed.replace('name: sample', 'name: other', 1)
            self.assertTrue(any('frontmatter changed' in issue
                                for issue in evolve.validate_candidate(changed_frontmatter, seed, denied)))
            bad = seed + '\nInvestigate ZorblaxCache behavior.\n'
            self.assertTrue(any('terms taken' in issue for issue in evolve.validate_candidate(bad, seed, denied)))


if __name__ == '__main__':
    unittest.main()
