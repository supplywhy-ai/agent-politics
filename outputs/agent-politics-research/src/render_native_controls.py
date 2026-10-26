"""Summarize verified architecture controls; fixed development cohorts only."""
import csv
import json
from pathlib import Path
from summarize_agentdojo_live import summarize

ROOT=Path(__file__).resolve().parents[1]
CONFIGURATIONS=[
    ('Ordinary executor','agentdojo-local-clean-v1','agentdojo-calendar-attack-none-v1'),
    ('Hardened executor','agentdojo-hardened-clean-v1','agentdojo-hardened-attack-v1'),
    ('Self-role full review','agentdojo-self-clean-v1','agentdojo-self-attack-v1'),
    ('Independent full review','agentdojo-read-scope-full-v1','agentdojo-calendar-attack-full-v1'),
    ('Independent minimized','agentdojo-read-scope-minimized-v1','agentdojo-calendar-attack-minimized-v1')]

def main():
    rows=[]
    for label,clean_name,attack_name in CONFIGURATIONS:
        c=summarize(ROOT/'results'/clean_name)
        a=summarize(ROOT/'results'/attack_name)
        rows.append(dict(configuration=label,clean_run=clean_name,attack_run=attack_name,
                         clean_utility=c['utility_count'],clean_n=c['tasks'],
                         attack_success=a['attack_success_count'],attack_n=a['attack_episodes'],
                         attacked_utility=a['utility_count'],
                         clean_tokens=c['api_reported_total_tokens'],attack_tokens=a['api_reported_total_tokens'],
                         clean_calls=c['executor_calls']+c['review_calls'],
                         attack_calls=a['executor_calls']+a['review_calls']))
    with (ROOT/'results/native-controls-summary-v1.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines=[r'\begin{tabular}{lrrrr}',r'\hline',
           r'Configuration & Clean & AS & Attacked utility & Tokens (clean/attack) \\',r'\hline']
    for r in rows:
        lines.append(f"{r['configuration']} & {r['clean_utility']}/{r['clean_n']} & {r['attack_success']}/{r['attack_n']} & {r['attacked_utility']}/{r['attack_n']} & {r['clean_tokens']:,}/{r['attack_tokens']:,} "+r'\\')
    lines.extend([r'\hline',r'\end{tabular}'])
    (ROOT/'manuscript/native-controls-table.tex').write_text('\n'.join(lines)+'\n')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4.8),sharey=True)
    labels=[r['configuration'] for r in rows]
    for ax,key,title,color in zip(axes,['clean_utility','attack_success','attacked_utility'],
        ['Clean tasks completed (higher is better)','Attacker goals achieved (lower is better)',
         'Attacked tasks completed (higher is better)'],['#327b77','#b54a48','#427ab1']):
        ax.barh(range(len(rows)),[r[key] for r in rows],color=color,height=.6)
        ax.set_xlim(0,3.6);ax.set_xticks([0,1,2,3]);ax.set_yticks(range(len(rows)),labels)
        ax.set_title(title,fontsize=10)
        for i,r in enumerate(rows):ax.text(r[key]+.06,i,f'{r[key]}/3',va='center')
        ax.spines[['top','right']].set_visible(False)
    axes[0].invert_yaxis()
    fig.suptitle('Native architecture controls — Qwen3-4B, 4-bit',fontsize=14)
    fig.text(.02,.025,'Clean: 3 fixed tasks. Attacked: 3 payloads on ONE calendar task. Single runs; unequal costs.\nAll review arms use the same four-tool read allowlist. Self-role review changes a role sentence, not hidden-state access.',fontsize=9)
    fig.tight_layout(rect=(0,.14,1,.93))
    for ext in ('png','pdf'):fig.savefig(ROOT/f'figures/native-controls-v1.{ext}',dpi=180)
    plt.close(fig)
    print(json.dumps(rows,indent=2))

if __name__=='__main__':main()
