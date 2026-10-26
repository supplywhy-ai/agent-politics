"""Run a frozen transfer cohort sequentially, with randomized task/arm order."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];WORKSPACE=ROOT.parents[1]
FLAGS={'ordinary':[],'hardened':['--executor-hardened'],
       'full':['--review','full','--read-policy','allow_verified_reads'],
       'minimized':['--review','minimized','--read-policy','allow_verified_reads']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--repetition',type=int,choices=[1,2,3],required=True)
    p.add_argument('--cohort',choices=['clean','attack'],required=True);a=p.parse_args()
    plan_path=ROOT/'fixtures/task-transfer-v1/plan.json';plan=json.loads(plan_path.read_text())
    for task in plan['tasks']:
        assert hashlib.sha256(Path(task['fixture']).read_bytes()).hexdigest()==task['sha256']
    prior=[]
    for rep in range(1,a.repetition):prior += [(rep,'clean'),(rep,'attack')]
    if a.cohort=='attack':prior.append((a.repetition,'clean'))
    for rep,cohort in prior:
        previous=ROOT/'results'/f'transfer-batch-r{rep}-{cohort}-v1.json'
        assert json.loads(previous.read_text())['status']=='complete'
    names=['agentdojo_local_live.py','agentdojo_gate.py','read_policy.py','native_budget.py',
           'token_budget.py','count_native_tokens.py','run_transfer_batch.py']
    sources={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in names}
    model=json.loads((ROOT/'results/calibration-qwen-v1/manifest.json').read_text())
    execution={'plan_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),
               'sources_sha256':sources,'model_id':model['model_id'],'model_files_sha256':model['model_files_sha256'],
               'python_hash_seed':'20261025','server_prompt_cache_size':10,
               'scope':'Frozen execution specification for transfer study. Verify with matching PYTHONHASHSEED.'}
    specification=ROOT/'fixtures/task-transfer-v1/execution-spec.json'
    if specification.exists():assert json.loads(specification.read_text())==execution,'Execution specification changed'
    else:specification.write_text(json.dumps(execution,indent=2)+'\n')
    specs=[]
    for arm in plan['arms']:
        for task in plan['tasks']:
            name=f"agentdojo-transfer-r{a.repetition}-{arm}-{a.cohort}-{task['task_id']}-v1"
            specs.append({'name':name,'arm':arm,'task':task})
    random.Random(plan['seed']+a.repetition*100+(a.cohort=='attack')).shuffle(specs)
    assert all(not (ROOT/'results'/s['name']).exists() for s in specs)
    batch=ROOT/'results'/f'transfer-batch-r{a.repetition}-{a.cohort}-v1.json';assert not batch.exists()
    record={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),
            'execution_spec_sha256':hashlib.sha256(specification.read_bytes()).hexdigest(),
            'specifications':specs,'completed':[],'repetition':a.repetition,'cohort':a.cohort}
    def save():batch.write_text(json.dumps(record,indent=2)+'\n')
    save()
    env=dict(os.environ,PYTHONHASHSEED=execution['python_hash_seed'],HF_HUB_OFFLINE='1',
             HF_HOME=str(WORKSPACE/'work/hf-cache'))
    base=[sys.executable,'-u',str(Path(__file__).with_name('agentdojo_local_live.py')),
          '--model-path',str(WORKSPACE/'work/models/qwen3-4b-instruct-2507-4bit'),
          '--model-manifest',str(ROOT/'results/calibration-qwen-v1/manifest.json'),
          '--token-counter-python',str(WORKSPACE/'work/mlx-venv/bin/python'),
          '--token-budget',str(plan['token_budget']),'--max-steps',str(plan['max_actor_steps'])]
    for s in specs:
        out=ROOT/'results'/s['name']
        extra=['--tasks',s['task']['task_id']] if a.cohort=='clean' else ['--attack-fixture',s['task']['fixture']]
        print('Starting',s['name'],flush=True)
        with (WORKSPACE/'work'/f"{s['name']}.log").open('w') as log:
            subprocess.run(base+['--out',str(out)]+FLAGS[s['arm']]+extra,env=env,
                           stdout=log,stderr=subprocess.STDOUT,check=True)
        summaries=json.loads((out/'summary.json').read_text())
        errors=[r for r in summaries if r['status'] in ('error','accounting_error')]
        if errors:
            record.update(status='needs_attention',failed_run=s['name'],errors=errors);save()
            raise RuntimeError('Preserved run error; inspect before continuing')
        record['completed'].append(s['name']);save()
        print('Completed',s['name'],flush=True)
    record.update(status='complete',finished_utc=datetime.now(timezone.utc).isoformat());save()

if __name__=='__main__':main()
