"""Fixed-cohort budget heatmaps, no interpolation or inferential statistics."""
import argparse
import csv
from pathlib import Path

ARMS=['ordinary','hardened','self','full','minimized']
LABELS=['Ordinary executor','Hardened executor','Self-role full review',
        'Independent full review','Independent minimized']

def main():
    p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True)
    p.add_argument('--figure',type=Path,required=True);p.add_argument('--table',type=Path,required=True)
    a=p.parse_args()
    rows=list(csv.DictReader(a.csv.open()))
    budgets=sorted({int(r['budget']) for r in rows})
    lookup={(r['arm'],int(r['budget'])):r for r in rows}
    assert len(lookup)==len(rows)==len(ARMS)*len(budgets)
    assert all(int(r['clean_n'])==int(r['attack_n'])==3 for r in rows)
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12.8,7.5))
    specifications=[('clean_utility','Clean task success (native score) ↑','GnBu',3),
                    ('attack_success','Attacker goals achieved ↓','Reds',3),
                    ('attacked_utility','Attacked task success (native score) ↑','GnBu',3),
                    ('exhausted','Episodes exhausting budget ↓','Greys',6)]
    for ax,(key,title,cmap,denom) in zip(axes.flat,specifications):
        values=[]
        for arm in ARMS:
            values.append([int(lookup[arm,b]['clean_exhausted'])+int(lookup[arm,b]['attack_exhausted'])
                           if key=='exhausted' else int(lookup[arm,b][key]) for b in budgets])
        ax.imshow(values,cmap=cmap,vmin=0,vmax=denom,aspect='auto')
        ax.set_xticks(range(len(budgets)),[f'{b//1000}k' for b in budgets])
        ax.set_yticks(range(len(ARMS)),LABELS)
        ax.set_title(title,fontsize=12);ax.set_xlabel('Per-episode input + output token cap')
        for i,row in enumerate(values):
            for j,value in enumerate(row):
                ax.text(j,i,f'{value}/{denom}',ha='center',va='center',
                        color='white' if value>denom*.55 else '#222222',fontsize=11)
    fig.suptitle('Native budget development matrix — Qwen3-4B, 4-bit',fontsize=15)
    fig.text(.02,.02,'Clean: 3 fixed tasks. Attacked: 3 payloads on ONE calendar task. One run per cell.\nEqual token caps do not imply equal compute or actual consumption. Self-review is a role-prompt control.\nTask success uses the native scorer and may coexist with exhaustion before the final reply. No general robustness claim.',fontsize=9)
    fig.tight_layout(rect=(0,.1,1,.95))
    for ext in ('png','pdf'):fig.savefig(a.figure.with_suffix('.'+ext),dpi=180)
    plt.close(fig)
    lines=[r'\begin{tabular}{rlrrrr}',r'\toprule',
           r'Cap & Configuration & Clean & AS & Attacked & Exhausted \\',r'\midrule']
    for b in budgets:
        for arm,label in zip(ARMS,LABELS):
            r=lookup[arm,b];ex=int(r['clean_exhausted'])+int(r['attack_exhausted'])
            lines.append(f"{b//1000}k & {label} & {r['clean_utility']}/3 & {r['attack_success']}/3 & {r['attacked_utility']}/3 & {ex}/6 "+r'\\')
        lines.append(r'\midrule')
    lines[-1]=r'\bottomrule';lines.append(r'\end{tabular}')
    a.table.write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
