"""Summarize only fully verified budget cohorts, retaining exhaustion outcomes."""
import argparse
import csv
import json
from pathlib import Path
from run_budget_matrix import ROOT,ARMS
from summarize_agentdojo_live import summarize

def main():
    p=argparse.ArgumentParser();p.add_argument('--budgets',nargs='+',type=int,required=True);a=p.parse_args()
    rows=[]
    for budget in a.budgets:
        for arm,_ in ARMS:
            c=summarize(ROOT/'results'/f'agentdojo-budget-{budget}-{arm}-clean-v1')
            t=summarize(ROOT/'results'/f'agentdojo-budget-{budget}-{arm}-attack-v1')
            rows.append(dict(budget=budget,arm=arm,clean_n=c['tasks'],clean_utility=c['utility_count'],
                attack_n=t['tasks'],attacked_utility=t['utility_count'],attack_success=t['attack_success_count'],
                clean_exhausted=c['budget_exhausted'],attack_exhausted=t['budget_exhausted'],
                clean_actual_tokens=c['api_reported_total_tokens'],attack_actual_tokens=t['api_reported_total_tokens'],
                actor_calls=c['executor_calls']+t['executor_calls'],review_calls=c['review_calls']+t['review_calls']))
    out=ROOT/'results'/('native-budget-summary-'+'-'.join(map(str,a.budgets))+'-v1.csv')
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
