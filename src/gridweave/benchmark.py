"""Paired multi-seed evaluation, including failures instead of cherry-picking."""

import csv
import json
from pathlib import Path
from statistics import mean, stdev

from scipy.stats import t as student_t

from .experiment import POLICY_LABELS, run_experiment
from .scenarios import SCENARIOS, generate_scenario


def interval(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "ci95_low": None, "ci95_high": None}
    center = mean(values)
    margin = float(student_t.ppf(0.975, len(values) - 1)) * stdev(values) / len(values)**0.5 if len(values) > 1 else None
    return {"n": len(values), "mean": center,
            "ci95_low": center - margin if margin is not None else None,
            "ci95_high": center + margin if margin is not None else None}


def run_benchmark(seeds: int = 20, carbon_price: float = 80.0,
                  kinds: list[str] | None = None, progress=None, *, seed_start: int = 0) -> dict:
    if not 1 <= seeds <= 1000:
        raise ValueError("seeds must be between 1 and 1000")
    if type(seed_start) is not int or not 0 <= seed_start <= 2**32 - seeds:
        raise ValueError("Invalid starting seed")
    rows, summaries = [], {}
    for kind in kinds or list(SCENARIOS):
        paired_cost, paired_carbon, regrets, gaps = [], [], [], []
        failures = []
        policy_metrics = {key: [] for key in POLICY_LABELS}
        for index in range(seeds):
            seed = seed_start + index
            r = run_experiment(generate_scenario(kind, seed), carbon_price)
            row = {"scenario": kind, "seed": seed, "errors": r["errors"],
                   "savings": r["savings_vs_immediate"],
                   "rolling_regret_pct": r["rolling_regret_vs_oracle_pct"], "policies": {}}
            for key, value in r["policies"].items():
                row["policies"][key] = {"metrics": value["metrics"], "solver": value["schedule"]["solver"]}
                # Preserve compact summary certificates rather than 24 repeated descriptions.
                row["policies"][key]["solver"].pop("subproblems", None)
                if value["metrics"]["validation"]["valid"]:
                    policy_metrics[key].append(value["metrics"])
                gap = value["schedule"]["solver"].get("relative_gap")
                if gap is not None:
                    gaps.append(gap)
            if r["savings_vs_immediate"]:
                paired_cost.append(r["savings_vs_immediate"]["cost_pct"])
                paired_carbon.append(r["savings_vs_immediate"]["carbon_pct"])
            if r["rolling_regret_vs_oracle_pct"] is not None:
                regrets.append(r["rolling_regret_vs_oracle_pct"])
            if r["errors"]:
                failures.append({"seed": seed, "errors": r["errors"]})
            rows.append(row)
            if progress:
                progress(kind, index + 1, seeds)
        summaries[kind] = {
            "attempted_seeds": seeds,
            "cost_savings_pct": interval(paired_cost),
            "carbon_savings_pct": interval(paired_carbon),
            "rolling_regret_pct": interval(regrets),
            "max_milp_gap": max(gaps, default=None),
            "failures": failures,
            "policies": {key: {
                "feasible_count": len(metrics),
                "mean_cost_usd": mean(v["operating_cost_usd"] for v in metrics) if metrics else None,
                "mean_carbon_kg": mean(v["carbon_kg"] for v in metrics) if metrics else None,
            } for key, metrics in policy_metrics.items()},
        }
    return {"schema_version": 1, "seed_range": [seed_start, seed_start + seeds - 1],
            "carbon_price_usd_per_tonne": carbon_price, "summaries": summaries, "runs": rows,
            "interpretation": "Paired percentages compare rolling control with immediate EDF on identical inputs. Student-t 95% confidence intervals describe synthetic seed variability, not uncertainty about real deployments. Failed comparisons are counted and listed; they are not silently assigned savings."}


def write_benchmark(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "benchmark.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    with (directory / "benchmark.csv").open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["scenario", "seed", "policy", "valid", "cost_usd", "carbon_kg", "objective_usd", "jobs_on_time", "solver_gap"])
        for run in report["runs"]:
            for key, value in run["policies"].items():
                m = value["metrics"]
                writer.writerow([run["scenario"], run["seed"], key, m["validation"]["valid"],
                                 m["operating_cost_usd"], m["carbon_kg"], m["objective_usd"],
                                 m["jobs_on_time"], value["solver"].get("relative_gap")])
    lines = ["# Reproducible experiment results", "", report["interpretation"], "",
             f"Carbon price: ${report['carbon_price_usd_per_tonne']:g}/tonne. Seeds: {report['seed_range'][0]}-{report['seed_range'][1]}. All data is synthetic.", "",
             "| Scenario | Valid paired runs | Cost saving, mean [95% CI] | CO2 saving, mean [95% CI] | Rolling objective regret vs oracle | Failed runs |",
             "|---|---:|---:|---:|---:|---:|"]

    def fmt(v):
        if v["mean"] is None:
            return "unavailable"
        if v["ci95_low"] is None:
            return f"{v['mean']:.2f}% (CI unavailable)"
        return f"{v['mean']:.2f}% [{v['ci95_low']:.2f}, {v['ci95_high']:.2f}]"

    for kind, summary in report["summaries"].items():
        lines.append(f"| {kind} | {summary['cost_savings_pct']['n']}/{summary['attempted_seeds']} | {fmt(summary['cost_savings_pct'])} | {fmt(summary['carbon_savings_pct'])} | {fmt(summary['rolling_regret_pct'])} | {len(summary['failures'])} |")
    lines += ["", "Savings include grid energy, the illustrative daily peak fee, and battery wear. CO2 is grid-import energy times the contemporaneous grid intensity, including battery charging. All on-time figures also require independent physical feasibility. The oracle bound applies to the stated model with perfect forecasts; rolling control has no global gap certificate.", "",
              "See `benchmark.json` for every run, constraint validation, policy ablations, failure details, and solver bounds; `benchmark.csv` is a tidy policy-level export.", ""]
    (directory / "RESULTS.md").write_text("\n".join(lines))
