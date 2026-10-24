"""Run comparators and retain input/proof/metrics together for reproducibility."""

from dataclasses import replace

from .metrics import measure
from .models import Scenario
from .optimizer import SchedulingError, optimize
from .policies import immediate, rolling

POLICY_LABELS = {
    "immediate_edf": "Immediate execution",
    "battery_only": "Battery only",
    "compute_only": "Compute shifting only",
    "joint_oracle": "Joint / perfect forecast",
    "rolling_mpc": "GridWeave / rolling forecast",
}


def run_experiment(s: Scenario, carbon_price: float = 80.0,
                   include_ablations: bool = True) -> dict:
    s.validate()
    plans, errors = {}, {}

    def attempt(key, scenario, fn):
        try:
            plan = fn()
            metrics = measure(scenario, plan, carbon_price)
            plans[key] = {"label": POLICY_LABELS[key], "schedule": plan.to_dict(), "metrics": metrics}
            if not metrics["validation"]["valid"]:
                errors[key] = "; ".join(metrics["validation"]["errors"])
        except SchedulingError as exc:
            errors[key] = str(exc)

    attempt("immediate_edf", s, lambda: immediate(s))
    attempt("joint_oracle", s, lambda: optimize(s, carbon_price))
    attempt("rolling_mpc", s, lambda: rolling(s, carbon_price))
    if include_ablations:
        no_storage = replace(s, facility=replace(s.facility, battery_mwh=0, battery_mw=0))
        attempt("compute_only", no_storage,
                lambda: optimize(no_storage, carbon_price, policy="compute_only"))
        if "immediate_edf" in plans and "immediate_edf" not in errors:
            fixed = plans["immediate_edf"]["schedule"]["allocation_gpus"]
            attempt("battery_only", s,
                    lambda: optimize(s, carbon_price, fixed_allocation=fixed, policy="battery_only"))
        else:
            errors["battery_only"] = "Requires a feasible immediate compute schedule"
    savings = None
    if all(key in plans and key not in errors for key in ("immediate_edf", "rolling_mpc")):
        base, ours = (plans[key]["metrics"] for key in ("immediate_edf", "rolling_mpc"))
        savings = {
            "cost_pct": 100 * (1 - ours["operating_cost_usd"] / base["operating_cost_usd"])
            if base["operating_cost_usd"] else None,
            "carbon_pct": 100 * (1 - ours["carbon_kg"] / base["carbon_kg"])
            if base["carbon_kg"] else None,
            "objective_pct": 100 * (1 - ours["objective_usd"] / base["objective_usd"])
            if base["objective_usd"] else None,
        }
    regret = None
    if all(key in plans and key not in errors for key in ("joint_oracle", "rolling_mpc")):
        oracle, ours = (plans[key]["metrics"]["objective_usd"]
                        for key in ("joint_oracle", "rolling_mpc"))
        regret = 100 * (ours / oracle - 1) if oracle else None
    return {"schema_version": 1, "scenario": s.to_dict(), "carbon_price_usd_per_tonne": carbon_price,
            "policies": plans, "errors": errors, "savings_vs_immediate": savings,
            "rolling_regret_vs_oracle_pct": regret,
            "notes": ["All inputs are synthetic and do not predict real-world savings.",
                      "Oracle sees actual future renewables; rolling control sees only the current observation and future forecast.",
                      "Reserved jobs and inference demand are known; unexpected job arrivals are not modeled.",
                      "Operating cost excludes carbon externalities and hardware/renewable/storage capital costs."]}


def frontier(s: Scenario, weights=(0, 40, 80, 160, 400, 1000)) -> list[dict]:
    """Perfect-forecast weighted-sum frontier. Discrete battery modes can create gaps."""
    points = []
    for weight in weights:
        plan = optimize(s, weight)
        metrics = measure(s, plan, weight)
        points.append({"carbon_price_usd_per_tonne": weight, **metrics,
                       "solver_gap": plan.solver["relative_gap"]})
    return points
