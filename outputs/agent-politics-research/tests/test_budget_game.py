import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from budget_game import Family, risk, optimal_single, optimal_robust, worst_risk, FAMILIES


class BudgetTests(unittest.TestCase):
    def test_closed_form_against_exhaustive_grid(self):
        for alpha in (.1,.5,1.):
            for beta in (.2,.8,2.):
                for floor in (0.,.01,.5,1.):
                    f = Family('test',.3,alpha,beta,floor,.4)
                    x = optimal_single(f,3.)
                    grid_min = min(risk(f,3.,3*i/3000) for i in range(3001))
                    self.assertLessEqual(risk(f,3.,x), grid_min+1e-12)
                    numerical = optimal_robust([f],3.)
                    self.assertAlmostEqual(risk(f,3.,x),risk(f,3.,numerical),places=11)

    def test_minimax_against_grid_and_attacker_best_response(self):
        x = optimal_robust(FAMILIES,4.)
        v = worst_risk(FAMILIES,4.,x)
        grid_min = min(worst_risk(FAMILIES,4.,i/10000) for i in range(40001))
        self.assertLessEqual(v,grid_min+1e-12)
        self.assertLess(grid_min-v,1e-5)
        # This fixture has an interior crossing; both attacks bind.
        self.assertAlmostEqual(risk(FAMILIES[0],4.,x),risk(FAMILIES[1],4.,x),places=10)

    def test_endpoint_and_zero_budget_cases(self):
        f = Family('perfect_floor',.2,.2,1.2,1.,.3)
        self.assertEqual(optimal_single(f,4),0)
        self.assertEqual(optimal_robust([f],4),0)
        self.assertEqual(optimal_robust(FAMILIES,0),0)
        self.assertEqual(risk(f,0,0),.2)

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            Family('bad',.2,0,1,.2,.3)
        for x in (-1,5,math.nan):
            with self.assertRaises(ValueError):
                risk(FAMILIES[0],4,x)

    def test_targeted_allocation_can_lose_to_adaptation(self):
        targeted = optimal_single(FAMILIES[0],4)
        robust = optimal_robust(FAMILIES,4)
        self.assertGreater(worst_risk(FAMILIES,4,targeted),worst_risk(FAMILIES,4,robust))


if __name__ == '__main__':
    unittest.main()
