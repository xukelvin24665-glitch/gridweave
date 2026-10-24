"""Independent physical and service checks; deliberately no optimizer imports."""

from math import isfinite

from .models import Scenario, Schedule


def validate_schedule(s: Scenario, plan: Schedule, tolerance: float = 1e-4) -> dict:
    f, h, dt = s.facility, s.horizon, s.slot_hours
    errors = []
    expected = {"grid_mw": h, "renewable_used_mw": h, "charge_mw": h,
                "discharge_mw": h, "soc_mwh": h + 1}
    for key, length in expected.items():
        values = getattr(plan, key)
        if len(values) != length or not all(isfinite(v) for v in values):
            errors.append(f"Invalid {key} shape or nonfinite value")
    if len(plan.allocation_gpus) != len(s.jobs) or any(
            len(row) != h or not all(isfinite(v) for v in row) for row in plan.allocation_gpus):
        errors.append("Invalid workload allocation shape or nonfinite value")
    if errors:
        return {"valid": False, "errors": errors, "max_residual": None, "jobs_on_time": 0}
    max_residual = 0.0

    def check(residual: float, label: str):
        nonlocal max_residual
        max_residual = max(max_residual, residual)
        if residual > tolerance:
            errors.append(label)

    on_time = 0
    for j, job in enumerate(s.jobs):
        row = plan.allocation_gpus[j]
        work_error = abs(sum(row) * dt - job.work_gpu_h)
        outside = max((abs(v) for t, v in enumerate(row)
                       if not job.release <= t < job.deadline), default=0)
        check(work_error, f"{job.id}: unfinished/excess work")
        check(outside, f"{job.id}: executed outside release/deadline")
        check(max(-min(row), max(row) - job.max_gpus, 0), f"{job.id}: allocation limit")
        if work_error <= tolerance and outside <= tolerance:
            on_time += 1
    check(abs(plan.soc_mwh[0] - f.initial_soc_mwh), "Initial SOC mismatch")
    check(abs(plan.soc_mwh[-1] - f.initial_soc_mwh), "Terminal SOC mismatch")
    check(max(0, f.reserve_soc_fraction * f.battery_mwh - min(plan.soc_mwh),
              max(plan.soc_mwh) - f.battery_mwh), "Battery energy/reserve limit")
    for t in range(h):
        g, r, c, d = (getattr(plan, key)[t] for key in
                       ("grid_mw", "renewable_used_mw", "charge_mw", "discharge_mw"))
        flex = sum(row[t] for row in plan.allocation_gpus)
        load = f.pue * (f.idle_it_mw + f.mw_per_gpu * (s.inference_gpus[t] + flex))
        check(max(0, flex + s.inference_gpus[t] - f.total_gpus), f"Slot {t}: GPU capacity")
        check(max(0, -g, g - f.grid_limit_mw, -r, r - s.renewable_mw[t]),
              f"Slot {t}: supply bounds")
        battery_power = f.battery_mw if f.battery_mwh else 0
        check(max(0, -c, -d, c - battery_power, d - battery_power), f"Slot {t}: battery power")
        check(min(c, d), f"Slot {t}: simultaneous charging/discharging")
        check(abs(g + r + d - load - c), f"Slot {t}: power balance")
        predicted_soc = plan.soc_mwh[t] + dt * (f.charge_efficiency * c - d / f.discharge_efficiency)
        check(abs(plan.soc_mwh[t + 1] - predicted_soc), f"Slot {t}: battery energy balance")
    return {"valid": not errors, "errors": errors, "max_residual": max_residual,
            "jobs_on_time": on_time}
