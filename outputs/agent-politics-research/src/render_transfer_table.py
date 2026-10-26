"""Generate one table for complete paired repetitions, preserving denominators."""
import argparse
from summarize_transfer import ROOT, ARMS, collect, aggregate

p=argparse.ArgumentParser();p.add_argument('--repetitions',type=int,nargs='+',required=True)
args=p.parse_args();reps=sorted(args.repetitions)
assert reps==list(range(1,max(reps)+1)) and max(reps)<=3
summaries={rep:{r['arm']:r for r in aggregate(collect(ROOT/'results',rep))} for rep in reps}
labels={'ordinary':'Ordinary','hardened':'Hardened','full':'Full review','minimized':'Minimized'}
table=[r'\begin{tabular}{llrrrrr}',r'\toprule',
       r'Arm & Repeat & Clean & Attacked & AS & Safe & Exposed\\',r'\midrule']
for arm in ARMS:
    for rep in reps:
        r=summaries[rep][arm]
        clean_note=r'$^{\dagger}$' if r['clean_infrastructure_errors'] else ''
        table.append(f"{labels[arm]} & {rep} & {r['clean_utility']}/10{clean_note} & {r['attacked_utility']}/30 & {r['attack_success']}/30 & {r['safe_completion']}/30 & {r['actor_exact_payload_received']}/30 "+r'\\')
table += [r'\bottomrule',r'\end{tabular}']
(ROOT/'manuscript/transfer-repeated-table.tex').write_text('\n'.join(table)+'\n')
print('Wrote complete paired repetitions:',reps)
