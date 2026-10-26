"""Compare complete verified clean cohorts before their paired attacks finish."""
import argparse
import json
from summarize_transfer import ROOT, ARMS, read, require_token_coverage, write_csv

def main():
    p=argparse.ArgumentParser();p.add_argument('--repetitions',type=int,nargs='+',required=True)
    args=p.parse_args();reps=sorted(args.repetitions)
    assert reps==list(range(1,max(reps)+1)) and max(reps)<=3
    rows=[]
    for rep in reps:
        batch=read(ROOT/f'results/transfer-batch-r{rep}-clean-v1.json')
        assert batch['status'] in ('complete','complete_with_errors','complete_with_retries')
        names=[s['name'] for s in batch['specifications']]
        failed=batch.get('failed_runs',[])
        assert len(names)==len(set(names))==40
        assert len(batch['completed'])+len(failed)==40
        assert not set(batch['completed'])&set(failed)
        assert set(names)==set(batch['completed'])|set(failed)
        assert (batch['status'] in ('complete_with_errors','complete_with_retries'))==bool(failed)
        replacements=batch.get('replacement_runs',{})
        if batch['status']=='complete_with_retries':
            assert set(replacements)==set(failed) and len(set(replacements.values()))==len(failed)
            assert not set(replacements.values())&set(names)
        else: assert not replacements
        require_token_coverage(ROOT/f'results/transfer-r{rep}-clean-token-audit-v1.json',
                               [ROOT/'results'/n for n in names+list(replacements.values())])
        for spec in batch['specifications']:
            selected_name=replacements.get(spec['name'],spec['name'])
            run=ROOT/'results'/selected_name;m=read(run/'manifest.json');v=read(run/'verification.json')
            assert m['status']=='complete' and len(m['episode_ids'])==len(v['tasks'])==1
            eid=m['episode_ids'][0];e=read(run/eid/'episode.json');check=v['tasks'][0]
            assert check['episode_id']==eid and check['state_replay_equal'] and check['native_message_history_replay_equal']
            assert e['clean'] and e['utility']==check['utility']
            transport_error=e['status']=='error'
            if transport_error:
                assert spec['name'] in failed and check['transport_failure_preserved']
                assert not check['actual_token_usage_complete']
            else: assert e['status']!='accounting_error'
            calls=[read(f) for f in (run/eid).glob('budget-call-*.json')]
            tokens=sum(c['response']['usage']['total_tokens'] for c in calls if 'response' in c)
            uncertain=sum(v['reservation'] for v in e['budget']['events'] if v['status']=='uncertain_failure')
            assert bool(uncertain)==transport_error
            assert tokens+uncertain==e['budget']['used']<=e['budget']['limit']
            rows.append({'repetition':rep,'arm':spec['arm'],'task_id':e['task_id'],
                         'selected_run':selected_name,'infrastructure_retry':int(selected_name!=spec['name']),
                         'native_utility':int(e['utility']),'actual_tokens':tokens,'actual_tokens_complete':int(not transport_error),'uncertain_reserved_tokens':uncertain,'infrastructure_error':int(transport_error),'status':e['status']})
    summaries=[]
    for rep in reps:
        for arm in ARMS:
            selected=[r for r in rows if r['repetition']==rep and r['arm']==arm]
            assert len(selected)==len({r['task_id'] for r in selected})==10
            summaries.append({'repetition':rep,'arm':arm,'tasks':10,
                              'native_utility':sum(r['native_utility'] for r in selected),
                              'actual_tokens':sum(r['actual_tokens'] for r in selected),
                              'actual_tokens_complete':int(all(r['actual_tokens_complete'] for r in selected)),
                              'infrastructure_errors':sum(r['infrastructure_error'] for r in selected),
                              'uncertain_reserved_tokens':sum(r['uncertain_reserved_tokens'] for r in selected)})
    stem='transfer-clean-repetitions-'+ '-'.join(map(str,reps))
    write_csv(ROOT/f'results/{stem}-episodes-v1.csv',rows)
    write_csv(ROOT/f'results/{stem}-summary-v1.csv',summaries)
    print(json.dumps({'scope':'Complete clean cohorts only; same ten tasks repeated; no attack-resistance claim.',
                      'summary':summaries},indent=2))

if __name__=='__main__':main()
