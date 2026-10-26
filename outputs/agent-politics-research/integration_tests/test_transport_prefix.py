import json,os,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from verify_agentdojo_live import verify
class TransportPrefixTests(unittest.TestCase):
 def setUp(self):
  os.environ['PYTHONHASHSEED']='20261025'
  self.temp=tempfile.TemporaryDirectory();self.run=Path(self.temp.name)/'run'
  shutil.copytree(ROOT/'results/agentdojo-transfer-r3-hardened-clean-user_task_34-v1',self.run)
 def tearDown(self):self.temp.cleanup()
 def test_requires_explicit_opt_in(self):
  with self.assertRaises(AssertionError):verify(self.run)
  v=verify(self.run,allow_transport_error=True)['tasks'][0]
  self.assertTrue(v['state_replay_equal']);self.assertTrue(v['transport_failure_preserved'])
  self.assertFalse(v['actual_token_usage_complete'])
 def test_changed_failed_prompt_rejected(self):
  p=self.run/'user_task_34/budget-call-02.json';d=json.loads(p.read_text());d['request']['messages'][-1]['content']='tampered';p.write_text(json.dumps(d))
  with self.assertRaises(AssertionError):verify(self.run,allow_transport_error=True)
 def test_missing_failed_receipt_rejected(self):
  (self.run/'user_task_34/budget-call-02.json').unlink()
  with self.assertRaises(AssertionError):verify(self.run,allow_transport_error=True)
 def test_changed_terminal_state_rejected(self):
  p=self.run/'user_task_34/episode.json';d=json.loads(p.read_text());d['utility']=True;p.write_text(json.dumps(d))
  with self.assertRaises(AssertionError):verify(self.run,allow_transport_error=True)
if __name__=='__main__':unittest.main()
