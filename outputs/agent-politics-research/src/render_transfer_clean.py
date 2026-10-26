"""Plot a complete verified clean transfer cohort; no inferential ranking."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((ROOT/'results/transfer-r1-clean-summary-v1.csv').open()))
arms=['ordinary','hardened','full','minimized']
labels=['Ordinary executor','Hardened executor','Full-context review','Minimized-context review']
tasks=[1,3,8,9,14,15,17,18,29,34]
lookup={(r['arm'],int(r['task_id'].split('_')[-1])):r for r in rows}
assert len(rows)==len(lookup)==40
values=[[int(lookup[a,t]['utility_count']) for t in tasks] for a in arms]
fig,(ax,cost)=plt.subplots(1,2,figsize=(13,4.7),gridspec_kw={'width_ratios':[3,1]})
ax.imshow(values,cmap=ListedColormap(['#e6e9ed','#167d8d']),vmin=0,vmax=1,aspect='auto')
ax.set_yticks(range(4),labels)
ax.set_xticks(range(10),[str(t) for t in tasks])
ax.set_xlabel('AgentDojo task ID (calendar: 1–9; email-derived: 14–18; documents: 29, 34)')
ax.set_title('Native task success: 1 = success, 0 = failure')
for i,row in enumerate(values):
    for j,v in enumerate(row):ax.text(j,i,str(v),ha='center',va='center',color='white' if v else '#333333')
tokens=[sum(int(lookup[a,t]['api_reported_total_tokens']) for t in tasks)/1000 for a in arms]
cost.barh(range(4),tokens,color='#167d8d');cost.invert_yaxis()
cost.set_yticks([]);cost.set_xlim(0,max(tokens)*1.3)
cost.set_xlabel('Total tokens (thousands)');cost.set_title('Actual consumption / 10 tasks')
for i,v in enumerate(tokens):cost.text(v+3,i,f'{v:.1f}k',va='center')
fig.suptitle('First clean transfer repetition — Qwen3-4B, 4-bit; 64k cap per episode')
fig.text(.02,.025,'Ten purposively selected tasks, one repetition. No attacks in this figure. All failures retained.\nEqual token caps do not imply equal actual consumption or compute. Task success uses the native scorer.',fontsize=9)
fig.tight_layout(rect=(0,.13,1,.94))
for ext in ['png','pdf']:fig.savefig(ROOT/f'figures/transfer-r1-clean-v1.{ext}',dpi=180)
(ROOT/'manuscript/images/transfer-r1-clean-v1.pdf').write_bytes((ROOT/'figures/transfer-r1-clean-v1.pdf').read_bytes())
plt.close(fig)
