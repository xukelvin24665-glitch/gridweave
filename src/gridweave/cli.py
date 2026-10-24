import argparse
import json
from pathlib import Path
import sys

from .benchmark import run_benchmark, write_benchmark
from .experiment import frontier, run_experiment
from .models import Scenario, Schedule
from .optimizer import SchedulingError
from .scenarios import SCENARIOS, generate_scenario
from .server import serve
from .validation import validate_schedule


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GridWeave | Smarter Compute. Cleaner Power.")
    sub = parser.add_subparsers(dest="command", required=True)
    web = sub.add_parser("serve", help="Open the local dashboard server")
    web.add_argument("--port", type=int, default=8765)
    demo = sub.add_parser("demo", help="Run all policies on a reproducible synthetic day")
    demo.add_argument("--scenario", choices=SCENARIOS, default="balanced")
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--battery", type=float, default=2.4)
    demo.add_argument("--carbon-price", type=float, default=80)
    demo.add_argument("--output", type=Path, default=Path("results/demo.json"))
    demo.add_argument("--frontier", action="store_true")
    bench = sub.add_parser("benchmark", help="Run paired stress experiments and confidence intervals")
    bench.add_argument("--seeds", type=int, default=20)
    bench.add_argument("--seed-start", type=int, default=0)
    bench.add_argument("--carbon-price", type=float, default=80)
    bench.add_argument("--scenario", choices=SCENARIOS, action="append")
    bench.add_argument("--output-dir", type=Path, default=Path("results"))
    solve = sub.add_parser("solve", help="Run a custom scenario JSON file")
    solve.add_argument("--input", type=Path, required=True)
    solve.add_argument("--output", type=Path, default=Path("output/experiment.json"))
    solve.add_argument("--carbon-price", type=float, default=80)
    validate = sub.add_parser("validate", help="Independently validate saved experiment schedules")
    validate.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            serve(args.port)
        elif args.command in ("demo", "solve"):
            s = (generate_scenario(args.scenario, args.seed, args.battery) if args.command == "demo"
                 else Scenario.from_dict(json.loads(args.input.read_text())))
            r = run_experiment(s, args.carbon_price)
            if getattr(args, "frontier", False):
                r["frontier"] = frontier(s)
            write_json(args.output, r)
            print(f"Saved {args.output.resolve()}")
            for key, value in r["policies"].items():
                m = value["metrics"]
                print(f"{key:16} ${m['operating_cost_usd']:8.2f}  {m['carbon_kg']:8.1f} kg CO2  "
                      f"{m['jobs_on_time']}/{m['jobs_total']} jobs  valid={m['validation']['valid']}")
            if r["errors"]:
                print(json.dumps(r["errors"], indent=2), file=sys.stderr)
                return 2
        elif args.command == "benchmark":
            def progress(kind, seed, total):
                if seed == total:
                    print(f"Completed {kind}: {total} seeds", flush=True)
            report = run_benchmark(args.seeds, args.carbon_price, args.scenario, progress, seed_start=args.seed_start)
            write_benchmark(report, args.output_dir)
            print(f"Saved {args.output_dir.resolve() / 'RESULTS.md'}")
            if any(summary["failures"] for summary in report["summaries"].values()):
                return 2
        elif args.command == "validate":
            data = json.loads(args.input.read_text())
            s = Scenario.from_dict(data["scenario"])
            from dataclasses import replace
            invalid = bool(data.get("errors"))
            for key, value in data["policies"].items():
                scenario = replace(s, facility=replace(s.facility, battery_mwh=0, battery_mw=0)) if key == "compute_only" else s
                result = validate_schedule(scenario, Schedule(**value["schedule"]))
                print(key, json.dumps(result))
                invalid |= not result["valid"]
            return 2 if invalid else 0
    except (ValueError, KeyError, TypeError, OSError, SchedulingError) as exc:
        print(f"GridWeave: {exc}", file=sys.stderr)
        return 2
    return 0
