"""Compact publication-sized matrix from saved verified development counts."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((R/'results/native-budget-summary-8000-16000-32000-64000-v1.csv').open()))
lookup={(r['arm'],int(r['budget'])):r for r in rows}
arms=['ordinary','hardened','self','full','minimized'];budgets=[8000,16000,32000,64000]
assert len(lookup)==20
plt.rcParams.update({'font.size':9})
fig,axs=plt.subplots(2,2,figsize=(7,5.5))
for ax,(key,title,denom,cmap) in zip(axs.flat,[('clean_utility','Clean utility (higher is better)',3,'GnBu'),('attack_success','Attack success (lower is better)',3,'Reds'),('attacked_utility','Attacked utility (higher is better)',3,'GnBu'),('exhausted','Budget exhaustion',6,'Greys')]):
 vals=[[int(lookup[a,b]['clean_exhausted'])+int(lookup[a,b]['attack_exhausted']) if key=='exhausted' else int(lookup[a,b][key]) for b in budgets] for a in arms]
 ax.imshow(vals,vmin=0,vmax=denom,cmap=cmap,aspect='auto')
 ax.set_xticks(range(4),['8k','16k','32k','64k']);ax.set_yticks(range(5),['Ordinary','Hardened','Self-role','Full review','Minimized'])
 ax.tick_params(labelsize=8);ax.set_title(title,fontsize=9)
 for i,row in enumerate(vals):
  for j,v in enumerate(row):ax.text(j,i,f'{v}/{denom}',ha='center',va='center',fontsize=9,color='white' if v>denom*.55 else '#222222')
 ax.set_xlabel('Token cap per episode',fontsize=8)
fig.tight_layout(pad=.7,w_pad=1.1,h_pad=1.4)
for ext in ['pdf','png']:fig.savefig(R/f'figures/native-budget-paper-v1.{ext}',dpi=200)
(R/'manuscript/images/native-budget-paper-v1.pdf').write_bytes((R/'figures/native-budget-paper-v1.pdf').read_bytes())
