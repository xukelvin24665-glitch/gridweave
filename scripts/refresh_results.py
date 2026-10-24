"""Refresh every committed evidence snapshot from one reproducible command."""

import json
from pathlib import Path

from gridweave.benchmark import run_benchmark, write_benchmark
from gridweave.experiment import frontier, run_experiment
from gridweave.scenarios import generate_scenario

root = Path(__file__).resolve().parents[1]
out = root / "results"
out.mkdir(exist_ok=True)
report = run_benchmark(20, progress=lambda kind, seed, total: print(f"{kind}: {seed}/{total}", flush=True) if seed == total else None)
write_benchmark(report, out)
holdout = run_benchmark(20, seed_start=100, progress=lambda kind, seed, total: print(f"holdout {kind}: {seed}/{total}", flush=True) if seed == total else None)
write_benchmark(holdout, out / "holdout")
summary = {key: value for key, value in report.items() if key != "runs"}
(root / "src/gridweave/web/evidence.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
scenario = generate_scenario()
demo = run_experiment(scenario)
demo["frontier"] = frontier(scenario)
(out / "demo.json").write_text(json.dumps(demo, indent=2, allow_nan=False) + "\n")
(root / "examples").mkdir(exist_ok=True)
(root / "examples/balanced.json").write_text(json.dumps(scenario.to_dict(), indent=2, allow_nan=False) + "\n")
print("Refreshed results, dashboard evidence, and custom-input example.")
if any(summary["failures"] for r in (report, holdout) for summary in r["summaries"].values()):
    raise SystemExit("One or more runs failed; inspect results/benchmark.json.")
