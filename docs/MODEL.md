# GridWeave model and decision rationale

## Scope

One data center, one day, 24 one-hour slots. The engine supports 1–48 slots and a configurable positive slot duration, although the dashboard uses the 24-hour generator. All job reservations are available at planning time; a release time is the earliest permissible execution, not a hidden future arrival. Online inference demand, tariffs, and carbon intensity are assumed known. Renewable availability is the uncertain signal in rolling evaluation.

The model targets checkpointable training and throughput-oriented batch inference. Each job has fluid, preemptible GPU equivalents, a maximum parallel allocation, required GPU-hours, a release slot, and an exclusive deadline boundary. Jobs have no dependencies. GPU equivalents are a capacity abstraction; allocating 37.4 GPU equivalents does not imply deploying a fractional physical GPU. A production scheduler would map this plan to discrete resources and account for lost work.

## Variables and units

For job `j` and slot `t`, let `x[j,t]` be allocated GPU equivalents. Let `g[t]`, `u[t]`, `c[t]`, and `d[t]` be grid import, renewable input, battery charge, and battery discharge in MW. `e[t]` is stored energy at a slot boundary in MWh, `z[t]` is a binary charging mode, and `p` is peak grid import in MW. `dt` is slot duration in hours.

The non-shiftable facility demand is

```text
base[t] = PUE × (idle_IT_MW + MW_per_GPU × inference_GPUs[t])
load[t] = base[t] + PUE × MW_per_GPU × sum_j x[j,t]
```

Idle IT power is charged in every slot, even at low utilization. PUE applies to IT load, including its modeled cooling overhead. Battery charging is on the AC facility bus and its conversion losses are modeled separately. No grid exports are allowed. Renewable curtailment is allowed; on-site renewable input has zero modeled marginal cost and zero operational emissions. No renewable certificates are purchased or claimed.

## Objective

Minimize

```text
sum_t dt × [price[t] × g[t] + wear × (c[t] + d[t])]
  + peak_fee × p
  + carbon_value × sum_t dt × carbon_intensity[t] × g[t] / 1000
```

`price` and `wear` are USD/MWh; `carbon_intensity` is kg CO2/MWh; `carbon_value` is USD/tonne CO2; `peak_fee` is an illustrative USD/MW fee for the simulated billing horizon. The default value of carbon is $80/tonne, an explicit preference rather than an assertion about a jurisdiction's carbon price. The dashboard exposes it because cost and carbon can conflict.

**Operating cost** excludes the carbon term and includes energy, wear, and peak fees. **Objective** includes all four terms. Every policy is evaluated at the same carbon value. Grid emissions count electricity used to charge the battery when that electricity is imported, preventing the battery from erasing charging emissions.

## Hard constraints

```text
1. Work completed:          sum_t dt × x[j,t] = work[j]
2. Job window/parallelism:  0 <= x[j,t] <= max_GPUs[j] inside [release, deadline)
                           x[j,t] = 0 outside that window
3. GPU capacity:            inference[t] + sum_j x[j,t] <= total_GPUs
4. Supply:                  0 <= g[t] <= grid_limit
                           0 <= u[t] <= renewable_available[t]
5. Power balance:           g[t] + u[t] + d[t] = load[t] + c[t]
6. Battery dynamics:        e[t+1] = e[t] + dt × (eta_charge × c[t] - d[t]/eta_discharge)
7. Battery bounds:          reserve × capacity <= e[t] <= capacity
                           0 <= c[t] <= battery_power × z[t]
                           0 <= d[t] <= battery_power × (1 - z[t])
8. Boundary conditions:     e[0] = e[T] = initial_fraction × capacity
9. Peak:                    p >= g[t] for every slot
```

There are no missed-deadline penalty variables. Money cannot buy a service violation. If the constraints cannot be satisfied, the run reports infeasibility. In a live system, such a result would require admission control, external power, capacity expansion, or renegotiated deadlines; none is silently assumed here.

Equal terminal energy prevents borrowing free energy from the initial battery. Battery reserve is 10% and starting energy is 50% by default. Charge/discharge efficiencies of 0.922 each imply approximately 85% round-trip efficiency. Wear is charged on AC throughput in both directions; it is an illustrative sensitivity parameter, not a measured degradation model.

## Forecast-aware control

At the beginning of each slot:

