"""Synthetic dependence experiment; no LLM calls or empirical safety claims."""
import argparse
import csv
import hashlib
import json
import math
import platform
import random
from pathlib import Path


def joint_cells(p, m, j):
    """D=dangerous proposal; M=monitor would allow a dangerous proposal.

    M is a counterfactual vulnerability on a standardized unsafe candidate,
    defined even when the executor does not propose that candidate.
    Cells: neither, D only, M only, both. j=P(D and M).
    """
    if not all(math.isfinite(x) and 0 <= x <= 1 for x in (p, m, j)):
        raise ValueError('Probabilities must be finite and in [0,1]')
    if j < max(0, p + m - 1) - 1e-12 or j > min(p, m) + 1e-12:
        raise ValueError('Joint probability violates Frechet bounds')
    return (max(0, 1-p-m+j), max(0, p-j), max(0, m-j), j)


def risk_bounds(p, m):
    joint_cells(p, m, min(p, m))
    return max(0, p+m-1), min(p, m)


def wilson(k, n, z=1.959963984540054):
    if n <= 0 or not 0 <= k <= n:
        raise ValueError('Invalid binomial counts')
    rate = k/n
    denominator = 1+z*z/n
    center = (rate+z*z/(2*n))/denominator
    radius = z*math.sqrt(rate*(1-rate)/n+z*z/(4*n*n))/denominator
    return max(0, center-radius), min(1, center+radius)


def sample_joint(p, m, j, n, seed):
    cells = joint_cells(p, m, j)
    thresholds = [sum(cells[:i+1]) for i in range(3)]
    counts = [0, 0, 0, 0]
    rng = random.Random(seed)
    for _ in range(n):
        u = rng.random()
        index = next((i for i, t in enumerate(thresholds) if u < t), 3)
        counts[index] += 1
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--n', type=int, default=100000)
    parser.add_argument('--seed', type=int, default=20261025)
    args = parser.parse_args()
    if args.n <= 0:
        parser.error('--n must be positive')
    args.out.mkdir(parents=True, exist_ok=True)
    p, m, pa = .2, .2, .1
    rows = []
    for i in range(11):
        weight = i/10
        # Mixture of independent coupling and maximally positive coupling.
        # Both have identical p and m. Weight is not generally Pearson rho.
        joint = (1-weight)*p*m + weight*min(p, m)
        counts = sample_joint(p, m, joint, args.n, args.seed+i)
        low, high = wilson(counts[3], args.n)
        rows.append(dict(coupling_weight=weight, executor_marginal=p,
                         monitor_miss_marginal=m, a_assumed_risk=pa,
                         b_exact_risk=joint, b_mc_risk=counts[3]/args.n,
                         b_ci_low=low, b_ci_high=high,
                         conditional_miss=joint/p, trials=args.n,
                         seed=args.seed+i, neither=counts[0],
                         executor_only=counts[1], monitor_only=counts[2],
                         both=counts[3]))
    with (args.out/'dependence.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        'experiment': 'synthetic_joint_dependence_pilot_v1',
        'evidence_type': 'assumed_probability_model_monte_carlo',
        'empirical_llm_evaluations': 0,
        'parameter_provenance': 'All probabilities and coupling weights are assumptions; n and seeds are design values.',
        'python': platform.python_version(),
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'n_per_cell': args.n, 'base_seed': args.seed,
        'assumptions': ['Perfect mandatory gate', 'Single decision per trial',
                        'IID trials within each coupling condition',
                        'Counterfactual monitor miss defined on unsafe candidate',
                        'No measured cost, utility, latency or adaptive adversary'],
        'risk_bounds': risk_bounds(p, m),
        'crossing_weight': (pa-p*m)/(min(p,m)-p*m),
        'intervals': 'Pointwise 95% Wilson intervals; Monte Carlo error only, not model uncertainty.'
    }
    (args.out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps({'rows': len(rows), 'trials': args.n*len(rows),
                      'crossing_weight': metadata['crossing_weight'],
                      'max_mc_absolute_error': max(abs(r['b_mc_risk']-r['b_exact_risk']) for r in rows)}))


if __name__ == '__main__':
    main()
