"""Joint MILP solved by SciPy/HiGHS. No service violations are purchasable."""

from time import perf_counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .models import Scenario, Schedule


class SchedulingError(RuntimeError):
    """No certified usable schedule; callers must not present fabricated savings."""

    def __init__(self, message: str, status: int = 2):
        super().__init__(message)
        self.status = status


def optimize(s: Scenario, carbon_price: float = 80.0, *, start: int = 0,
             remaining: list[float] | None = None, initial_soc: float | None = None,
             renewable: list[float] | None = None, past_peak: float = 0.0,
             fixed_allocation: list[list[float]] | None = None,
             time_limit: float = 15.0, policy: str = "joint_oracle") -> Schedule:
    """Solve [start, horizon), retaining absolute job windows.

    A feasible incumbent may be returned after a time limit, with its actual gap.
    Battery charge/discharge are AC-side MW. All workload allocations are fluid,
    preemptible GPU equivalents. Final SOC equals the day's initial SOC.
    """
    s.validate()
    if not np.isfinite(carbon_price) or carbon_price < 0:
        raise ValueError("carbon_price must be finite and nonnegative")
    if type(start) is not int or not 0 <= start < s.horizon:
        raise ValueError("start must be an in-horizon integer")
    f, dt, n, h = s.facility, s.slot_hours, len(s.jobs), s.horizon - start
    work = np.array(remaining if remaining is not None else [j.work_gpu_h for j in s.jobs])
    if len(work) != n or not np.all(np.isfinite(work)) or np.any(work < -1e-6):
        raise ValueError("Invalid remaining job work")
    work = np.maximum(0, work)
    soc0 = f.initial_soc_mwh if initial_soc is None else initial_soc
    renew = np.asarray(s.renewable_mw if renewable is None else renewable, dtype=float)
    if len(renew) != s.horizon or np.any(renew < 0) or not np.all(np.isfinite(renew)):
        raise ValueError("Invalid renewable trace")
    # x[j,t], grid[t], renewable used[t], charge[t], discharge[t], soc[0..h], z[t], peak
    gx, ru, ch, dis, soc, mode, peak = [n * h + k * h for k in range(5)] + [n * h + 5 * h + 1, n * h + 6 * h + 1]
    size = peak + 1
    lower, upper = np.zeros(size), np.full(size, np.inf)
    objective, integer = np.zeros(size), np.zeros(size, dtype=np.uint8)
    upper[gx:gx + h] = f.grid_limit_mw
    upper[ru:ru + h] = renew[start:]
    upper[ch:ch + h] = f.battery_mw if f.battery_mwh else 0
    upper[dis:dis + h] = f.battery_mw if f.battery_mwh else 0
    lower[soc:soc + h + 1] = f.reserve_soc_fraction * f.battery_mwh
    upper[soc:soc + h + 1] = f.battery_mwh
    lower[soc] = upper[soc] = soc0
    lower[soc + h] = upper[soc + h] = f.initial_soc_mwh
    upper[mode:mode + h] = 1
    integer[mode:mode + h] = 1
    lower[peak] = past_peak
    objective[gx:gx + h] = dt * (np.array(s.price_usd_per_mwh[start:])
                                               + carbon_price * np.array(s.carbon_kg_per_mwh[start:]) / 1000)
    objective[ch:ch + h] = objective[dis:dis + h] = dt * f.degradation_usd_per_mwh
    objective[peak] = f.peak_usd_per_mw_day
    for j, job in enumerate(s.jobs):
        for t in range(h):
            idx, absolute = j * h + t, t + start
            upper[idx] = job.max_gpus if job.release <= absolute < job.deadline else 0
            if fixed_allocation is not None:
                lower[idx] = upper[idx] = fixed_allocation[j][absolute]
    rows, cols, values, lb, ub = [], [], [], [], []

    def constraint(terms, minimum, maximum):
        row = len(lb)
        for col, value in terms:
            rows.append(row)
            cols.append(col)
            values.append(value)
        lb.append(minimum)
        ub.append(maximum)

    for j in range(n):
        constraint([(j * h + t, dt) for t in range(h)], work[j], work[j])
    for t in range(h):
        a = start + t
        constraint([(j * h + t, 1) for j in range(n)], -np.inf,
                   f.total_gpus - s.inference_gpus[a])
        # grid + used renewable + discharge = IT/cooling load + battery charging
        base = f.pue * (f.idle_it_mw + f.mw_per_gpu * s.inference_gpus[a])
        constraint([(gx + t, 1), (ru + t, 1), (dis + t, 1), (ch + t, -1)]
                   + [(j * h + t, -f.pue * f.mw_per_gpu) for j in range(n)], base, base)
        constraint([(soc + t + 1, 1), (soc + t, -1),
                    (ch + t, -dt * f.charge_efficiency),
                    (dis + t, dt / f.discharge_efficiency)], 0, 0)
        constraint([(ch + t, 1), (mode + t, -f.battery_mw)], -np.inf, 0)
        constraint([(dis + t, 1), (mode + t, f.battery_mw)], -np.inf, f.battery_mw)
        constraint([(gx + t, 1), (peak, -1)], -np.inf, 0)
    matrix = coo_matrix((values, (rows, cols)), shape=(len(lb), size)).tocsc()
    began = perf_counter()
    result = milp(objective, integrality=integer, bounds=Bounds(lower, upper),
                  constraints=LinearConstraint(matrix, np.array(lb), np.array(ub)),
                  options={"time_limit": time_limit, "mip_rel_gap": 1e-6})
    elapsed = perf_counter() - began
    if result.x is None or result.status not in (0, 1):
        raise SchedulingError(f"No feasible schedule: {result.message}", int(result.status))
    v = result.x
    # Check solver incumbent before publishing, including time-limited solutions.
    av = matrix @ v
    residual = max(float(np.max(np.maximum(np.array(lb) - av, 0))),
                   float(np.max(np.maximum(av - np.array(ub), 0))),
                   float(np.max(np.maximum(lower - v, 0))),
                   float(np.max(np.maximum(v - upper, 0))))
    int_residual = float(np.max(np.abs(v[mode:mode + h] - np.round(v[mode:mode + h]))))
    if residual > 1e-4 or int_residual > 1e-5:
        raise SchedulingError(f"Solver incumbent failed feasibility check: {residual}", 4)

    def clean(a):
        return np.where(np.abs(a) < 1e-8, 0.0, a).tolist()

    return Schedule(policy, [clean(v[j * h:(j + 1) * h]) for j in range(n)],
                    clean(v[gx:gx + h]), clean(v[ru:ru + h]), clean(v[ch:ch + h]),
                    clean(v[dis:dis + h]), clean(v[soc:soc + h + 1]), {
                        "status": "optimal" if result.status == 0 else "time_limit_feasible",
                        "message": result.message,
                        "objective_usd": float(result.fun),
                        "dual_bound_usd": float(result.mip_dual_bound),
                        "relative_gap": float(result.mip_gap),
                        "solve_seconds": elapsed,
                        "max_constraint_residual": residual,
                        "scope": "Perfect-forecast model" if renewable is None else "Forecast subproblem",
                    })
