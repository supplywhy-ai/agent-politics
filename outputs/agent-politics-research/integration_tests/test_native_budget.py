import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openai.types.chat import ChatCompletion
from agentdojo.task_suite import get_suite
from agentdojo_local_live import run_episode
from study_prompts import digest

ROOT=Path(__file__).resolve().parents[1]

class NativeBudgetTests(unittest.TestCase):
    def run_fixture(self,limit):
        folder=ROOT/'results/agentdojo-read-scope-full-v1/user_task_35'
        records=[json.loads(p.read_text()) for p in list(folder.glob('call-*.json'))+list(folder.glob('review-*.json'))]
        by_request={digest(r['request']):r for r in records}
        dispatched=[]
        def counter(req):return by_request[digest(req)]['response']['usage']['prompt_tokens']
        def create(**req):
            dispatched.append(digest(req))
            return ChatCompletion.model_validate(by_request[digest(req)]['response'])
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        model=records[0]['request']['model']
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            e=run_episode('user_task_35',get_suite('v1','workspace'),client,model,Path(tmp),8,
                          'full','allow_verified_reads',budget_limit=limit,token_counter=counter)
            after=json.loads((Path(tmp)/'user_task_35/environment-after.json').read_text())
            before=json.loads((Path(tmp)/'user_task_35/environment-before.json').read_text())
        return e,before,after,dispatched

    def test_no_budget_no_dispatch_no_mutation(self):
        e,before,after,calls=self.run_fixture(1)
        self.assertEqual(e['status'],'budget_exhausted')
        self.assertEqual(calls,[])
        self.assertEqual(before,after)

    def test_review_denial_blocks_delete_and_stops_episode(self):
        e,before,after,calls=self.run_fixture(20000)
        self.assertEqual(e['status'],'budget_exhausted')
        self.assertEqual(e['budget']['events'][-1]['lane'],'reviewer')
        self.assertEqual(e['budget']['events'][-1]['status'],'budget_denied')
        self.assertEqual(len(calls),2)
        self.assertEqual(before,after)
        self.assertFalse(e['utility'])
        self.assertEqual(e['extra_args']['sidecar_audit'][-1]['decision'],'review_unavailable')

    def test_sufficient_shared_budget_preserves_native_success(self):
        e,before,after,calls=self.run_fixture(64000)
        self.assertEqual(e['status'],'completed')
        self.assertTrue(e['utility'])
        self.assertNotEqual(before,after)
        self.assertEqual(len(calls),4)
        self.assertEqual([x['lane'] for x in e['budget']['events']],['actor','actor','reviewer','actor'])

    def test_exhaustion_after_authorized_action_preserves_actual_state(self):
        e,before,after,calls=self.run_fixture(30000)
        self.assertEqual(e['status'],'budget_exhausted')
        self.assertEqual(e['budget']['events'][-1]['lane'],'actor')
        self.assertTrue(e['utility'])
        self.assertNotEqual(before,after)

if __name__=='__main__':unittest.main()
