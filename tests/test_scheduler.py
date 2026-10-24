from dataclasses import replace
import itertools
import math
import unittest

from gridweave.experiment import frontier, run_experiment
from gridweave.metrics import measure
from gridweave.models import Facility, Job, Scenario
from gridweave.optimizer import SchedulingError, optimize
from gridweave.policies import immediate, rolling
from gridweave.scenarios import SCENARIOS, generate_scenario
from gridweave.validation import validate_schedule


def tiny(prices=(100, 10, 100), carbon=(100, 1000, 100), dt=1.0):
    h = len(prices)
    return Scenario("tiny", 0, list(prices), list(carbon), [0.0] * h, [0.0] * h,
                    [0.0] * h, [Job("j", "Tiny job", 0, h, 2 * dt, 2)],
                    Facility(total_gpus=2, idle_it_mw=0, mw_per_gpu=1, pue=1,
                             grid_limit_mw=10, battery_mwh=0, battery_mw=0,
                             peak_usd_per_mw_day=0), slot_hours=dt)


class ModelTests(unittest.TestCase):
    def test_round_trip_and_seed_reproducibility(self):
        s = generate_scenario(seed=123)
        self.assertEqual(s.to_dict(), Scenario.from_dict(s.to_dict()).to_dict())
        self.assertEqual(s.to_dict(), generate_scenario(seed=123).to_dict())
        self.assertNotEqual(s.renewable_mw, generate_scenario(seed=124).renewable_mw)

    def test_rejects_unphysical_inputs(self):
        s = tiny()
        for field, value in [("pue", 0.9), ("charge_efficiency", 1.1),
                             ("discharge_efficiency", 0), ("battery_mwh", -1),
                             ("initial_soc_fraction", 1.1), ("grid_limit_mw", math.nan)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                replace(s, facility=replace(s.facility, **{field: value})).validate()
        for s2 in [replace(s, price_usd_per_mwh=[1]), replace(s, seed=-1),
                   replace(s, jobs=s.jobs * 2), replace(s, inference_gpus=[3, 0, 0]),
                   replace(s, renewable_mw=[0, -1, 0]),
                   replace(s, jobs=[replace(s.jobs[0], deadline=0)]),
                   replace(s, jobs=[replace(s.jobs[0], release=True)]),
                   replace(s, jobs=[replace(s.jobs[0], work_gpu_h=100)])]:
            with self.subTest(scenario=s2), self.assertRaises(ValueError):
                s2.validate()

    def test_bad_json_structure_is_user_error(self):
        for data in [[], {}, {"jobs": None}, {**tiny().to_dict(), "facility": {"wrong": 1}}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                Scenario.from_dict(data)


class OptimizationTests(unittest.TestCase):
    def test_known_cost_optimum(self):
        s = tiny()
        plan = optimize(s, 0)
        self.assertEqual(plan.allocation_gpus, [[0.0, 2.0, 0.0]])
        self.assertAlmostEqual(measure(s, plan, 0)["operating_cost_usd"], 20)
        self.assertEqual(plan.solver["relative_gap"], 0)

    def test_carbon_value_changes_decision(self):
        s = tiny()
        cost = measure(s, optimize(s, 0), 0)
        green = measure(s, optimize(s, 200), 200)
        self.assertLess(green["carbon_kg"], cost["carbon_kg"])
        self.assertGreater(green["operating_cost_usd"], cost["operating_cost_usd"])

    def test_matches_exhaustive_tiny_enumeration(self):
        s = tiny(prices=(70, 10), carbon=(300, 700))
        # Independently enumerate all allocations in 0.1 GPU increments.
        costs = []
        for a, b in itertools.product(range(21), repeat=2):
            if a + b == 20:
                costs.append(a / 10 * (70 + 80 * .3) + b / 10 * (10 + 80 * .7))
        plan = optimize(s, 80)
        self.assertAlmostEqual(measure(s, plan, 80)["objective_usd"], min(costs), places=7)
        self.assertAlmostEqual(plan.solver["dual_bound_usd"], min(costs), places=7)

    def test_subhourly_units(self):
        s = tiny(prices=(100,), carbon=(400,), dt=.25)
        m = measure(s, optimize(s, 0), 0)
        self.assertAlmostEqual(m["work_gpu_h"], .5)
        self.assertAlmostEqual(m["grid_mwh"], .5)
        self.assertAlmostEqual(m["operating_cost_usd"], 50)
        self.assertAlmostEqual(m["carbon_kg"], 200)

    def test_release_and_exclusive_deadline(self):
        s = tiny()
        s = replace(s, jobs=[replace(s.jobs[0], release=1, deadline=2)])
        p = optimize(s)
        self.assertEqual(p.allocation_gpus, [[0, 2, 0]])

    def test_joint_capacity_infeasible_is_reported(self):
        s = tiny()
        s = replace(s, jobs=[Job("a", "A", 0, 3, 4, 2), Job("b", "B", 0, 3, 4, 2)])
        with self.assertRaises(SchedulingError) as caught:
            optimize(s)
        self.assertEqual(caught.exception.status, 2)
        r = run_experiment(s)
        self.assertIn("joint_oracle", r["errors"])
        self.assertIsNone(r["savings_vs_immediate"])
        self.assertFalse(r["policies"]["immediate_edf"]["metrics"]["validation"]["valid"])

    def test_battery_conservation_terminal_and_modes(self):
        s = generate_scenario()
        p = optimize(s)
        self.assertTrue(validate_schedule(s, p)["valid"])
        self.assertAlmostEqual(p.soc_mwh[0], p.soc_mwh[-1])
        self.assertGreater(sum(p.charge_mw), 0)
        self.assertTrue(all(min(c, d) < 1e-7 for c, d in zip(p.charge_mw, p.discharge_mw)))
        stored = sum(p.charge_mw) * s.facility.charge_efficiency
        spent = sum(p.discharge_mw) / s.facility.discharge_efficiency
        self.assertAlmostEqual(stored, spent, places=6)

    def test_oracle_dominates_feasible_comparators(self):
        r = run_experiment(generate_scenario())
        self.assertEqual(r["errors"], {})
        best = r["policies"]["joint_oracle"]["metrics"]["objective_usd"]
        for key, value in r["policies"].items():
            self.assertTrue(value["metrics"]["validation"]["valid"], key)
            self.assertLessEqual(best, value["metrics"]["objective_usd"] + 1e-4, key)

    def test_frontier_monotonic_tradeoff(self):
        points = frontier(tiny(), weights=(0, 80, 200, 1000))
        for a, b in zip(points, points[1:]):
            self.assertLessEqual(b["carbon_kg"], a["carbon_kg"] + 1e-5)
            self.assertGreaterEqual(b["operating_cost_usd"] + 1e-5, a["operating_cost_usd"])

    def test_zero_workloads_and_zero_renewables(self):
        s = replace(tiny(), jobs=[])
        p = optimize(s)
        self.assertTrue(validate_schedule(s, p)["valid"])
        self.assertEqual(measure(s, p)["deadline_success_pct"], 100)

    def test_no_battery_regression(self):
        s = generate_scenario(battery_mwh=0)
        p = optimize(s)
        self.assertTrue(validate_schedule(s, p)["valid"])
        self.assertEqual(sum(p.charge_mw + p.discharge_mw + p.soc_mwh), 0)

    def test_all_stress_conditions(self):
        for kind in SCENARIOS:
            for seed in (0, 7):
                with self.subTest(kind=kind, seed=seed):
                    s = generate_scenario(kind, seed)
                    p = rolling(s)
                    self.assertTrue(validate_schedule(s, p)["valid"])
                    self.assertIsNone(p.solver["relative_gap"])

    def test_rolling_first_action_cannot_see_future_actuals(self):
        a = generate_scenario()
        actual = a.renewable_mw.copy()
        actual[8:] = [v * .2 for v in actual[8:]]
        b = replace(a, renewable_mw=actual)
        pa, pb = rolling(a), rolling(b)
        self.assertAlmostEqual(pa.grid_mw[0], pb.grid_mw[0])
        self.assertAlmostEqual(pa.charge_mw[0], pb.charge_mw[0])
        for xa, xb in zip(pa.allocation_gpus, pb.allocation_gpus):
            self.assertAlmostEqual(xa[0], xb[0])

    def test_terminal_guard_covers_observed_grid_stress_regressions(self):
        for seed in (6, 8, 11, 16, 19):
            with self.subTest(seed=seed):
                s = generate_scenario("grid_stress", seed)
                self.assertTrue(validate_schedule(s, rolling(s))["valid"])

    def test_unguarded_controller_failure_is_visible(self):
        s = generate_scenario("grid_stress", 6)
        with self.assertRaises(SchedulingError):
            rolling(s, terminal_guard_slots=0)


class IndependentValidationTests(unittest.TestCase):
    def test_detects_tampered_schedule(self):
        s = generate_scenario()
        for kind in ("power", "work", "soc", "simultaneous", "grid", "nan", "shape"):
            p = immediate(s)
            if kind == "power": p.grid_mw[0] += .1
            elif kind == "work": p.allocation_gpus[0][0] += 1
            elif kind == "soc": p.soc_mwh[-1] = 0
            elif kind == "simultaneous": p.charge_mw[0] = p.discharge_mw[0] = .2
            elif kind == "grid": p.grid_mw[0] = 20
            elif kind == "nan": p.grid_mw[0] = math.nan
            else: p.grid_mw.pop()
            with self.subTest(kind=kind):
                self.assertFalse(validate_schedule(s, p)["valid"])


if __name__ == "__main__":
    unittest.main()
