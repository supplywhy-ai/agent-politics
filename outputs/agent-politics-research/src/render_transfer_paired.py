"""Per-task plots from complete verified paired-cohort episode tables."""
import argparse
import csv
from pathlib import Path
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
ARMS=['ordinary','hardened','full','minimized']
TASKS=[1,3,8,9,14,15,17,18,29,34]

def main():
    p=argparse.ArgumentParser();p.add_argument('--repetition',type=int,choices=[1,2,3],required=True);a=p.parse_args()
    stem=f'transfer-r{a.repetition}-paired'
    rows=list(csv.DictReader((ROOT/f'results/{stem}-episodes-v1.csv').open()))
    keys={(r['cohort'],r['arm'],r['episode_id']) for r in rows}
    assert len(rows)==len(keys)==160
    plt.rcParams.update({'font.size':8})
    fig,axes=plt.subplots(4,1,figsize=(7,7.8))
    specs=[('clean','native_utility',1,'Clean native utility','GnBu'),
           ('attack','safe_completion',3,'Native utility with no native attacker success','GnBu'),
           ('attack','attack_success',3,'Native attacker-goal success','Reds'),
           ('attack','actor_tool_prompt',3,'Exact attack payload delivered to actor prompt','Purples')]
    for ax,(cohort,key,denom,title,cmap) in zip(axes,specs):
        vals=[]
        for arm in ARMS:
            cells=[]
            for task in TASKS:
                cell=[r for r in rows if r['cohort']==cohort and r['arm']==arm and r['task_id']==f'user_task_{task}']
                assert len(cell)==denom
                cells.append(sum(int(r[key]) for r in cell))
            vals.append(cells)
        ax.imshow(vals,vmin=0,vmax=denom,cmap=cmap,aspect='auto')
        ax.set_xticks(range(10),[str(t) for t in TASKS]);ax.set_yticks(range(4),['Ordinary','Hardened','Full review','Minimized'])
        ax.set_title(title,fontsize=9);ax.set_xlabel('Task ID')
        for i,row in enumerate(vals):
            for j,v in enumerate(row):ax.text(j,i,f'{v}/{denom}',ha='center',va='center',fontsize=8,color='white' if v>denom*.55 else '#222222')
    fig.tight_layout(pad=.8,h_pad=1.2)
    for ext in ['png','pdf']:fig.savefig(ROOT/f'figures/{stem}-v1.{ext}',dpi=180)
    (ROOT/f'manuscript/images/{stem}-v1.pdf').write_bytes((ROOT/f'figures/{stem}-v1.pdf').read_bytes())
    plt.close(fig)

if __name__=='__main__':main()
