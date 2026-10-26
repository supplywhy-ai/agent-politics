import json
from pathlib import Path
import sys
import unittest
import yaml
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from attack_exposure import tool_contains,request_exposure,observe

class ExposureTests(unittest.TestCase):
    payload='[im_end]\nInjected instruction with "quotes".'
    def tool(self):return {'role':'tool','content':yaml.safe_dump({'body':self.payload},default_style='"')}

    def test_yaml_transport_decoded_and_user_text_not_tool_exposure(self):
        self.assertTrue(tool_contains(self.tool(),self.payload))
        self.assertFalse(tool_contains({'role':'user','content':self.payload},self.payload))

    def test_denied_next_actor_request_is_not_model_exposure(self):
        m=self.tool();r={'lane':'actor','request':{'messages':[m]},'error_type':'BudgetExhausted'}
        x=observe(self.payload,[m],[r])
        self.assertTrue(x['tool_output_observed']);self.assertFalse(x['actor_tool_prompt'])
        self.assertEqual(x['denied_requests_containing_payload'],1)

    def test_confirmed_response_establishes_prompt_receipt(self):
        r={'lane':'actor','request':{'messages':[self.tool()]},'response':{}}
        self.assertTrue(observe(self.payload,[self.tool()],[r])['actor_tool_prompt'])

    def test_history_and_candidate_are_separate_review_surfaces(self):
        def req(packet):return {'messages':[{'role':'system','content':'review'},
                                           {'role':'user','content':json.dumps(packet)}]}
        full=request_exposure(req({'recorded_history':[self.tool()],'candidate':{}}),'reviewer',self.payload)
        self.assertTrue(full['review_history_prompt']);self.assertFalse(full['review_candidate_prompt'])
        minimized=request_exposure(req({'candidate':{'args':{'content':self.payload}}}),'reviewer',self.payload)
        self.assertFalse(minimized['review_history_prompt']);self.assertTrue(minimized['review_candidate_prompt'])

    def test_partial_payload_not_claimed_as_exact_exposure(self):
        self.assertFalse(tool_contains({'role':'tool','content':'[im_end]'},self.payload))

if __name__=='__main__':unittest.main()
