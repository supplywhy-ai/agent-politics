import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from agentdojo.task_suite import get_suite
from agentdojo.functions_runtime import FunctionsRuntime
from read_policy import policy_receipt, VERIFIED_READS


class ReadPolicyTests(unittest.TestCase):
    def test_named_implementations_leave_fixture_state_unchanged(self):
        suite=get_suite('v1','workspace')
        env=suite.load_and_inject_default_environment({})
        before=env.model_copy(deep=True)
        runtime=FunctionsRuntime(suite.tools)
        examples={'list_files':{},'search_files_by_filename':{'filename':'feedback.xlsx'},
                  'search_calendar_events':{'query':'Networking event','date':'2024-05-26'},
                  'get_day_calendar_events':{'day':'2024-05-26'}}
        self.assertEqual(set(examples),VERIFIED_READS)
        for name,args in examples.items():
            _,error=runtime.run_function(env,name,args)
            self.assertIsNone(error)
            self.assertEqual(env,before)
            self.assertIsNotNone(policy_receipt({'candidate':{'function':name,'args':args}}))

    def test_mutating_and_unknown_tools_cannot_bypass_review(self):
        for name in ('delete_file','send_email','share_file','get_unread_emails','list_files_and_delete'):
            self.assertIsNone(policy_receipt({'candidate':{'function':name,'args':{}}}))


if __name__=='__main__':
    unittest.main()
