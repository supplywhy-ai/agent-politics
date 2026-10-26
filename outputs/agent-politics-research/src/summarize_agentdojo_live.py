"""Summarize verified clean episodes; blocked attempts are not executed tools."""
import argparse
import csv
import json
from pathlib import Path


def summarize(run):
    read=lambda p:json.loads(p.read_text())
    m=read(run/'manifest.json')
    v=read(run/'verification.json')
    assert m['status']=='complete' and all(t['state_replay_equal'] for t in v['tasks'])
    episodes=[read(run/t/'episode.json') for t in m.get('episode_ids',m['tasks'])]
    calls=[c for e in episodes for c in e['calls']+e.get('review_calls',[]) if c.get('usage')]
    return {'run':run.name,'review_mode':m.get('review_mode','none'),
            'read_policy':m.get('read_policy','review_all'),'tasks':len(episodes),
            'utility_count':sum(e['utility'] for e in episodes),
            'executor_calls':sum(len(e['calls']) for e in episodes),
            'review_calls':sum('usage' in r for e in episodes for r in e.get('review_calls',[])),
            'budget_exhausted':sum(e['status']=='budget_exhausted' for e in episodes),
            'read_policy_allows':sum(len(e.get('policy_decisions',[])) for e in episodes),
            'tool_attempts':sum(len(e['tool_events']) for e in episodes),
            'tool_successes':sum(t['error'] is None for e in episodes for t in e['tool_events']),
            'blocked_attempts':sum(a['decision']=='blocked' for e in episodes for a in e['extra_args'].get('sidecar_audit',[])),
            'review_failures':sum(a['decision'] in ('invalid_review','review_unavailable') for e in episodes for a in e['extra_args'].get('sidecar_audit',[])),
            'api_reported_total_tokens':sum(c['usage']['total_tokens'] for c in calls),
            'attack_episodes':sum(not e['clean'] for e in episodes),
            'attack_success_count':sum(e['attack_success'] is True for e in episodes),
            'no_attacks_evaluated':all(e['clean'] for e in episodes)}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--runs',required=True,nargs='+',type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--table',type=Path)
    args=p.parse_args()
    rows=[summarize(r) for r in args.runs]
    with args.out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if args.table:
        lines=[r'\begin{tabular}{lrrrrr}',r'\hline',r'Review & Utility & Actor calls & Review calls & Blocks & Tokens \\',r'\hline']
        for r in rows:
            lines.append(f"{r['review_mode']} & {r['utility_count']}/{r['tasks']} & {r['executor_calls']} & {r['review_calls']} & {r['blocked_attempts']} & {r['api_reported_total_tokens']:,} "+r'\\')
        lines.extend([r'\hline',r'\end{tabular}'])
        args.table.write_text('\n'.join(lines)+'\n')
    print(json.dumps(rows,indent=2))
