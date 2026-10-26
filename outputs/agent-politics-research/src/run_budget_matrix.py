"""Sequential local-only development matrix; never overwrites prior runs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parents[1]
ARMS=[('ordinary',[]),('hardened',['--executor-hardened']),
      ('self',['--review','self_full','--read-policy','allow_verified_reads']),
      ('full',['--review','full','--read-policy','allow_verified_reads']),
      ('minimized',['--review','minimized','--read-policy','allow_verified_reads'])]

def main():
    p=argparse.ArgumentParser();p.add_argument('--budgets',nargs='+',type=int,default=[8000,16000,32000,64000])
    a=p.parse_args()
    assert len(set(a.budgets))==len(a.budgets) and set(a.budgets)<={8000,16000,32000,64000}
    specs=[]
    for budget in a.budgets:
        for arm,flags in ARMS:
            for cohort in ('clean','attack'):
                name=f'agentdojo-budget-{budget}-{arm}-{cohort}-v1'
                specs.append(dict(name=name,budget=budget,arm=arm,cohort=cohort,flags=flags))
    assert all(not (ROOT/'results'/s['name']).exists() for s in specs)
    manifest=ROOT/'results'/('budget-batch-'+'-'.join(map(str,a.budgets))+'-v1.json')
    assert not manifest.exists()
    record={'started_utc':datetime.now(timezone.utc).isoformat(),'scope':'Development only; equal token caps, not equal compute.',
            'specifications':specs,'completed':[],'status':'running',
            'runner_sha256':hashlib.sha256(Path(__file__).with_name('agentdojo_local_live.py').read_bytes()).hexdigest()}
    def save():manifest.write_text(json.dumps(record,indent=2)+'\n')
    save()
    base=[sys.executable,'-u',str(Path(__file__).with_name('agentdojo_local_live.py')),
          '--model-path',str(WORKSPACE/'work/models/qwen3-4b-instruct-2507-4bit'),
          '--model-manifest',str(ROOT/'results/calibration-qwen-v1/manifest.json'),
          '--token-counter-python',str(WORKSPACE/'work/mlx-venv/bin/python')]
    for s in specs:
        print('Starting',s['name'],flush=True)
        extra=['--attack-fixture',str(ROOT/'fixtures/native-calendar-attacks-v1.json')] if s['cohort']=='attack' else []
        with (WORKSPACE/'work'/f"{s['name']}.log").open('w') as log:
            subprocess.run(base+['--out',str(ROOT/'results'/s['name']),'--token-budget',str(s['budget'])]+s['flags']+extra,
                           stdout=log,stderr=subprocess.STDOUT,check=True)
        record['completed'].append(s['name']);save()
        print('Completed',s['name'],flush=True)
    record.update(status='complete',finished_utc=datetime.now(timezone.utc).isoformat());save()

if __name__=='__main__':main()
