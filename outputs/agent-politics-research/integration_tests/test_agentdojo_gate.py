import json
import sys
import unittest
from pathlib import Path
from typing import Annotated
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from agentdojo_gate import GatedToolsExecutor
from agentdojo.functions_runtime import Depends, FunctionCall, FunctionsRuntime, TaskEnvironment, make_function
from pydantic import Field


class Ledger(TaskEnvironment):
    entries: list[str] = Field(default_factory=list)


class World(TaskEnvironment):
    ledger: Ledger = Field(default_factory=Ledger)


def record(ledger: Annotated[Ledger, Depends('ledger')], value: str) -> str:
    """Record a fictional delivery.

    :param value: Fictional delivery recipient.
    """
    ledger.entries.append(value)
    return 'recorded'


class GateIntegration(unittest.TestCase):
    def setUp(self):
        self.runtime = FunctionsRuntime([make_function(record)])
        self.env = World()
        self.messages = [{'role':'assistant','content':None,
                          'tool_calls':[FunctionCall(function='record',args={'value':'authorized'},id='call_1')]}]

    def run_gate(self,reviewer,messages=None):
        return GatedToolsExecutor(reviewer).query('Record authorized',self.runtime,self.env,
                                                  self.messages if messages is None else messages,{})

    def test_allow_reaches_actual_upstream_runtime(self):
        result = self.run_gate(lambda _: True)
        self.assertEqual(self.env.ledger.entries,['authorized'])
        self.assertIs(result[1],self.runtime)
        self.assertEqual(result[3][-1]['tool_call_id'],'call_1')
        self.assertIsNone(result[3][-1]['error'])

    def test_deny_and_malformed_have_no_side_effect(self):
        for decision,status in [(False,'blocked'),('true','invalid_review'),(None,'invalid_review'),(1,'invalid_review')]:
            with self.subTest(decision=decision):
                result = self.run_gate(lambda _: decision)
                self.assertEqual(self.env.ledger.entries,[])
                self.assertEqual(result[4]['sidecar_audit'][0]['decision'],status)
                self.assertIn(status,result[3][-1]['error'])

    def test_review_failure_blocks(self):
        def unavailable(_):
            raise TimeoutError('scripted timeout')
        result = self.run_gate(unavailable)
        self.assertEqual(self.env.ledger.entries,[])
        self.assertEqual(result[4]['sidecar_audit'][0]['decision'],'review_unavailable')

    def test_reviewer_cannot_change_approved_candidate(self):
        def mutate_copy(packet):
            decoded = json.loads(packet)
            self.assertNotIn('env',decoded)
            decoded['candidate']['args']['value'] = 'attacker'
            return True
        self.run_gate(mutate_copy)
        self.assertEqual(self.env.ledger.entries,['authorized'])

    def test_each_call_in_batch_is_checked(self):
        self.messages[0]['tool_calls'].append(FunctionCall(function='record',args={'value':'attacker'},id='call_2'))
        result = self.run_gate(lambda packet: json.loads(packet)['candidate']['args']['value']=='authorized')
        self.assertEqual(self.env.ledger.entries,['authorized'])
        self.assertEqual([a['decision'] for a in result[4]['sidecar_audit']],['allowed','blocked'])
        self.assertEqual([m['tool_call_id'] for m in result[3][-2:]],['call_1','call_2'])

    def test_no_action_requires_no_review(self):
        def must_not_call(_):
            self.fail('No-action message was reviewed')
        result = self.run_gate(must_not_call,[{'role':'assistant','content':[],'tool_calls':None}])
        self.assertEqual(result[4]['sidecar_audit'],[])

    def test_nested_calls_rejected_explicitly(self):
        self.messages[0]['tool_calls'][0].args['value'] = FunctionCall(function='record',args={'value':'attacker'})
        result = self.run_gate(lambda _: True)
        self.assertEqual(self.env.ledger.entries,[])
        self.assertEqual(result[4]['sidecar_audit'][0]['decision'],'unsupported_nested_call')

    def test_upstream_workspace_email_side_effect_and_attack_scorer(self):
        from agentdojo.task_suite import get_suite
        suite = get_suite('v1','workspace')
        attack = suite.injection_tasks['injection_task_0']
        for decision in (True,False):
            with self.subTest(allow=decision):
                env = suite.load_and_inject_default_environment({})
                before = env.model_copy(deep=True)
                calls = attack.ground_truth(env)
                messages = [{'role':'assistant','content':None,'tool_calls':calls}]
                result = GatedToolsExecutor(lambda _: decision).query(
                    'Summarize the requested calendar event.',FunctionsRuntime(suite.tools),env,messages,{})
                self.assertEqual(attack.security('',before,result[2]),decision)
                self.assertEqual(len(result[2].inbox.emails)-len(before.inbox.emails),int(decision))


if __name__ == '__main__':
    unittest.main()
