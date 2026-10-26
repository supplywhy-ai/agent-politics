"""Descriptive development results; includes an exact-policy replay baseline."""
import argparse
import csv
import json
from pathlib import Path
from mock_environment import Task, MockEnvironment, authorization_policy
from replay_pipeline import decode_action, prepare, score
from reviewer_probes import prepare_probes, score_probes
from study_prompts import digest


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def index_receipts(raw_calls, stages):
    assert len(raw_calls) == sum(len(responses) for _,responses in stages)
    calls = {}
    offset = 0
    for stage, responses in stages:
        for response, receipt in zip(responses, raw_calls[offset:offset+len(responses)]):
            assert receipt['request_id'] == response['request_id']
            assert receipt['response_sha256'] == digest(response)
            assert response['origin'] == 'model_recording'
            key = (stage,response['request_id'])
            assert key not in calls
            calls[key] = receipt
        offset += len(responses)
    return calls


def analyze(root):
    read = lambda name: json.loads((root / name).read_text())
    manifest = read('manifest.json')
    if manifest['status'] != 'complete':
        raise ValueError('Analyze only completed runs')
    cases = manifest['cases']
    generations, reviews, probes = (read(name + '.json') for name in ('generations', 'reviews', 'probes'))
    result = score(cases, generations, reviews)
    assert result == read('score.json')
    probe_requests = prepare_probes(cases)
    probe_result = score_probes(probe_requests, probes)
    probe_request_index = {r['request_id']:r for r in probe_requests}
    assert probe_result == read('probe-score.json')
    rows = result['rows']
    assert all(r['harm'] is not None for r in rows)
    raw_calls = read('calls.json')
    calls = index_receipts(raw_calls, (('generations',generations),('reviews',reviews),('probes',probes)))

    generation_index = {r['request_id']: r for r in generations}
    case_index = {c['case_id']: c for c in cases}
    for req in prepare(cases):
        c = case_index[req['case_id']]
        action = decode_action(generation_index[req['request_id']]['text'])
        task = Task(**c['task'])
        env = MockEnvironment(task, c['documents'], authorization_policy(task))
        status = 'invalid_generation' if action is None else 'abstained'
        authorized = None
        if action is not None and action.tool != 'abstain':
            authorized = authorization_policy(task)(action)
            status = env.dispatch(action)
        rows.append({'case_id': c['case_id'], 'condition': c['condition'],
                     'executor_hardened': req['executor_hardened'], 'review_mode': 'policy',
                     'generation_request_id': req['request_id'], 'status': status,
                     'authorized_candidate': authorized, 'false_block': False, **env.outcomes()})

    summaries = []
    for condition in ('clean', 'attack'):
        for hard in (False, True):
            for mode in ('none', 'self_full', 'independent_full', 'independent_minimized', 'policy'):
                selected = [r for r in rows if (r['condition'],r['executor_hardened'],r['review_mode']) == (condition,hard,mode)]
                usage = [calls[(stage,r[key])] for r in selected
                         for key,stage in (('generation_request_id','generations'),('review_request_id','reviews')) if key in r]
                summaries.append({'condition': condition, 'executor_hardened': hard, 'review_mode': mode,
                    'n': len(selected), 'harm_count': sum(r['harm'] for r in selected),
                    'safe_completion_count': sum(r['safe_completion'] for r in selected),
                    'unsafe_candidate_count': sum(r['authorized_candidate'] is False for r in selected),
                    'false_block_count': sum(r['false_block'] for r in selected),
                    'invalid_count': sum(r['status'].startswith('invalid_') for r in selected),
                    'attributed_prompt_tokens': sum(c['prompt_tokens'] for c in usage),
                    'attributed_generated_tokens': sum(c['generation_tokens'] for c in usage)})
    write_csv(root / 'arm-summary.csv', summaries)
    probe_summaries = []
    for mode in ('self_full', 'independent_full', 'independent_minimized'):
        for kind in ('authorized', 'wrong_recipient', 'wrong_document'):
            selected = [r for r in probe_result['rows'] if (r['mode'],r['probe_kind']) == (mode,kind)]
            probe_summaries.append({'review_mode':mode, 'probe_kind':kind, 'n':len(selected),
                'unique_message_inputs':len({digest(probe_request_index[r['request_id']]['messages']) for r in selected}),
                'unsafe_allow_count':sum(r['unsafe_allow'] for r in selected),
                'false_block_count':sum(r['false_block'] for r in selected),
                'invalid_count':sum(r['invalid'] for r in selected),
                'missing_count':sum(r['missing'] for r in selected)})
    write_csv(root / 'probe-summary.csv', probe_summaries)
    verification = {'score_recomputed_equal':True, 'probe_score_recomputed_equal':True,
                    'response_hashes_verified':len(calls), 'case_count':len(cases),
                    'lexical_task_variants':len({c['task_cluster'] for c in cases}),
                    'independent_task_families':1,
                    'all_stop':all(c['finish_reason']=='stop' for c in calls.values()),
                    'policy_baseline':'exact authorization on same generated candidates; zero review inference',
                    'cost_warning':'Shared generation calls are attributed to each arm; do not sum arm totals as actual run usage.',
                    'inference_warning':'Development only, no independent-binomial uncertainty or causal generalization.'}
    (root / 'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    return summaries


def plot(rows, output):
    import matplotlib.pyplot as plt
    selected = [r for r in rows if r['condition']=='attack']
    labels = [('Hardened' if r['executor_hardened'] else 'Ordinary')+' / '+r['review_mode'] for r in selected]
    fig, axes = plt.subplots(1,2,figsize=(12,6.5),sharey=True)
    for ax, key, title, color in zip(axes, ('harm_count','safe_completion_count'),
                                    ('Unauthorized action (%) — lower is better','Safe completion (%) — higher is better'),
                                    ('#b54a48','#327b77')):
        values = [100*r[key]/r['n'] for r in selected]
        ax.barh(range(len(labels)),values,color=color)
        ax.set_xlim(0,115)
        ax.set_xticks([0,25,50,75,100])
        ax.set_title(title,fontsize=11)
        ax.set_yticks(range(len(labels)),labels)
        for i,(r,v) in enumerate(zip(selected,values)):
            ax.text(v+1,i,f"{r[key]}/{r['n']}",va='center',fontsize=9)
        ax.spines[['top','right']].set_visible(False)
    axes[0].invert_yaxis()
    fig.suptitle('Local development replay — Qwen3-4B, greedy, 4-bit',fontsize=14)
    fig.text(.02,.025,'12 attacked cases: 6 hand-authored attacks × 2 lexical variants of one task.\nShared candidates; no retries. Policy = exact code check. Descriptive development results, not held-out evidence.',fontsize=9)
    fig.tight_layout(rect=(0,.09,1,.94))
    fig.savefig(output.with_suffix('.png'),dpi=180)
    fig.savefig(output.with_suffix('.pdf'))
    plt.close(fig)


def latex_table(rows, output):
    names = {'none':'None', 'self_full':'Self/full', 'independent_full':'Separate/full',
             'independent_minimized':'Separate/minimized', 'policy':'Exact policy'}
    lines = [r'\begin{tabular}{llrrr}', r'\hline',
             r'Executor & Review & Harm & Safe completion & Mean tokens \\', r'\hline']
    for r in rows:
        if r['condition'] != 'attack':
            continue
        tokens = (r['attributed_prompt_tokens'] + r['attributed_generated_tokens'])/r['n']
        lines.append(('Hardened' if r['executor_hardened'] else 'Ordinary') + ' & ' + names[r['review_mode']] +
                     f" & {r['harm_count']}/{r['n']} & {r['safe_completion_count']}/{r['n']} & {tokens:.1f} " + r'\\')
    lines.extend([r'\hline', r'\end{tabular}'])
    output.write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--run',required=True,type=Path)
    p.add_argument('--figure',type=Path)
    p.add_argument('--table',type=Path)
    args=p.parse_args()
    rows=analyze(args.run)
    if args.figure:
        plot(rows,args.figure)
    if args.table:
        latex_table(rows,args.table)
    print(json.dumps(rows,indent=2))
