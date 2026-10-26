import json
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from development_cases import build
from reviewer_probes import prepare_probes, score_probes


class ProbeTests(unittest.TestCase):
    def test_balanced_unique_and_no_evaluator_metadata(self):
        requests = prepare_probes(build())
        self.assertEqual(len(requests), 126)
        self.assertEqual(len({r['request_id'] for r in requests}), 126)
        self.assertEqual(sum(r['expected_allow'] for r in requests), 42)
        for r in requests:
            message = json.loads(r['messages'][-1]['content'])
            self.assertNotIn('expected_allow', message)
            self.assertNotIn('probe_kind', message)
            if r['mode'] == 'independent_minimized':
                self.assertNotIn('recorded_history', message)

    def test_perfect_and_wrong_decisions(self):
        req = prepare_probes(build()[:1])
        perfect = [{'request_id': r['request_id'], 'origin': 'scripted_test',
                    'text': json.dumps({'allow': r['expected_allow']})} for r in req]
        rows = score_probes(req, perfect)['rows']
        self.assertFalse(any(r['unsafe_allow'] or r['false_block'] for r in rows))
        wrong = [{**r, 'text': '{"allow":true}'} for r in perfect]
        self.assertEqual(sum(r['unsafe_allow'] for r in score_probes(req, wrong)['rows']), 6)

    def test_invalid_and_missing_are_separate(self):
        req = prepare_probes(build()[:1])
        rows = score_probes(req, [{'request_id': req[0]['request_id'],
                                'origin': 'scripted_test', 'text': 'invalid'}])['rows']
        self.assertTrue(rows[0]['invalid'])
        self.assertFalse(rows[0]['false_block'])
        self.assertEqual(sum(r['missing'] for r in rows), 8)


if __name__ == '__main__':
    unittest.main()
