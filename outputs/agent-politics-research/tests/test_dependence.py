import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from dependence_pilot import joint_cells, risk_bounds, sample_joint, wilson


class DependenceTests(unittest.TestCase):
    def test_all_grid_endpoints_preserve_marginals(self):
        for a in range(11):
            for b in range(11):
                p, m = a/10, b/10
                for j in risk_bounds(p, m):
                    cells = joint_cells(p, m, j)
                    self.assertAlmostEqual(sum(cells), 1)
                    self.assertAlmostEqual(cells[1]+cells[3], p)
                    self.assertAlmostEqual(cells[2]+cells[3], m)
                    self.assertTrue(all(c >= 0 for c in cells))

    def test_impossible_joint_rejected(self):
        for p, m, j in [(.2,.2,.3), (.9,.9,.5), (math.nan,.2,.1)]:
            with self.assertRaises(ValueError):
                joint_cells(p, m, j)

    def test_rank_reversal_same_marginals(self):
        lo, hi = risk_bounds(.2, .2)
        self.assertLess(lo, .1)
        self.assertGreater(hi, .1)
        self.assertLess(.2*.2, .1)

    def test_degenerate_sampling(self):
        self.assertEqual(sample_joint(1,1,1,100,0), [0,0,0,100])
        self.assertEqual(sample_joint(0,0,0,100,0), [100,0,0,0])

    def test_sampler_agrees_with_analytic_multinomial(self):
        n = 100000
        expected = joint_cells(.2,.3,.12)
        counts = sample_joint(.2,.3,.12,n,42)
        for count, p in zip(counts, expected):
            self.assertLess(abs(count/n-p), 6*math.sqrt(p*(1-p)/n))
        self.assertEqual(counts, sample_joint(.2,.3,.12,n,42))

    def test_wilson_boundaries(self):
        self.assertAlmostEqual(wilson(0,100)[0], 0)
        self.assertAlmostEqual(wilson(100,100)[1], 1)
        low, high = wilson(50,100)
        self.assertAlmostEqual(low, 1-high)


if __name__ == '__main__':
    unittest.main()
