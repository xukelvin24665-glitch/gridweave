from .models import Scenario, Schedule
from .validation import validate_schedule


def measure(s: Scenario, plan: Schedule, carbon_price: float = 80.0) -> dict:
    validation = validate_schedule(s, plan)
    f, dt = s.facility, s.slot_hours
    grid = sum(plan.grid_mw) * dt
    renew = sum(plan.renewable_used_mw) * dt
    available = sum(s.renewable_mw) * dt
    energy_cost = sum(g * p for g, p in zip(plan.grid_mw, s.price_usd_per_mwh)) * dt
    emissions = sum(g * c for g, c in zip(plan.grid_mw, s.carbon_kg_per_mwh)) * dt
    throughput = sum(plan.charge_mw + plan.discharge_mw) * dt
    wear = throughput * f.degradation_usd_per_mwh
    peak = max(plan.grid_mw)
    demand = peak * f.peak_usd_per_mw_day
    cost = energy_cost + wear + demand
    return {
        "operating_cost_usd": cost,
        "energy_cost_usd": energy_cost,
        "battery_wear_usd": wear,
        "peak_cost_usd": demand,
        "carbon_kg": emissions,
        "objective_usd": cost + carbon_price * emissions / 1000,
        "grid_mwh": grid,
        "peak_grid_mw": peak,
        "renewable_used_mwh": renew,
        "renewable_curtailed_mwh": max(0, available - renew),
        "renewable_input_pct": 100 * renew / (grid + renew) if grid + renew > 0 else 0,
        "renewable_utilization_pct": 100 * renew / available if available > 0 else 0,
        "battery_throughput_mwh": throughput,
        "equivalent_ac_cycles": throughput / (2 * f.battery_mwh) if f.battery_mwh else 0,
        "work_gpu_h": sum(sum(row) for row in plan.allocation_gpus) * dt,
        "jobs_on_time": validation["jobs_on_time"],
        "jobs_total": len(s.jobs),
        "deadline_success_pct": 100 * validation["jobs_on_time"] / len(s.jobs) if s.jobs else 100,
        "validation": validation,
    }
