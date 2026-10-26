"""Recorded-path admission thresholds, NOT counterfactual budgeted outcomes."""
import csv
import json
from pathlib import Path
from render_native_controls import CONFIGURATIONS,ROOT
from token_budget import TokenBudget,BudgetExhausted


def main():
    audit={}
    for name in ('native-token-count-audit-v1.json','native-controls-token-audit-v1.json'):
        data=json.loads((ROOT/'results'/name).read_text())
        assert data['all_equal']
        audit.update({str(Path(r['record']).resolve()):r['computed_prompt_tokens'] for r in data['records']})
    rows=[]
    for label,clean,attack in CONFIGURATIONS:
        for cohort,name in [('clean',clean),('attack',attack)]:
            folder=ROOT/'results'/name
            m=json.loads((folder/'manifest.json').read_text())
            for eid in m.get('episode_ids',m['tasks']):
                ep=folder/eid
                reviews=[json.loads(p.read_text())|{'path':p} for p in sorted(ep.glob('review-*.json'))]
                queue=[];ri=0
                for path in sorted(ep.glob('call-*.json')):
                    record=json.loads(path.read_text());queue.append(('actor',path,record))
                    for tool in record['response']['choices'][0]['message'].get('tool_calls') or []:
                        if m.get('review_mode','none')=='none' or tool['function']['name'] in m.get('verified_reads',[]):continue
                        review=reviews[ri];ri+=1
                        packet=json.loads(review['request']['messages'][1]['content'])
                        assert packet['candidate']=={'function':tool['function']['name'],
                            'args':json.loads(tool['function']['arguments'])}
                        queue.append(('reviewer',review['path'],review))
                assert ri==len(reviews)
                used=threshold=0
                for lane,path,r in queue:
                    prompt=audit[str(path.resolve())]
                    assert prompt==r['response']['usage']['prompt_tokens']
                    threshold=max(threshold,used+prompt+r['request']['max_tokens'])
                    used+=r['response']['usage']['total_tokens']
                row=dict(configuration=label,cohort=cohort,episode=eid,
                         recorded_tokens=used,minimum_full_reservation_budget=threshold,calls=len(queue))
                for limit in (8000,16000,32000,64000):
                    b=TokenBudget(limit,lambda r:r['_audit_prompt'])
                    admitted=0
                    for lane,path,r in queue:
                        request=dict(r['request'],_audit_prompt=audit[str(path.resolve())])
                        try:b.call(request,lane,lambda q:r['response'])
                        except BudgetExhausted:break
                        admitted+=1
                    row[f'path_admitted_{limit}']=admitted==len(queue)
                    assert (admitted==len(queue))==(limit>=threshold)
                rows.append(row)
    out=ROOT/'results/native-budget-path-audit-v1.csv'
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=[]
    for label,_,_ in CONFIGURATIONS:
        selected=[r for r in rows if r['configuration']==label]
        summary.append({'configuration':label,'episodes':len(selected),
                        'maximum_path_threshold':max(r['minimum_full_reservation_budget'] for r in selected),
                        **{str(b):sum(r[f'path_admitted_{b}'] for r in selected) for b in (8000,16000,32000,64000)}})
    result={'scope':'Recorded trajectory admission only; no new inference, no counterfactual safety or utility.',
            'model_calls':0,'budget_grid':[8000,16000,32000,64000],'summary':summary}
    (ROOT/'results/native-budget-path-summary-v1.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
