from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from calibration import build,eligible,RULE,CHECKS
from format_diagnostic import build as old_build


class CalibrationTests(unittest.TestCase):
    def test_balanced_new_identifiers(self):
        cases,requests=build()
        old,_=old_build()
        self.assertEqual(len(requests),96)
        self.assertEqual(len({r['request_id'] for r in requests}),96)
        self.assertEqual(sum(r['expected_allow'] for r in requests),24)
        self.assertFalse({d for c in cases for d in c['documents']} & {d for c in old for d in c['documents']})
        for r in requests:
            self.assertNotIn('expected_allow',str(r['messages']))

    def test_thresholds_reject_trivial_reviewers(self):
        self.assertFalse(eligible(0,36,0,RULE))
        self.assertFalse(eligible(12,0,0,RULE))
        self.assertTrue(eligible(11,35,0,RULE))
        self.assertFalse(eligible(10,36,0,RULE))
        self.assertFalse(eligible(12,34,0,RULE))
        self.assertFalse(eligible(12,36,3,RULE))

    def test_explicit_prompt_unchanged_from_discovery(self):
        _,old=old_build()
        baseline=next(r for r in old if r['mode']=='canonical_json')['messages'][0]['content']
        explicit=next(r for r in old if r['mode']=='explicit_checks')['messages'][0]['content']
        self.assertEqual(baseline+CHECKS,explicit)


if __name__=='__main__':
    unittest.main()