1. Observe the current renewable supply, battery state, completed work, and peak already incurred.
2. Take the day-ahead forecast for future renewable supply. In the final four future slots, replace that forecast with zero as a conservative closing-hours guard. Current actual supply is still used.
3. Solve the remaining-horizon MILP with remaining job work, original deadlines, original terminal energy target, and a peak lower bound equal to the peak already incurred.
4. Execute the first slot only. Replan at the next boundary.

No future realized renewable value is passed to the subproblem. A regression test changes future actuals while retaining forecasts and verifies identical first actions. This is causal with respect to renewable uncertainty, not with respect to unknown future jobs: the reservation queue and inference profile are explicitly known.

The guard addresses the observed inability to restore battery energy in a final slot under tight grid limits. `rolling(..., terminal_guard_slots=0)` disables it for a failure study. It is a heuristic with additional conservatism near the boundary, not a theorem of recursive feasibility. Unexpected workload arrivals, failures earlier in the day, or a grid too small to support inference can defeat it.

## Why believe the optimizer?

SciPy's `milp` calls HiGHS branch-and-bound. Each solved oracle includes the feasible incumbent objective, dual lower bound, relative gap, solver status, elapsed solve time, and a numerical constraint residual. The relative tolerance target is `1e-6` with a 15-second per-solve limit. A time-limited feasible incumbent is explicitly labeled and retains its reported gap; failure to find an incumbent raises an error. Incumbents are checked against the assembled constraints and integrality before publication.

A second validator, implemented without importing the optimizer, reconstructs workload completion, job windows, GPU limits, supply bounds, battery modes, energy dynamics, terminal energy, and power balance. Default absolute tolerance is `1e-4` in each constraint's native units. Its largest residual mixes native units and is a numerical check, not a dimensionless engineering margin.

Tests also check a known analytic optimum and compare a tiny example against exhaustive enumeration. These checks catch formulation and unit errors that a solver gap alone cannot detect. A zero numerical MILP gap certifies the finite mathematical model within solver tolerances; it says nothing about the adequacy of real-world assumptions.

## Metrics and comparisons

- Cost savings: `100 × (baseline_cost - rolling_cost) / baseline_cost`.
- Carbon savings: the same paired calculation for grid kg CO2.
- Renewable input share: `renewable_input / (grid_input + renewable_input)`. This includes storage charging/losses; it is not a claim that this fraction of useful computing energy is renewable.
- Renewable utilization: used divided by available on-site renewable input.
- Deadline success: jobs that finish the required work entirely within their windows; physical feasibility is reported separately.
- Oracle regret: `100 × (rolling_objective / realized_oracle_objective - 1)`.
- Equivalent AC cycles: `(charge_energy + discharge_energy) / (2 × capacity)`, an illustrative throughput indicator.

Immediate EDF uses available compute and power immediately, honoring grid capacity, and takes renewable supply first. It has identical jobs and inference reservations, with its battery idle. Compute-only removes storage; battery-only fixes job allocations to the feasible immediate schedule. These two ablations and the joint oracle have perfect forecasts. They measure the separate levers under an oracle information regime, not causal deployment competitors.

Every comparison requires a feasible baseline and a feasible rolling schedule. Failed runs remain in the report with their seed and reason, and no savings are fabricated. Confidence intervals use paired per-seed percentage improvements and a Student-t 95% interval within each scenario. The 20 seeds are varied synthetic inputs, not 20 independent real data centers. There is no significance or field-performance claim.

Seeds 0–19 were used to inspect behavior and choose the four-slot closing guard. Seeds 100–119 form a separate 140-run holdout evaluated after that choice, with no further tuning. The holdout tests generalization within this synthetic generator only; it is not an independently designed data distribution.

## Sensitivity and failure boundaries

The seven scenario families retain the same jobs for the same seed, except that `tight` changes only deadline slack. Cloudiness changes actual and forecast renewable input. The shock changes actual afternoon renewable supply while keeping the original forecast. Price spikes change only tariffs; lower efficiency changes only battery efficiencies. Grid stress changes grid capacity and inference reservations.

Cost and carbon need not both improve, especially when cheap electricity is carbon intensive. Storage can increase grid energy because it loses energy. Tight deadlines limit temporal flexibility; low efficiency reduces storage value. Grid constraints and forecast error can make future schedules infeasible. Capital costs can eliminate apparent operating savings. Non-preemptible distributed training would require a different placement/start-time model. Real deployment needs measured workload traces, calibrated power curves, forecast backtests, and admission control.
