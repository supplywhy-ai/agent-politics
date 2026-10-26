import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from openai.types.chat import ChatCompletion
from agentdojo.task_suite import get_suite
import agentdojo_local_live
from verify_agentdojo_live import verify

class DriveReplayTests(unittest.TestCase):
    def test_restore_observed_clocks_but_recompute_file_state(self):
        calls=0
        def create(**request):
            nonlocal calls
            calls+=1
            message={'role':'assistant','content':'Done.'}
            if calls==1:
                message={'role':'assistant','content':None,'tool_calls':[
                    {'id':'append-test','type':'function','function':{'name':'append_to_file',
                     'arguments':json.dumps({'file_id':'3','content':'\nNew test activity.'})}},
                    {'id':'create-test','type':'function','function':{'name':'create_file',
                     'arguments':json.dumps({'filename':'replay-test.txt','content':'Fixture text.'})}},
                    {'id':'calendar-test','type':'function','function':{'name':'create_calendar_event',
                     'arguments':json.dumps({'title':'Replay test','start_time':'2024-05-18 08:00',
                     'end_time':'2024-05-18 09:00','description':'Fixture invitation.',
                     'participants':['alice@example.com','bob@example.com']})}}]}
            return ChatCompletion.model_validate({'id':f'fixture-{calls}','object':'chat.completion','created':0,
                'model':'scripted-test','choices':[{'index':0,'finish_reason':'stop','message':message}],
                'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}})
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp)
            e=agentdojo_local_live.run_episode('user_task_29',get_suite('v1','workspace'),client,
                'scripted-test',root,8,'none','review_all')
            self.assertEqual(e['status'],'completed')
            self.assertTrue(all(t['error'] is None for t in e['tool_events']))
            source=Path(agentdojo_local_live.__file__).read_bytes();(root/'runner-source.py').write_bytes(source)
            manifest={'status':'complete','source_sha256':hashlib.sha256(source).hexdigest(),
                      'model_files_sha256':{},'suite_version':'v1','suite':'workspace','tasks':['user_task_29']}
            (root/'manifest.json').write_text(json.dumps(manifest))
            result=verify(root)
            self.assertEqual(result['tasks'][0]['restored_drive_clock_values'],2)
            self.assertEqual(result['tasks'][0]['restored_send_clock_values'],1)
            after=root/'user_task_29/environment-after.json'
            original=after.read_text();data=json.loads(original)
            before=json.loads((root/'user_task_29/environment-before.json').read_text())
            new_mail=set(data['inbox']['emails'])-set(before['inbox']['emails'])
            self.assertEqual(len(new_mail),1)
            data['inbox']['emails'][new_mail.pop()]['body']='tampered invitation'
            after.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):verify(root)
            data=json.loads(original);data['cloud_drive']['files']['3']['content']='tampered'
            after.write_text(json.dumps(data))
            with self.assertRaises(AssertionError):verify(root)

if __name__=='__main__':unittest.main()
