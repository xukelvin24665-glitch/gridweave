# HackSHSID 2026 submission answers

## Title

GridWeave — Smarter Compute. Cleaner Power.

## Short description

GridWeave co-schedules flexible AI jobs and battery storage around electricity prices and renewable power. It protects modeled deadlines and compares forecast-aware control with baselines and an optimal oracle using reproducible synthetic experiments.

251 characters, within the 300-character limit.

## Track

Sustainability

## Thumbnail image

Upload [gridweave-thumbnail.png](gridweave-thumbnail.png). This is a 1600 × 900 PNG, below 5 MB.

## Project inspiration and description

GridWeave began with a timing mismatch: AI workloads need computing power, but the cheapest and cleanest electricity is not always available when demand peaks. We interpreted the challenge as a joint scheduling problem: coordinate flexible AI jobs and battery storage while preserving fixed inference reservations and job deadlines.

Our prototype uses mixed-integer optimization to choose hourly compute allocations, grid imports, renewable consumption, and battery charging or discharging. Hard constraints enforce job completion, GPU capacity, grid limits, battery losses, and minimum energy reserves. The battery must end the day with its starting energy, so savings cannot come from simply leaving it empty. Operators can adjust a carbon value to explore the trade-off between operating cost and emissions.

For uncertain renewable supply, a rolling controller observes current conditions and replans each hour using future forecasts. A conservative closing-hours guard helps protect the battery’s required final charge. The dashboard makes these decisions visible through power charts, a workload heatmap, policy comparisons, and a cost–carbon frontier.

The project’s distinguishing contribution is its inspectable evidence: five policies separate the effects of compute shifting and storage; a perfect-forecast oracle provides a numerical optimization bound; and a separate validator checks the resulting schedules. We evaluated 280 synthetic scenarios across seven conditions, including forecast shocks, price spikes, tight deadlines, and grid stress.

All data is explicitly synthetic. This is a reproducible research prototype, not a live data-center controller or a claim of measured industry savings. Its assumptions and failure boundaries are documented, including known job reservations, divisible workloads, and excluded capital costs.

## Public GitHub repository link

https://github.com/xukelvin24665-glitch/gridweave

## Testing evidence — text

All 26 automated tests passed. Coverage includes analytic optima, exhaustive tiny-case enumeration, workload deadlines, GPU and grid limits, battery energy conservation, infeasible inputs, forecast causality, and HTTP/API behavior.

We evaluated 280 synthetic scenarios: 140 main cases using seeds 0–19 and 140 holdout cases using seeds 100–119, across seven conditions. All five policies passed independent physical and service checks in every case, totaling 1,400 feasible policy evaluations.

On the default synthetic day, rolling control reduced operating cost from $616.23 to $350.84 (43.1%) and grid emissions from 3,835.22 kg to 2,785.47 kg CO2 (27.4%), with all 16 jobs on time. Across the 20 main balanced-day seeds, mean savings were 39.80% for cost and 26.57% for emissions, with paired 95% confidence intervals reported in the results.

These results demonstrate behavior within the stated model and synthetic generator; they are not measurements from an operating data center.

## Testing evidence — image uploads and captions

1. [01-dashboard.jpg](evidence/01-dashboard.jpg) — Working dashboard on the default synthetic day: 16/16 jobs on time, 43.1% lower operating cost, and 27.4% fewer grid emissions versus immediate execution.
2. [02-stress-tests.png](evidence/02-stress-tests.png) — Seven scenario families, 20 main seeds each. Bars show mean paired cost and emissions savings; error bars show 95% confidence intervals. All inputs are synthetic.
3. [03-policy-comparison.png](evidence/03-policy-comparison.png) — Five policies on identical default inputs isolate compute shifting, battery storage, and joint control. Perfect-forecast policies are labeled separately from rolling control.
4. [04-test-results.png](evidence/04-test-results.png) — Summary rendered from the actual execution log: all 26 automated tests passed. Raw log retained in unit-tests.txt; 280 synthetic cases also passed feasibility checks.

All four images are below 5 MB. [Full test log](evidence/unit-tests.txt).

## AI statement

We used OpenAI Codex extensively to design and implement the prototype, generate synthetic scenarios, write documentation and submission materials, and run automated tests and validation. AI assistance included the optimizer and dashboard code. All reported performance figures come from executed synthetic experiments, not measurements from an operating data center.

## Video link (optional)

Leave blank. No demo video has been published.

## Regenerating the graphics

The thumbnail extends the existing project branding. Evidence charts use the committed results, and the test-summary image uses the actual captured log. To regenerate them:

```bash
python -m pip install -e '.[submission]'
python -m unittest discover -s tests -v > submission/evidence/unit-tests.txt 2>&1
python scripts/build_submission_assets.py
```
