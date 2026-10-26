import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from agentdojo_local_live import wire_messages
from agentdojo.functions_runtime import FunctionCall
from agentdojo.types import text_content_block_from_string as block


class LocalWireTests(unittest.TestCase):
    def test_native_roles_and_tool_ids_preserved(self):
        call=FunctionCall(function='search',args={'query':'fictional'},id='call_1')
        messages=[{'role':'system','content':[block('policy')]},
                  {'role':'assistant','content':None,'tool_calls':[call]},
                  {'role':'tool','content':[block('result')],'tool_call_id':'call_1',
                   'tool_call':call,'error':None}]
        result=wire_messages(messages)
        self.assertEqual([m['role'] for m in result],['system','assistant','tool'])
        self.assertEqual(result[1]['tool_calls'][0]['id'],result[2]['tool_call_id'])
        self.assertEqual(result[2]['content'],'result')

    def test_tool_error_is_returned_to_model(self):
        result=wire_messages([{'role':'tool','content':[block('None')],
                              'tool_call_id':'call_1','error':'blocked'}])
        self.assertEqual(result[0]['content'],'blocked')


if __name__=='__main__':
    unittest.main()
