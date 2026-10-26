"""Render descriptive upstream-log summaries; not new model evaluations."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_archived_agentdojo import ARMS

root = Path(__file__).resolve().parents[1]
with (root/'results/agentdojo-archive-v1/summary.csv').open() as f:
    lookup = {(r['arm'],r['condition']):r for r in csv.DictReader(f)
              if r['subset']=='error_free_common'}
labels = ['No defense','Repeat user prompt','Delimit tool output','Tool filter','Injection detector']
fig, axes = plt.subplots(1,3,figsize=(11,4.3),sharey=True,layout='constrained')
specs = [('clean','utility','Clean task completion ↑'),
         ('attack','attack_success','Attack success ↓'),
         ('attack','safe_completion','Safe completion under attack ↑')]
for ax,(condition,metric,title) in zip(axes,specs):
    values = [100*float(lookup[(a,condition)][metric]) for a in ARMS]
    bars = ax.barh(range(5),values,color='#3378a8',height=.65)
    ax.set_yticks(range(5),labels)
    ax.set(xlim=(0,100),xlabel='Percent',title=title)
    ax.bar_label(bars,labels=[f'{v:.1f}' for v in values],padding=3,fontsize=9)
    ax.grid(axis='x',alpha=.2)
axes[0].invert_yaxis()
fig.suptitle('AgentDojo public logs: historical GPT-4o (2024-05-13)\n97 common clean tasks; 629 common attack cases; no new model calls',fontsize=12)
fig.savefig(root/'figures/agentdojo-archive.png',dpi=180)
fig.savefig(root/'figures/agentdojo-archive.pdf')
lines = [r'\begin{tabular}{lrrrr}',r'\toprule',
         r'Defense & Clean utility & Attack utility & ASR & Safe completion\\',r'\midrule']
for arm,label in zip(ARMS,labels):
    c,a = lookup[(arm,'clean')],lookup[(arm,'attack')]
    values = [c['utility'],a['utility'],a['attack_success'],a['safe_completion']]
    lines.append(label+' & '+' & '.join(f'{100*float(v):.2f}' for v in values)+r'\\')
lines.extend([r'\bottomrule',r'\end{tabular}'])
(root/'manuscript/archive-table.tex').write_text('\n'.join(lines)+'\n')
print(root/'figures/agentdojo-archive.png')
