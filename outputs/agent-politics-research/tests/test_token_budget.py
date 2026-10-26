import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from token_budget import TokenBudget,BudgetExhausted,AccountingError


class BudgetTests(unittest.TestCase):
    def test_actor_and_reviewer_share_budget_and_unused_reservation_returns(self):
        b=TokenBudget(30,lambda r:10)
        def api(r):return {'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}}
        b.call({'max_tokens':10},'actor',api)
        self.assertEqual(b.used,12)
        b.call({'max_tokens':8},'reviewer',api)
        self.assertEqual(b.used,24)
        with self.assertRaises(BudgetExhausted):
            b.call({'max_tokens':1},'actor',lambda r:self.fail('must not dispatch'))
        self.assertEqual(b.used,24)
        self.assertFalse(b.events[-1]['dispatched'])

    def test_exact_boundary_is_admitted_but_full_output_must_fit(self):
        b=TokenBudget(15,lambda r:10)
        with self.assertRaises(BudgetExhausted):
            b.call({'max_tokens':6},'actor',lambda r:self.fail('must not dispatch'))
        b.call({'max_tokens':5},'actor',lambda r:{'usage':{
            'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}})
        self.assertEqual(b.used,15)

    def test_network_failure_consumes_reservation_and_closes_ledger(self):
        b=TokenBudget(30,lambda r:10)
        def fail(r):raise TimeoutError('unknown server outcome')
        with self.assertRaises(TimeoutError):b.call({'max_tokens':5},'reviewer',fail)
        self.assertEqual(b.used,15)
        with self.assertRaises(AccountingError):
            b.call({'max_tokens':1},'actor',lambda r:self.fail('must not retry'))

    def test_bad_usage_fails_closed(self):
        for usage in ({'prompt_tokens':9,'completion_tokens':1,'total_tokens':10},
                      {'prompt_tokens':10,'completion_tokens':6,'total_tokens':16},
                      {'prompt_tokens':10,'completion_tokens':1,'total_tokens':12}):
            b=TokenBudget(30,lambda r:10)
            with self.assertRaises(AccountingError):
                b.call({'max_tokens':5},'actor',lambda r:{'usage':usage})
            self.assertTrue(b.closed)
            self.assertEqual(b.used,15)

    def test_request_is_copied_and_snapshot_cannot_mutate_ledger(self):
        b=TokenBudget(30,lambda r:10)
        original={'max_tokens':5,'messages':[{'content':'trusted'}]}
        def api(r):
            r['messages'][0]['content']='changed'
            return {'usage':{'prompt_tokens':10,'completion_tokens':1,'total_tokens':11}}
        b.call(original,'actor',api)
        self.assertEqual(original['messages'][0]['content'],'trusted')
        snapshot=b.snapshot();snapshot['events'].clear()
        self.assertEqual(len(b.events),1)

if __name__=='__main__':unittest.main()
