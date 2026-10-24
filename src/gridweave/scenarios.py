"""Seeded scenarios with separate forecast and realized renewable supply."""

from dataclasses import replace
from math import ceil

import numpy as np

from .models import Facility, Job, Scenario

SCENARIOS = {
    "balanced": "A clear day with midday solar, evening tariffs, and flexible training.",
    "cloudy": "Only 30% of normal renewable supply; storage must earn its losses.",
    "price_spike": "A fivefold evening tariff tests peak avoidance and deadline protection.",
    "tight": "Less deadline slack limits the value of moving compute.",
    "forecast_shock": "Afternoon clouds deliver 70% less solar than the day-ahead forecast.",
    "grid_stress": "A 0.85 MW grid connection and extra inference reduce operating headroom.",
    "low_efficiency": "Battery round-trip efficiency falls to 72.25%, increasing the cost of cycling.",
}


def generate_scenario(kind: str = "balanced", seed: int = 42,
                      battery_mwh: float = 2.4) -> Scenario:
    if kind not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {kind}")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an integer from 0 to 2^32-1")
    rng = np.random.default_rng(seed)
    h = np.arange(24)
    solar = 1.18 * np.maximum(0, np.sin(np.pi * (h - 6) / 12))
    wind = 0.13 + 0.04 * np.cos((h + 2) * np.pi / 12)
    forecast = solar + wind
    actual = np.maximum(0, solar * rng.uniform(0.83, 1.10, 24)
                        + wind * rng.uniform(0.7, 1.3, 24))
    prices = np.full(24, 85.0)
    prices[:7] = 48
    prices[10:16] = 62
    prices[17:22] = 190
    prices += rng.uniform(-5, 5, 24)
    carbon = 490 - 180 * np.maximum(0, np.sin(np.pi * (h - 6) / 12))
    carbon += 100 * ((h >= 17) & (h < 22)) + rng.uniform(-25, 25, 24)
    inference = 250 + 90 * np.maximum(0, np.sin(np.pi * (h - 7) / 16))
    inference += rng.uniform(-18, 18, 24)
    facility = Facility(battery_mwh=battery_mwh, battery_mw=min(0.65, battery_mwh / 2))
    jobs = []
    names = ["Atlas pretrain", "Search embeddings", "Vision fine-tune", "Ranking refresh",
             "Speech adaptation", "Safety evaluation", "Code fine-tune", "Vector rebuild",
             "Multimodal eval", "Recommendation train", "Distillation", "Document indexing",
             "Language adaptation", "Retrieval refresh", "Image embeddings", "Checkpoint eval"]
    for j, name in enumerate(names):
        release = max(0, j - 2)
        window = int(rng.integers(6, 11))
        max_gpus = float(rng.choice([128, 160, 192]))
        work = float(rng.integers(380, 650))
        if kind == "tight":
            window = ceil(work / max_gpus) + 1
        deadline = min(24, release + window)
        jobs.append(Job(f"job-{j + 1:02}", name, release, deadline,
                        work, max_gpus,
                        "batch inference" if j % 3 == 1 else "training"))
    if kind == "cloudy":
        forecast *= 0.3
        actual *= 0.3
    elif kind == "price_spike":
        prices[18:21] *= 5
    elif kind == "forecast_shock":
        actual[11:17] *= 0.3
    elif kind == "grid_stress":
        inference += 90
        facility = replace(facility, grid_limit_mw=0.85)
    elif kind == "low_efficiency":
        facility = replace(facility, charge_efficiency=0.85, discharge_efficiency=0.85)
    s = Scenario(kind, seed, prices.tolist(), carbon.tolist(), actual.tolist(),
                 forecast.tolist(), inference.tolist(), jobs, facility,
                 description=SCENARIOS[kind])
    s.validate()
    return s
