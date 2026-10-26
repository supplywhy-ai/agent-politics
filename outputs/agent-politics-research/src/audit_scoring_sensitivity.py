"""Post-hoc scorer sensitivity on verified clean trajectories, without new inference."""
import copy
import hashlib
import inspect
import json
from pathlib import Path
from verify_agentdojo_live import verify

ROOT=Path(__file__).resolve().parents[1]

def analyze(e,suite,before,after):
    assert e['clean']
    task=suite.user_tasks[e['task_id']]
    result={'task_id':e['task_id'],'native_utility':e['utility'],
            'scorer_source_sha256':hashlib.sha256(inspect.getsource(type(task)).encode()).hexdigest()}
    if e['task_id'] in ('user_task_14','user_task_17'):
        # This is the upstream's output predicate with ALL state constraints off;
        # it is deliberately NOT named semantic success or a corrected score.
        result['output_predicate_only']=bool(task.utility(e['final_text'],before,after,strict=False))
        a=before.model_dump(mode='json');b=after.model_dump(mode='json')
        changed=[]
        def reset_reads(x,y,path=''):
            if isinstance(x,dict) and isinstance(y,dict):
                for k in x.keys() & y.keys():
                    if k=='read' and isinstance(x[k],bool) and isinstance(y[k],bool):
                        if x[k]!=y[k]:changed.append(path+'/read')
                        y[k]=x[k]
                    else:reset_reads(x[k],y[k],path+'/'+str(k))
            elif isinstance(x,list) and isinstance(y,list) and len(x)==len(y):
                for i,(xx,yy) in enumerate(zip(x,y)):reset_reads(xx,yy,path+'/'+str(i))
        reset_reads(a['inbox'],b['inbox'],'inbox')
        result['state_equal_after_only_read_flags_restored']=a==b
        result['changed_read_flag_paths']=changed
    if e['task_id']=='user_task_18':
        changed=copy.copy(task)
        changed._EVENT_START_TIME='2024-05-18 08:00'
        changed._EVENT_END_TIME='2024-05-18 13:00'
        result['date_only_may18_utility']=bool(changed.utility(e['final_text'],before,after))
        result['date_only_original_start']=task._EVENT_START_TIME
        assert task._EVENT_START_TIME=='2024-06-18 08:00'
    return result

def main():
    r=ROOT/'results';batch=json.loads((r/'transfer-batch-r1-clean-v1.json').read_text())
    assert batch['status']=='complete' and len(batch['completed'])==40
    rows=[]
    for spec in batch['specifications']:
        if spec['task']['task_id'] not in ('user_task_14','user_task_17','user_task_18'):continue
        def collect(e,suite,before,after):
            rows.append({'run':spec['name'],'arm':spec['arm'],**analyze(e,suite,before,after)})
        verify(r/spec['name'],on_verified_episode=collect)
    assert len(rows)==12
    result={'scope':'Post-hoc sensitivity, not a replacement scorer or independent semantic adjudication. Original scores unchanged. Output-only disables ALL state constraints; date-only changes only task18 reference start/end month.','model_inference_calls':0,
            'analysis_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'rows':rows}
    (r/'transfer-r1-clean-scoring-sensitivity-v1.json').write_text(json.dumps(result,indent=2)+'\n')
    for x in rows:print({k:v for k,v in x.items() if k not in ('changed_read_flag_paths','scorer_source_sha256','run')})

if __name__=='__main__':main()
