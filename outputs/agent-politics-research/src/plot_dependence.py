"""Plot saved synthetic results, never recompute data while rendering."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

base = Path(__file__).resolve().parents[1]
with (base/'results/dependence-v1/dependence.csv').open() as f:
    rows = [{k: float(v) for k,v in row.items()} for row in csv.DictReader(f)]
x = [r['coupling_weight'] for r in rows]
y = [100*r['b_mc_risk'] for r in rows]
fig, ax = plt.subplots(figsize=(8,4.8), constrained_layout=True)
ax.plot(x, [100*r['b_exact_risk'] for r in rows], color='#1967a3', label='B: exact joint risk')
ax.errorbar(x, y, yerr=[[100*(r['b_mc_risk']-r['b_ci_low']) for r in rows],
                      [100*(r['b_ci_high']-r['b_mc_risk']) for r in rows]],
            fmt='o', markersize=4, color='#1967a3', capsize=3,
            label='B: Monte Carlo, pointwise 95% CI')
ax.axhline(100*rows[0]['a_assumed_risk'], color='#b74728', linestyle='--', label='A: assumed risk (10%)')
ax.axvline(.375, color='#777777', linestyle=':', linewidth=1)
ax.text(.39, 2, 'Ranking reverses at 0.375', fontsize=10)
ax.set(xlabel='Mixture weight: independent → maximally shared failures',
       ylabel='Attack success probability (%)', ylim=(0,22), xlim=(-.025,1.025),
       title='Synthetic pilot: identical marginal error rates, different system risk')
ax.text(.02,.96,'Executor vulnerability = 20%; monitor miss marginal = 20%\nAll probabilities assumed; no LLM evaluations',
        transform=ax.transAxes,va='top',fontsize=9)
ax.legend(loc='lower right', fontsize=8)
ax.grid(axis='y',alpha=.2)
out = base/'figures'
out.mkdir(exist_ok=True)
fig.savefig(out/'dependence-pilot.png',dpi=180)
fig.savefig(out/'dependence-pilot.pdf')
print(out/'dependence-pilot.png')
