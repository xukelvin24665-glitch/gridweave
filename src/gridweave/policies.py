"""Immediate EDF baseline and causal receding-horizon control."""

from time import perf_counter

from .models import Scenario, Schedule
from .optimizer import SchedulingError, optimize


def immediate(s: Scenario) -> Schedule:
    """Use available GPUs/supply immediately, earliest deadline first, no battery.

    Fair baseline: identical inference reservation, renewable access, job windows,
    power limits, and workload. No price/carbon lookahead. EDF may fail on an
    overloaded instance; the independent validator exposes that failure.
    """
    s.validate()
    f, h, dt = s.facility, s.horizon, s.slot_hours
    left = [job.work_gpu_h for job in s.jobs]
    x = [[0.0] * h for _ in s.jobs]
    grid, used = [], []
    for t in range(h):
        base = f.pue * (f.idle_it_mw + s.inference_gpus[t] * f.mw_per_gpu)
        if base > f.grid_limit_mw + s.renewable_mw[t] + 1e-7:
            raise SchedulingError(f"Immediate baseline cannot power inference in slot {t}")
        available = min(f.total_gpus - s.inference_gpus[t],
                        max(0, (f.grid_limit_mw + s.renewable_mw[t] - base)
                            / (f.pue * f.mw_per_gpu)))
        ready = sorted((j for j, job in enumerate(s.jobs) if job.release <= t < job.deadline),
                       key=lambda j: (s.jobs[j].deadline, s.jobs[j].release, j))
        for j in ready:
            amount = min(available, s.jobs[j].max_gpus, left[j] / dt)
            x[j][t] = max(0, amount)
            left[j] = max(0, left[j] - amount * dt)
            available -= amount
        load = base + f.pue * f.mw_per_gpu * sum(row[t] for row in x)
        used.append(min(load, s.renewable_mw[t]))
        grid.append(max(0, load - used[-1]))
    return Schedule("immediate_edf", x, grid, used, [0.0] * h, [0.0] * h,
                    [f.initial_soc_mwh] * (h + 1),
                    {"status": "heuristic", "scope": "Causal immediate execution; storage idle"})


def rolling(s: Scenario, carbon_price: float = 80.0, *, terminal_guard_slots: int = 4) -> Schedule:
    """Replan each slot, observe current supply, use day-ahead future forecasts.

    The reserved job queue, price, carbon and inference profile are known. Only
    renewable supply is uncertain. The actual future trace is never read by the
    subproblem. In the closing slots, assume zero future renewable supply to
    protect the terminal SOC target from optimistic forecasts. This guard is a
    conservative heuristic, not a robust feasibility proof for the whole day.
    """
    h, n, dt = s.horizon, len(s.jobs), s.slot_hours
    if type(terminal_guard_slots) is not int or not 0 <= terminal_guard_slots <= 48:
        raise ValueError("terminal_guard_slots must be an integer from 0 to 48")
    left = [job.work_gpu_h for job in s.jobs]
    x = [[0.0] * h for _ in s.jobs]
    grid, used, charge, discharge = [], [], [], []
    soc = [s.facility.initial_soc_mwh]
    certificates = []
    began = perf_counter()
    for t in range(h):
        forecast = list(s.renewable_forecast_mw)
        for future in range(max(t + 1, h - terminal_guard_slots), h):
            forecast[future] = 0.0
        forecast[t] = s.renewable_mw[t]
        try:
            plan = optimize(s, carbon_price, start=t, remaining=left,
                            initial_soc=soc[-1], renewable=forecast,
                            past_peak=max(grid, default=0.0), policy="rolling_mpc")
        except SchedulingError as exc:
            raise SchedulingError(f"Rolling controller infeasible at slot {t}: {exc}", exc.status) from exc
        for j in range(n):
            x[j][t] = plan.allocation_gpus[j][0]
            left[j] = max(0, left[j] - x[j][t] * dt)
        grid.append(plan.grid_mw[0])
        used.append(plan.renewable_used_mw[0])
        charge.append(plan.charge_mw[0])
        discharge.append(plan.discharge_mw[0])
        soc.append(plan.soc_mwh[1])
        certificates.append({"slot": t, **plan.solver})
    return Schedule("rolling_mpc", x, grid, used, charge, discharge, soc, {
        "status": "completed",
        "scope": "Causal renewable forecasts; no global optimality claim",
        "relative_gap": None,
        "max_subproblem_gap": max(c["relative_gap"] for c in certificates),
        "terminal_guard_slots": terminal_guard_slots,
        "forecast_policy": "Day-ahead forecasts; zero future renewables in closing guard slots; current actual observed",
        "solve_seconds": perf_counter() - began,
        "subproblems": certificates,
    })
