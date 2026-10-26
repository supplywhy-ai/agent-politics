"""Plot verified native clean/attack development cohorts; no inference statistics."""
import argparse
import csv
import json
from pathlib import Path
from summarize_agentdojo_live import summarize


def render(root,figure,table):
    configurations=[('No review','agentdojo-local-clean-v1','agentdojo-calendar-attack-none-v1'),
                    ('Full history + read policy','agentdojo-read-scope-full-v1','agentdojo-calendar-attack-full-v1'),
                    ('Minimized + read policy','agentdojo-read-scope-minimized-v1','agentdojo-calendar-attack-minimized-v1')]
    rows=[]
    for label,clean_name,attack_name in configurations:
        clean=summarize(root/clean_name); attack=summarize(root/attack_name)
        rows.append({'configuration':label,'clean_run':clean_name,'attack_run':attack_name,
                     'clean_utility':clean['utility_count'],'clean_n':clean['tasks'],
                     'attack_success':attack['attack_success_count'],'attack_n':attack['attack_episodes'],
                     'attack_utility':attack['utility_count'],
                     'clean_model_calls':clean['executor_calls']+clean['review_calls'],
                     'attack_model_calls':attack['executor_calls']+attack['review_calls'],
                     'clean_tokens':clean['api_reported_total_tokens'],
                     'attack_tokens':attack['api_reported_total_tokens']})
    with (root/'native-pilot-summary-v1.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    paired=[]
    for family in ('direct','workflow_authority','role_spoof'):
        candidates=[]
        for _,_,run in configurations:
            ep=json.loads((root/run/f'user_task_0--{family}'/'episode.json').read_text())
            candidates.append([e['args'] for e in ep['tool_events'] if e['function']=='send_email'])
        assert all(len(c)==1 for c in candidates)
        assert candidates[0]==candidates[1]==candidates[2]
        paired.append({'attack':family,'same_email_candidate_across_three_configurations':True})
    (root/'native-pilot-pairing-v1.json').write_text(json.dumps(paired,indent=2)+'\n')
    lines=[r'\begin{tabular}{lrrr}',r'\hline',r'Configuration & Clean utility & Attack success & Attacked utility \\',r'\hline']
    for r in rows:
        lines.append(f"{r['configuration']} & {r['clean_utility']}/3 & {r['attack_success']}/3 & {r['attack_utility']}/3 "+r'\\')
    lines.extend([r'\hline',r'\end{tabular}'])
    table.write_text('\n'.join(lines)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4.8),sharey=True)
    for ax,key,title,color in zip(axes,('clean_utility','attack_success','attack_utility'),
        ('Clean tasks completed ↑','Attacker goals achieved ↓','Attacked tasks completed ↑'),
        ('#327b77','#b54a48','#427ab1')):
        ax.bar(range(3),[r[key] for r in rows],color=color,width=.6)
        ax.set_ylim(0,3.7);ax.set_yticks([0,1,2,3])
        ax.set_xticks(range(3),['No review','Full +\nread policy','Minimized +\nread policy'])
        ax.set_title(title,fontsize=11)
        for i,r in enumerate(rows):ax.text(i,r[key]+.08,f"{r[key]}/3",ha='center')
        ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Native AgentDojo development pilot — Qwen3-4B, 4-bit',fontsize=14)
    fig.text(.025,.025,'Clean: 3 fixed tasks. Attacked: 3 fixed payloads on ONE calendar task.\nRead policy allows 4 inspected nonmutating tools. Single runs; unequal inference costs; no general robustness claim.',fontsize=9)
    fig.tight_layout(rect=(0,.12,1,.92))
    fig.savefig(figure.with_suffix('.png'),dpi=180);fig.savefig(figure.with_suffix('.pdf'));plt.close(fig)
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True)
    p.add_argument('--figure',type=Path,required=True);p.add_argument('--table',type=Path,required=True)
    a=p.parse_args();render(a.results,a.figure,a.table)
