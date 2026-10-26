"""Secondary descriptive analysis of upstream logs; no new model evaluations.

Use only common task keys and separately report all-labelled/error-free records.
Attack-mode security=True means attacker success in the inspected upstream code.
Clean security=True is a sentinel and must never enter an attack-success rate.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

BASE = 'gpt-4o-2024-05-13'
ARMS = [BASE, BASE+'-repeat_user_prompt', BASE+'-spotlighting_with_delimiting',
        BASE+'-tool_filter', BASE+'-transformers_pi_detector']
PIN = '089ed468cf3ed0322acc66b0211f26d9d90dbf60'


def classify(data):
    if not str(data.get('user_task_id','')).startswith('user_task_'):
        return None
    if data.get('injection_task_id') is None and data.get('attack_type') is None:
        return 'clean'
    if data.get('injection_task_id') is not None and data.get('attack_type') == 'important_instructions':
        return 'attack'
    return None


def summarize(records, condition):
    n = len(records)
    if not n:
        return {'n':0,'utility':None,'attack_success':None,'safe_completion':None}
    utility = sum(r['utility'] for r in records)/n
    if condition == 'clean':
        return {'n':n,'utility':utility,'attack_success':None,'safe_completion':None}
    return {'n':n,'utility':utility,
            'attack_success':sum(r['security'] for r in records)/n,
            'safe_completion':sum(r['utility'] and not r['security'] for r in records)/n}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args = parser.parse_args()
    revision = subprocess.check_output(['git','-C',str(args.repo),'rev-parse','HEAD'],text=True).strip()
    if revision != PIN:
        raise ValueError('Repository revision differs from inspected source; review semantics before changing pin')
    maps, audit, provenance = {}, {}, []
    for arm in ARMS:
        maps[arm] = {}
        audit[arm] = {'selected':0,'invalid_labels':0,'errors':0,'benchmark_versions':{}}
        for path in sorted((args.repo/'runs'/arm).glob('*/user_task_*/*/*.json')):
            raw = path.read_bytes()
            data = json.loads(raw)
            condition = classify(data)
            if condition is None:
                continue
            if data.get('pipeline_name') != arm:
                raise ValueError(f'Pipeline metadata mismatch: {path}')
            audit[arm]['selected'] += 1
            version = str(data.get('benchmark_version','not_recorded'))
            audit[arm]['benchmark_versions'][version] = audit[arm]['benchmark_versions'].get(version,0)+1
            if type(data.get('utility')) is not bool or type(data.get('security')) is not bool:
                audit[arm]['invalid_labels'] += 1
                continue
            error = bool(data.get('error'))
            audit[arm]['errors'] += int(error)
            key = (condition,data['suite_name'],data['user_task_id'],data.get('injection_task_id'))
            if key in maps[arm]:
                raise ValueError(f'Duplicate task key in {arm}: {key}')
            record = {'utility':data['utility'],'security':data['security'],'error':error}
            maps[arm][key] = record
            provenance.append({'arm':arm,'condition':condition,'suite':key[1],
                               'user_task_id':key[2],'injection_task_id':key[3],
                               **record,'benchmark_version':version,
                               'path':str(path.relative_to(args.repo)),
                               'sha256':hashlib.sha256(raw).hexdigest()})
    common = set.intersection(*(set(m) for m in maps.values()))
    rows = []
    for condition in ('clean','attack'):
        for subset in ('all_labelled_common','error_free_common'):
            keys = [k for k in common if k[0]==condition and
                    (subset=='all_labelled_common' or all(not maps[a][k]['error'] for a in ARMS))]
            keys.sort(key=lambda k: tuple(str(v) for v in k))
            for arm in ARMS:
                records = [maps[arm][k] for k in keys]
                rows.append({'arm':arm,'condition':condition,'subset':subset,
                             'unique_user_tasks':len({(k[1],k[2]) for k in keys}),
                             'errors_in_arm':sum(r['error'] for r in records),
                             **summarize(records,condition)})
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'summary.csv').open('w',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    manifest = {'evidence_type':'secondary_analysis_of_public_model_logs',
                'new_model_calls':0,'source_repo':'https://github.com/ethz-spylab/agentdojo',
                'source_commit':revision,'pipeline_arms':ARMS,'audit':audit,
                'common_keys':len(common),'source_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'interpretation':'Descriptive historical comparison; not our A/B experiment or a causal estimate.',
                'limitations':['Historical model versions, fixed attack family, unverified generation-time benchmark revision.',
                               'Existing scorer labels reused; final environments not independently reconstructed.',
                               'Shared tasks and attacks are dependent; no binomial significance claims.',
                               'Error-free subset is complete-case selection and may be biased.',
                               'No independent sidecar or matched inference-budget arm is identified here.']}
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (args.out/'source-records.json').write_text(json.dumps(provenance,indent=2)+'\n')
    for r in rows:
        if r['subset']=='error_free_common':
            print(json.dumps(r))


if __name__ == '__main__':
    main()
