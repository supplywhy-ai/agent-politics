"""Descriptive repeatability on ten tasks; never treat 480 episodes as 480 tasks."""
import json
from collections import defaultdict
from summarize_transfer import ROOT, ARMS, collect, aggregate, write_csv

def main():
    # collect refuses missing cohorts, failed verification, or incomplete audits.
    rows=[]
    summaries=[]
    for rep in (1,2,3):
        current=collect(ROOT/'results',rep)
        rows.extend(current)
        summaries.extend({'repetition':rep,**s} for s in aggregate(current))
    assert len(rows)==480
    cells=defaultdict(list)
    for row in rows:
        cells[(row['cohort'],row['arm'],row['task_id'],row['episode_id'])].append(row)
    assert len(cells)==160
    stability=[]
    for (cohort,arm,task,eid),values in sorted(cells.items()):
        assert {v['repetition'] for v in values}=={1,2,3} and len(values)==3
        values.sort(key=lambda v:v['repetition'])
        result={'cohort':cohort,'arm':arm,'task_id':task,'episode_id':eid,
                'utility_by_repetition':','.join(str(v['native_utility']) for v in values),
                'utility_varies':int(len({v['native_utility'] for v in values})>1),
                'status_by_repetition':','.join(v['status'] for v in values),
                'status_varies':int(len({v['status'] for v in values})>1),
                'all_actual_token_usage_complete':int(all(v['actual_tokens_complete'] for v in values)),
                'infrastructure_error_by_repetition':','.join(str(v['infrastructure_error']) for v in values),
                'tokens_min':min(v['actual_tokens'] for v in values),
                'tokens_max':max(v['actual_tokens'] for v in values)}
        for key in ('attack_success','safe_completion','actor_tool_prompt'):
            result[key+'_by_repetition']=','.join(str(v[key]) for v in values) if cohort=='attack' else ''
            result[key+'_varies']=int(len({v[key] for v in values})>1) if cohort=='attack' else ''
        stability.append(result)
    stem='transfer-three-repetitions'
    write_csv(ROOT/f'results/{stem}-episodes-v1.csv',rows)
    write_csv(ROOT/f'results/{stem}-summary-v1.csv',summaries)
    write_csv(ROOT/f'results/{stem}-stability-v1.csv',stability)
    table=[r'\begin{tabular}{llrrrr}',r'\toprule',
           r'Arm & Repeat & Clean & Attacked & AS & Safe\\',r'\midrule']
    for arm in ARMS:
        for s in summaries:
            if s['arm']!=arm:continue
            table.append(f"{arm} & {s['repetition']} & {s['clean_utility']}/10 & {s['attacked_utility']}/30 & {s['attack_success']}/30 & {s['safe_completion']}/30 "+r'\\')
    table += [r'\bottomrule',r'\end{tabular}']
    (ROOT/f'manuscript/{stem}-table.tex').write_text('\n'.join(table)+'\n')
    print(json.dumps({'episodes':len(rows),'underlying_tasks':10,
                     'scope':'Three complete repetitions, per-repetition descriptive counts; no independence or statistical significance claim.',
                     'summary':summaries},indent=2))

if __name__=='__main__':main()
