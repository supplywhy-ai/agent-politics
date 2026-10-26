import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from format_diagnostic import build


class FormatTests(unittest.TestCase):
    def test_factorial_and_labels(self):
        cases,reqs=build()
        self.assertEqual(len(reqs),48)
        self.assertEqual(len({r['request_id'] for r in reqs}),48)
        tasks={c['case_id']:c['task'] for c in cases}
        for r in reqs:
            a=r['candidate']; t=tasks[r['case_id']]
            expected=a['recipient']==t['recipient'] and a['document_id']==t['document_id']
            self.assertEqual(r['expected_allow'],expected)
            self.assertNotIn('expected_allow',str(r['messages']))

    def test_json_order_changes_only_order(self):
        _,reqs=build()
        for a,b in zip(reqs[::4],reqs[1::4]):
            self.assertEqual(a['messages'][0],b['messages'][0])
            self.assertNotEqual(a['messages'][1]['content'],b['messages'][1]['content'])
            self.assertEqual(json.loads(a['messages'][1]['content']),json.loads(b['messages'][1]['content']))


if __name__=='__main__':
    unittest.main()
