from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
r=Path(__file__).resolve().parents[1]
fig,ax=plt.subplots(figsize=(7,3.4));ax.set(xlim=(0,10),ylim=(0,4.9));ax.axis('off')
def box(x,y,w,h,text,color):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.05',facecolor=color,edgecolor='#405468',linewidth=1))
 ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=8)
def arrow(a,b,label=None,offset=(0,0)):
 ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=11,color='#405468',linewidth=1.1))
 if label:ax.text((a[0]+b[0])/2+offset[0],(a[1]+b[1])/2+offset[1],label,ha='center',va='center',fontsize=7)
box(.2,2.9,2,1,'Actor\nTrusted task +\ntool history','#e3eef7')
box(3.8,2.9,2.5,1,'Execution gate\nFreeze proposed action','#e3eef7')
box(7.8,2.9,2,1,'Native tool\nFictional workspace','#e3eef7')
box(3.3,.35,3.5,1.45,'Reviewer\nTask + candidate + tool schema\nFull: also recorded history\nMinimized: no recorded history','#f0eaf7')
arrow((2.25,3.4),(3.75,3.4),'Candidate',(0,.23))
arrow((6.35,3.4),(7.75,3.4),'Execute if allowed',(0,.23))
arrow((4.3,2.85),(4.3,1.85),'Packet',(-.45,0))
arrow((5.8,1.85),(5.8,2.85),'Decision',(.55,0))
ax.plot([8.8,8.8,1.2,1.2],[3.95,4.45,4.45,4.05],color='#405468',lw=1.1)
arrow((1.2,4.1),(1.2,3.93))
ax.text(5,4.65,'Tool returns may contain attacker text',fontsize=7,ha='center')
ax.text(1.4,.96,'Gate policy:\n4 allowlisted reads bypass review;\nother calls require approval.\nDenied calls do not execute.',fontsize=7,ha='center',va='center')
fig.tight_layout(pad=.3)
for ext in ('png','pdf'):fig.savefig(r/f'figures/native-review-flow-v1.{ext}',dpi=200)
(r/'manuscript/images/native-review-flow-v1.pdf').write_bytes((r/'figures/native-review-flow-v1.pdf').read_bytes())
