"""Plot complete repetitions side by side without pooling dependent episodes."""
import csv
from pathlib import Path
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
ARMS=['ordinary','hardened','full','minimized']

def main():
    rows=list(csv.DictReader((ROOT/'results/transfer-three-repetitions-summary-v1.csv').open()))
    index={(int(r['repetition']),r['arm']):r for r in rows}
    assert len(rows)==len(index)==12
    assert set(index)=={(rep,arm) for rep in (1,2,3) for arm in ARMS}
    assert all(int(r['clean_n'])==10 and int(r['attack_n'])==30 for r in rows)
    plt.rcParams.update({'font.size':8})
    fig,axes=plt.subplots(2,2,figsize=(7,5.4))
    panels=[('clean_utility','Clean native task successes',10),
            ('safe_completion','Native utility without attacker success',30),
            ('attack_success','Native attacker-goal successes',30),
            ('tokens','Confirmed tokens, clean + attacked',None)]
    colors=['#336d9c','#b16b29','#398979']
    for ax,(key,title,denom) in zip(axes.flat,panels):
        for rep,color in zip((1,2,3),colors):
            values=[]
            for arm in ARMS:
                row=index[(rep,arm)]
                values.append((int(row['clean_tokens'])+int(row['attack_tokens']))/1000
                              if key=='tokens' else int(row[key]))
            x=[i+(rep-2)*.24 for i in range(4)]
            bars=ax.bar(x,values,width=.22,color=color,label=f'Repetition {rep}')
            labels=[(('≥' if key=='tokens' and not int(index[(rep,arm)]['clean_tokens_complete']) else '')+f'{v:.0f}') for arm,v in zip(ARMS,values)]
            ax.bar_label(bars,labels=labels,fontsize=6,padding=2)
        ax.set_xticks(range(4),['Ordinary','Hardened','Full','Minimized'])
        ax.set_title(title,fontsize=9)
        ax.spines[['top','right']].set_visible(False)
        if denom:
            ax.set_ylim(0,denom*1.15);ax.set_ylabel(f'Count / {denom}')
        else:
            ax.set_ylim(0,ax.get_ylim()[1]*1.12);ax.set_ylabel('Thousands of tokens')
        ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    handles,labels=axes.flat[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='upper center',ncol=3,frameon=False)
    fig.tight_layout(rect=(0,0,1,.94),h_pad=2)
    for ext in ('png','pdf'):
        fig.savefig(ROOT/f'figures/transfer-three-repetitions-v1.{ext}',dpi=200)
    (ROOT/'manuscript/images/transfer-three-repetitions-v1.pdf').write_bytes(
        (ROOT/'figures/transfer-three-repetitions-v1.pdf').read_bytes())
    plt.close(fig)

if __name__=='__main__':main()
