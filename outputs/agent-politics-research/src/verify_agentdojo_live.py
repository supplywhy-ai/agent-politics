"""Replay saved native tool trajectories without model calls and check final state."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import yaml
from openai.types.chat import ChatCompletionMessage
from agentdojo.agent_pipeline.llms.openai_llm import _openai_to_assistant_message
from agentdojo.agent_pipeline.tool_execution import ToolsExecutor
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite import get_suite
from agentdojo.agent_pipeline.agent_pipeline import load_system_message
from agentdojo_gate import GatedToolsExecutor,serializable
from agentdojo.types import get_text_content_as_str
from agentdojo_local_live import wire_messages
from study_prompts import digest, decode_review
from read_policy import policy_receipt
from agentdojo.default_suites.v1.tools import email_client
from agentdojo.default_suites.v1.tools import cloud_drive_client
from token_budget import TokenBudget,BudgetExhausted


def file_hash(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def verify(run,on_verified_episode=None,allow_transport_error=False):
    read=lambda p:json.loads(p.read_text())
    m=read(run/'manifest.json')
    assert m['status']=='complete'
    if m.get('python_hash_seed') is not None:
        assert os.environ.get('PYTHONHASHSEED')==m['python_hash_seed'], 'Replay must use recorded PYTHONHASHSEED'
    assert file_hash(run/'runner-source.py')==m['source_sha256']
    if 'read_policy_source_sha256' in m:
        assert file_hash(run/'read-policy-source.py')==m['read_policy_source_sha256']
    for name,expected in m.get('budget_sources_sha256',{}).items():
        assert file_hash(run/name)==expected
    for name,expected in m['model_files_sha256'].items():
        assert file_hash(Path(m['model_path'])/name)==expected
    suite=get_suite(m['suite_version'],m['suite'])
    verified=[]
    for episode_id in m.get('episode_ids',m['tasks']):
        folder=run/episode_id
        e=read(folder/'episode.json')
        task_id=e['task_id']
        transport_error=e['status']=='error'
        if transport_error:
            assert allow_transport_error, 'Transport errors require explicit prefix verification'
            assert e['clean'] and e['review_mode']=='none'
            assert e['error']['type'] in ('APITimeoutError','APIConnectionError')
        else:
            assert e['status']!='accounting_error'
        if m.get('token_budget') is not None:
            ledger=read(folder/'budget.json')
            assert ledger==e['budget'] and ledger['closed']==transport_error
            assert ledger['limit']==m['token_budget']
            replay=TokenBudget(m['token_budget'],lambda r:prompt)
            records=sorted(folder.glob('budget-call-*.json'))
            assert len(records)==len(ledger['events'])
            settled=[]
            for index,(path,event) in enumerate(zip(records,ledger['events'])):
                data=read(path);prompt=event['prompt_tokens']
                def dispatch_recorded(request):
                    if event['status']=='uncertain_failure':
                        assert transport_error and index==len(records)-1
                        assert data['lane']=='actor' and 'response' not in data
                        assert data['error_type']==e['error']['type']==event['error_type']
                        raise type(data['error_type'],(RuntimeError,),{})('recorded transport failure')
                    return data['response']
                try:replay.call(data['request'],data['lane'],dispatch_recorded)
                except BudgetExhausted:
                    assert data['error_type']=='BudgetExhausted' and 'response' not in data
                    assert index==len(records)-1 and e['status']=='budget_exhausted'
                except RuntimeError as exc:
                    assert transport_error and type(exc).__name__==e['error']['type']
                    assert event['status']=='uncertain_failure' and index==len(records)-1
                else:settled.append((digest(data['request']),digest(data['response'])))
            assert replay.snapshot()==ledger
            expected=[(r['request_hash'],r['response_hash']) for r in e['calls']+e['review_calls'] if 'response_hash' in r]
            assert sorted(settled)==sorted(expected)
        env_class=type(suite.load_and_inject_default_environment({}))
        before_raw=read(folder/'environment-before.json')
        before=env_class.model_validate(before_raw)
        assert before.model_dump(mode='json')==before_raw
        assert suite.load_and_inject_default_environment(e.get('injections',{})).model_dump(mode='json')==before_raw
        # Upstream after-validators rebuild live maps from initial_* collections.
        # Validating a final snapshot would silently resurrect deleted objects.
        after_raw=read(folder/'environment-after.json')
        env=before.model_copy(deep=True)
        runtime=FunctionsRuntime(suite.tools)
        saved_messages=read(folder/'messages.json')
        messages=saved_messages[:2]
        expected_system=load_system_message(None)
        if m.get('executor_hardened',False):
            expected_system+='\n'+m['executor_hardening_prompt']
        assert e.get('executor_hardened',False)==m.get('executor_hardened',False)
        assert wire_messages(messages)==[
            {'role':'system','content':expected_system},
            {'role':'user','content':suite.user_tasks[task_id].PROMPT}]
        # Replay only: native send_email stamps wall time. Restore the observed
        # clock values, never the returned action arguments or final state.
        # Calendar tools can send invitation mail without returning its timestamp.
        # Restore only these observed clock values; all email fields are recomputed
        # by the original tool. Final-state-only clock values are replay inputs,
        # not independently validated timestamp outputs.
        mail_observations=[yaml.safe_load(x['content'][0]['content'])
                           for x in saved_messages if x['role']=='tool' and not x['error']
                           and x['tool_call']['function']=='send_email']
        before_mail=before_raw['inbox']['emails']
        for key,value in after_raw['inbox']['emails'].items():
            if key not in before_mail or value['timestamp']!=before_mail[key]['timestamp']:
                mail_observations.append(value)
        mail_clocks={}
        for observation in mail_observations:
            stamp=observation['timestamp']
            if isinstance(stamp,str):stamp=datetime.datetime.fromisoformat(stamp)
            mail_clocks.setdefault(str(observation['id_']),set()).add(stamp)
        mail_clocks={key:sorted(values) for key,values in mail_clocks.items()}
        mail_times=[stamp for values in mail_clocks.values() for stamp in values]
        clock_index=0
        drive_times=[yaml.safe_load(x['content'][0]['content'])['last_modified']
                     for x in saved_messages if x['role']=='tool' and not x['error']
                     and x['tool_call']['function'] in ('create_file','append_to_file')]
        drive_clock_index=0
        class RecordedDateTime(datetime.datetime):
            @classmethod
            def now(cls,tz=None):
                nonlocal clock_index
                key=str(env.inbox._get_next_id())
                assert mail_clocks.get(key),f'No observed clock for generated email {key}'
                observed=mail_clocks[key].pop(0)
                clock_index+=1
                return observed if tz is None else observed.astimezone(tz)
        class RecordedDriveDateTime(datetime.datetime):
            @classmethod
            def now(cls,tz=None):
                nonlocal drive_clock_index
                observed=drive_times[drive_clock_index]
                drive_clock_index+=1
                return observed if tz is None else observed.astimezone(tz)
        reviews=e.get('review_calls',[])
        for review in reviews:
            receipt=read(folder/f"review-{review['index']:02d}.json")
            assert digest(receipt['request'])==review['request_hash']
            assert receipt['request']['messages'][0]=={'role':'system','content':m['review_policy']}
            if 'error' in receipt:
                assert review['error_type']=='BudgetExhausted' and review['decision'] is None
                assert e['status']=='budget_exhausted'
                continue
            assert digest(receipt['response'])==review['response_hash']
            response=receipt['response']['choices'][0]
            decision=decode_review(response['message']['content']) if response['finish_reason']!='length' else None
            assert decision==review['decision']
        review_index=0
        replay_policy=[]
        review_stopped=False
        def recorded_review(packet_json):
            nonlocal review_index,review_stopped
            receipt=policy_receipt(json.loads(packet_json)) if e.get('read_policy')=='allow_verified_reads' and not review_stopped else None
            if receipt is not None:
                replay_policy.append(receipt)
                return True
            record=reviews[review_index]
            decision=record['decision']
            review_index+=1
            if 'error_type' in record:
                review_stopped=True
                raise BudgetExhausted('recorded review budget denial')
            return decision
        executor=GatedToolsExecutor(recorded_review) if e.get('review_mode','none')!='none' else ToolsExecutor()
        extras={}
        final_text=''
        for call in e['calls']:
            data=read(folder/f"call-{call['step']:02d}.json")
            assert digest(data['request'])==call['request_hash']
            assert digest(data['response'])==call['response_hash']
            assert data['request']['messages']==wire_messages(messages)
            response=data['response']['choices'][0]
            output=_openai_to_assistant_message(ChatCompletionMessage.model_validate(response['message']))
            messages.append(output)
            final_text=get_text_content_as_str(output['content']) if output['content'] else ''
            if response['finish_reason']=='length' or not output.get('tool_calls'):
                break
            with patch.object(email_client,'datetime',SimpleNamespace(datetime=RecordedDateTime)), \
                 patch.object(cloud_drive_client,'datetime',SimpleNamespace(datetime=RecordedDriveDateTime)):
                _,_,env,messages,extras=executor.query(e['trusted_request'],runtime,env,messages,extras)
        assert env.model_dump(mode='json')==after_raw
        assert json.loads(json.dumps(messages,default=serializable))==saved_messages
        assert final_text==e['final_text']
        if transport_error:
            failed=read(records[-1])
            assert failed['request']['messages']==wire_messages(messages)
            assert failed['request']['max_tokens']==512
            assert ledger['events'][-1]['status']=='uncertain_failure'
            assert ledger['events'][-1]['lane']=='actor'
        assert review_index==len(reviews)
        assert replay_policy==e.get('policy_decisions',[])
        assert clock_index==len(mail_times)
        assert drive_clock_index==len(drive_times)
        assert extras.get('sidecar_audit',[])==e['extra_args'].get('sidecar_audit',[])
        assert bool(suite.user_tasks[task_id].utility(e['final_text'],before,env))==e['utility']
        if e.get('injection_task'):
            assert bool(suite.injection_tasks[e['injection_task']].security(e['final_text'],before,env))==e['attack_success']
        else:
            assert e['attack_success'] is None
        if on_verified_episode is not None:
            # Analysis gets copies only, after native state and score equality.
            on_verified_episode(e, suite, before.model_copy(deep=True), env.model_copy(deep=True))
        verified.append({'episode_id':episode_id,'task_id':task_id,'utility':e['utility'],
                         'attack_success':e['attack_success'],'transport_failure_preserved':transport_error,
                         'actual_token_usage_complete':not transport_error,'restored_send_clock_values':len(mail_times),
                         'restored_drive_clock_values':len(drive_times),
                         'executor_calls':len(e['calls']),
                         'review_calls':sum('usage' in r for r in reviews),'state_replay_equal':True,
                         'native_message_history_replay_equal':True,'audit_replay_equal':True})
    out={'runner_source_hash_verified':True,'model_file_hashes_verified':True,'tasks':verified,
         'verifier_source_sha256':file_hash(Path(__file__)),
         'clock_replay_note':'Observed mail/file timestamps are replay inputs; invitation-only timestamps may come from final state and are not independently validated. All other fields are recomputed by native tools.',
         'verification_model_calls':0,'scope':'Recorded-decision replay and original benchmark scorer, not independent semantic grading.'}
    (run/'verification.json').write_text(json.dumps(out,indent=2)+'\n')
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--runs',nargs='+',required=True,type=Path)
    args=p.parse_args()
    for run in args.runs:
        print(run,json.dumps(verify(run)))
