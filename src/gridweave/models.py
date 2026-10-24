"""Serializable inputs. MW, MWh, USD, kg CO2, and GPU-hours throughout."""

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any


def _finite(value: float, name: str, minimum: float = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    if not isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")


@dataclass(frozen=True)
class Job:
    id: str
    name: str
    release: int
    deadline: int
    work_gpu_h: float
    max_gpus: float
    kind: str = "training"


@dataclass(frozen=True)
class Facility:
    total_gpus: float = 1024
    idle_it_mw: float = 0.18
    mw_per_gpu: float = 0.0007
    pue: float = 1.18
    grid_limit_mw: float = 2.0
    battery_mwh: float = 2.4
    battery_mw: float = 0.65
    charge_efficiency: float = 0.922
    discharge_efficiency: float = 0.922
    initial_soc_fraction: float = 0.5
    reserve_soc_fraction: float = 0.1
    degradation_usd_per_mwh: float = 8.0
    peak_usd_per_mw_day: float = 25.0

    @property
    def initial_soc_mwh(self) -> float:
        return self.battery_mwh * self.initial_soc_fraction

    def validate(self) -> None:
        for name, value in asdict(self).items():
            _finite(value, name)
        if self.total_gpus <= 0 or self.mw_per_gpu <= 0 or self.pue < 1:
            raise ValueError("GPU count/power must be positive and PUE must be >= 1")
        for name in ("charge_efficiency", "discharge_efficiency"):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if not 0 <= self.reserve_soc_fraction <= self.initial_soc_fraction <= 1:
            raise ValueError("SOC fractions must satisfy 0 <= reserve <= initial <= 1")


@dataclass(frozen=True)
class Scenario:
    name: str
    seed: int
    price_usd_per_mwh: list[float]
    carbon_kg_per_mwh: list[float]
    renewable_mw: list[float]
    renewable_forecast_mw: list[float]
    inference_gpus: list[float]
    jobs: list[Job]
    facility: Facility = field(default_factory=Facility)
    slot_hours: float = 1.0
    description: str = ""
    provenance: str = "Synthetic data; illustrative assumptions, not a measured facility."

    @property
    def horizon(self) -> int:
        return len(self.price_usd_per_mwh)

    def validate(self) -> None:
        self.facility.validate()
        if not isinstance(self.name, str) or not self.name or len(self.name) > 160:
            raise ValueError("Scenario name must contain 1-160 characters")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be an integer from 0 to 2^32-1")
        if not 1 <= self.horizon <= 48:
            raise ValueError("Use 1-48 time slots")
        _finite(self.slot_hours, "slot_hours", 0.05)
        if self.slot_hours > 24:
            raise ValueError("slot_hours must be <= 24")
        for name in ("price_usd_per_mwh", "carbon_kg_per_mwh", "renewable_mw",
                     "renewable_forecast_mw", "inference_gpus"):
            values = getattr(self, name)
            if len(values) != self.horizon:
                raise ValueError(f"{name} must have {self.horizon} entries")
            for value in values:
                _finite(value, name)
        if max(self.inference_gpus) > self.facility.total_gpus:
            raise ValueError("Inference reservation exceeds GPU capacity")
        if len(self.jobs) > 80:
            raise ValueError("Use at most 80 jobs")
        ids = set()
        for job in self.jobs:
            if not isinstance(job.id, str) or not job.id or job.id in ids:
                raise ValueError("Job IDs must be nonempty unique strings")
            ids.add(job.id)
            if type(job.release) is not int or type(job.deadline) is not int:
                raise ValueError("Job release/deadline must be integer slot boundaries")
            if not 0 <= job.release < job.deadline <= self.horizon:
                raise ValueError(f"Invalid availability window for {job.id}")
            _finite(job.work_gpu_h, "work_gpu_h", 0.001)
            _finite(job.max_gpus, "max_gpus", 0.001)
            if job.work_gpu_h > (job.deadline - job.release) * self.slot_hours * job.max_gpus + 1e-7:
                raise ValueError(f"{job.id} cannot finish even with its full allocation")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        if not isinstance(data, dict):
            raise ValueError("Scenario must be a JSON object")
        try:
            result = cls(**{**data, "facility": Facility(**data.get("facility", {})),
                            "jobs": [Job(**job) for job in data["jobs"]]})
            result.validate()
        except (TypeError, KeyError, AttributeError) as exc:
            raise ValueError(f"Invalid scenario structure: {exc}") from exc
        return result


@dataclass
class Schedule:
    policy: str
    allocation_gpus: list[list[float]]
    grid_mw: list[float]
    renewable_used_mw: list[float]
    charge_mw: list[float]
    discharge_mw: list[float]
    soc_mwh: list[float]
    solver: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
