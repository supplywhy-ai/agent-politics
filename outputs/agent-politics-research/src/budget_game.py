"""Finite attack-family game under ASSUMED exponential response curves.

Defender publicly commits to a deterministic review budget x in [0,B].
Attacker selects a family after observing x. Payoff is single-action harm.
No empirical calibration; all family parameters below are synthetic.
"""
import argparse
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class Family:
    name: str
    p0: float
    alpha: float
    beta: float
    floor: float
    integrated_alpha: float

    def __post_init__(self):
        values = (self.p0, self.alpha, self.beta, self.floor, self.integrated_alpha)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Parameters must be finite')
        if not 0 < self.p0 <= 1 or not 0 <= self.floor <= 1:
            raise ValueError('Invalid probability')
        if min(self.alpha, self.beta, self.integrated_alpha) <= 0:
            raise ValueError('Response rates must be positive')


def check_budget(budget, x):
    if not math.isfinite(budget) or not math.isfinite(x) or budget < 0 or not 0 <= x <= budget:
        raise ValueError('Require 0 <= reviewer allocation <= total budget')


def risk(family, budget, x):
    check_budget(budget, x)
    proposal = family.p0 * math.exp(-family.alpha*(budget-x))
    conditional_miss = family.floor + (1-family.floor)*math.exp(-family.beta*x)
    return proposal*conditional_miss


def integrated_risk(family, budget):
    check_budget(budget, 0)
    return family.p0*math.exp(-family.integrated_alpha*budget)


def optimal_single(f, budget):
    check_budget(budget, 0)
    if f.beta <= f.alpha or f.floor >= 1-f.alpha/f.beta:
        return 0.0
    if f.floor == 0:
        return budget
    return min(budget, math.log((f.beta-f.alpha)*(1-f.floor)/(f.alpha*f.floor))/f.beta)


def worst_risk(families, budget, x):
    if not families:
        raise ValueError('At least one attack family required')
    return max(risk(f, budget, x) for f in families)


def optimal_robust(families, budget, iterations=120):
    """Golden-section minimization of a convex max of convex curves.

    Includes endpoints explicitly; flat optima may yield any minimizer.
    This is a continuous deterministic commitment, not a mixed-policy solver.
    """
    check_budget(budget, 0)
    objective = lambda x: worst_risk(families, budget, x)
    lo, hi = 0., budget
    ratio = (math.sqrt(5)-1)/2
    left, right = hi-ratio*(hi-lo), lo+ratio*(hi-lo)
    fl, fr = objective(left), objective(right)
    for _ in range(iterations):
        if fl <= fr:
            hi, right, fr = right, left, fl
            left = hi-ratio*(hi-lo)
            fl = objective(left)
        else:
            lo, left, fl = left, right, fr
            right = lo+ratio*(hi-lo)
            fr = objective(right)
    return min((0., budget, (lo+hi)/2), key=objective)


FAMILIES = (
    Family('review_sensitive', .20, .20, 1.20, .05, .35),
    Family('review_resistant', .16, .25, .40, .70, .30),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    budget = 4.0
    robust = optimal_robust(FAMILIES, budget)
    records = []
    for label, x in [('all_executor', 0.), ('all_reviewer', budget),
                     ('optimize_first_family', optimal_single(FAMILIES[0], budget)),
                     ('robust_commitment', robust)]:
        records.append({'allocation_rule': label, 'review_budget': x,
                        **{f.name: risk(f,budget,x) for f in FAMILIES},
                        'worst_risk': worst_risk(FAMILIES,budget,x)})
    with (args.out/'allocations.csv').open('w',newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    with (args.out/'curves.csv').open('w',newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['review_budget', *[f.name for f in FAMILIES], 'worst_risk'])
        for i in range(401):
            x = budget*i/400
            writer.writerow([x,*[risk(f,budget,x) for f in FAMILIES],worst_risk(FAMILIES,budget,x)])
    report = {'evidence_type': 'analytic_synthetic_game_not_empirical',
              'budget': budget, 'budget_units': 'abstract, not dollars or tokens',
              'families': [asdict(f) for f in FAMILIES],
              'parameter_provenance': 'All family parameters are assumptions; B is a design choice.',
              'a_worst_risk': max(integrated_risk(f,budget) for f in FAMILIES),
              'b_robust_review_budget': robust,
              'b_worst_risk': worst_risk(FAMILIES,budget,robust),
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'limitations': ['No normal task utility or false-block model',
                              'No empirical budget response calibration',
                              'Known finite attack set; no attack outside this set',
                              'Perfect gate and one action per trial',
                              'Attacker observes deterministic allocation',
                              'Conditional miss floor is not a measured correlation coefficient']}
    (args.out/'metadata.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
