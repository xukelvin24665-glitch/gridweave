# GridWeave: judge presentation and Q&A

## Four-minute presentation

**0:00–0:30 — Problem and decision.**

“AI demand and clean power do not arrive together. We ask which work must run now, which work can wait, and whether a battery should store energy or deliver it. GridWeave coordinates those decisions while keeping reserved inference and job deadlines fixed.”

**0:30–1:10 — What good means.**

“Good means lower operating cost and fewer grid emissions with no modeled service or physical violations. Cost includes electricity, battery wear, and a small illustrative peak fee. A visible carbon value lets the operator state how much to prioritize emissions. All inputs in this demonstration are synthetic, and they are exported so the experiment can be repeated.”

**1:10–2:00 — Live demonstration.**

Open the dashboard with seed 42, balanced weather, 2.4 MWh storage, and $80/tonne. Run the experiment. Read the actual cost and emissions savings shown on the cards. Show all 16 on-time jobs, switch between Power, Compute, and Battery, and point to a workload's deadline in the heatmap. Explain that the battery returns to its starting energy: it cannot manufacture a saving by ending empty.

**2:00–2:40 — Evidence and optimality.**

Show the five-policy comparison. Immediate execution is the simple baseline. Two ablations isolate compute shifting and storage. The perfect-forecast joint oracle supplies a numerical lower bound. The rolling controller only sees current actual renewable power and future forecasts. Read the displayed oracle gap and rolling regret; do not call the rolling controller globally optimal.

**2:40–3:25 — Robustness.**

Switch to Unexpected solar shortfall and run again. Then show the saved benchmark table: 20 seeds across seven conditions, with confidence intervals and failure counts. Explain the conservative closing-hours guard. Without that guard, grid-stress seed 6 demonstrates a final battery-restoration failure. There is a retained automated test for that boundary.

**3:25–4:00 — Limitations and next experiment.**

“Our current guarantees are inside the model. GPU equivalents are fluid, all reservations are known, PUE is fixed, and capital costs are excluded. We would next replay real traces, calibrate server power, add checkpoint and placement overhead, test forecast errors and unexpected arrivals, and evaluate storage investment separately. Our contribution is a complete, inspectable co-scheduling experiment with honest bounds and a practical rolling controller.”

## Answers to likely questions

**Why use a weighted carbon objective?** It makes the trade-off explicit in consistent monetary units. No single weighting is objectively correct. The frontier exposes how cost and carbon change when that preference changes. A future operator could instead impose a hard carbon budget.

**Is this algorithm new?** Mixed-integer optimization and receding-horizon control are established methods. We are not claiming to invent them. The project combines job deadlines, supply limits, battery physics, forecast-aware execution, oracle bounds, ablations, and reproducible stress tests in one accessible experiment.

**Why should we believe the result is near optimal?** The oracle has a HiGHS numerical lower bound and relative gap for this model. Every schedule also passes an independently implemented feasibility check, and a tiny case is checked by exhaustive enumeration. Rolling regret measures distance from the perfect-forecast oracle; there is no global rolling gap certificate.

**Can a battery make emissions worse?** Yes. Charging from a dirty grid and losing energy can outweigh later displacement. All charging imports are counted in carbon accounting, and the carbon value changes which arbitrage opportunities are worth taking. A reduction in operating cost is not automatically a carbon reduction.

**Why not postpone everything until solar noon?** Release/deadline windows, per-job GPU caps, total GPU capacity, power limits, and inference reservations prohibit that. Some workloads cannot move at all. Tight-deadline experiments explore this boundary.

**Why not run only on renewables?** Supply may be too low to serve fixed inference and deadlines. This model allows grid imports rather than silently dropping service. A genuinely infeasible instance is reported, and no successful schedule is fabricated.

**Why can forecasts cause failure?** A plan can rely on future power that does not arrive. This is particularly dangerous if a tight grid prevents recharging before the terminal boundary. The four-slot guard assumes zero future renewables near the end. It reduced the observed failure but is not a guarantee against arbitrary shocks.

**How realistic is fractional GPU allocation?** It is a planning abstraction for aggregate checkpointable work over an hour. It is not a live cluster allocation plan. Discrete placement, gang scheduling, topology and overhead could reduce the opportunity; these need a richer model and trace replay.

**Are the savings a business case for buying batteries?** No. They are operating results with synthetic tariffs and no capital expenditure. Battery, renewable, and server investment costs, cycle-life calibration, maintenance, and financing would be required for that conclusion.

**How is the baseline fair?** It receives identical jobs, inference reservations, renewable access, and physical capacity, and executes ready work immediately in earliest-deadline order. Storage stays idle. The battery-only ablation optimizes energy around that same compute schedule, revealing how much of the benefit comes from storage.

**What is not causal in the evaluation?** Realized future renewable supply is hidden from rolling subproblems, but all job reservations, inference demand, tariff, and grid intensity are known. Unknown future arrivals are not modeled. The oracle and two ablations intentionally use perfect foresight and are labeled accordingly.

## Demo recovery

If internet access is unavailable, an already installed environment can still run the dashboard. If the server is unavailable, use the committed `results/demo.json`, `results/RESULTS.md`, and dashboard screenshot. Restart with `python -m gridweave serve`; choose another port if needed. If a custom scenario is infeasible, show the reported constraints and explain the necessary admission or capacity decision instead of presenting savings.
