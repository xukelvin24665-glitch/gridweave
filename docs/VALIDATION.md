# Delivery verification

Verified on 24 October 2026 using Python 3.13 on macOS with NumPy 2.5.4 and SciPy 1.18.1.

## Automated checks

- **26 tests passed**, covering analytic optima, exhaustive tiny-case enumeration, cost/carbon trade-offs, subhourly units, release/deadline boundaries, aggregate infeasibility, battery energy conservation, mutual exclusion, terminal energy, zero workloads, zero storage, oracle dominance, causal forecast access, closing-hours regressions, independent tamper detection, confidence intervals, holdout seed handling, input validation, static assets, and custom HTTP requests.
- **140 main cases** (seeds 0–19 across seven scenarios): all five policies independently feasible in every case, 700 policy evaluations.
- **140 holdout cases** (seeds 100–119 across seven scenarios): all five policies independently feasible in every case, 700 additional policy evaluations.
- The saved demonstration's five schedules passed the standalone validation command.
- The included custom scenario completed through both the CLI and HTTP API.
- The deliberately overloaded example reports infeasibility rather than a fabricated successful schedule.
- Packaged dashboard evidence matches the main benchmark summary.

These are local test results. GitHub Actions is configured for Python 3.12 and 3.13 on Linux but has not been run on GitHub as part of this local delivery. Cross-platform runtime and equally optimal schedules may differ.

## Browser checks

The actual local app was exercised at desktop and mobile breakpoints. Checks included chart switching, zero battery capacity, zero carbon value, a solar forecast shock, the six-point cost/carbon frontier, JSON download, status/constraint messages, local table overflow, and readable responsive chart dimensions. The exported JSON contains the same validated default results as the backend. No browser warning or script error was observed during the checked flows.

Saved views: [desktop overview](screenshots/dashboard.jpg), [mobile overview](screenshots/mobile.jpg), and [mobile battery chart](screenshots/mobile-chart.jpg).

## Reproduce

```bash
python -m unittest discover -s tests -v
python -m gridweave validate results/demo.json
python scripts/refresh_results.py
```

The full benchmark is evidence about this model and synthetic generator. It is not a production safety certificate, a measured carbon reduction, or a storage investment case. The retained unguarded failure and explicit limitations are part of the result.
