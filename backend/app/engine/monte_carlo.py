"""Monte Carlo sweep — runs a scenario N times with a varied readiness value to
produce probability/range outputs (Prem's brief "Mode 1 — Operational Intelligence":
"73% chance of $2.5M-$4.2M loss" style output).

Stays deterministic like the rest of the engine (see engine/graph.py's
_seeded_fraction pattern): readiness for iteration i is derived from a seeded hash
of (config.seed, scenario.id, i), not real randomness — identical inputs always
produce an identical distribution, same replay guarantee as everything else here.
"""
from __future__ import annotations

import hashlib
import statistics
from typing import Callable

from pydantic import BaseModel

from .config import RunConfig
from .environment import EnvironmentSpec
from .result import RunResult
from .scenario import Scenario


def _seeded_fraction(*parts: object) -> float:
    """Same pattern as engine/graph.py::_seeded_fraction — deterministic [0,1)."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


class RangeStats(BaseModel):
    mean: float
    min: float
    max: float
    p05: float   # 5th percentile — "pessimistic" bound
    p95: float   # 95th percentile — "optimistic" bound


class MonteCarloResult(BaseModel):
    scenario_id: str
    iterations: int
    readiness_range: tuple[int, int]
    certified_rate: float                       # fraction of runs that were certified
    score_stats: dict[str, RangeStats] = {}      # per role
    kpi_stats: dict[str, RangeStats] = {}        # per kpi


def _percentile(values: list[float], pct: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    idx = min(len(values) - 1, max(0, round(pct * (len(values) - 1))))
    return values[idx]


def _stats(values: list[float]) -> RangeStats:
    return RangeStats(
        mean=round(statistics.fmean(values), 3) if values else 0.0,
        min=round(min(values), 3) if values else 0.0,
        max=round(max(values), 3) if values else 0.0,
        p05=round(_percentile(values, 0.05), 3),
        p95=round(_percentile(values, 0.95), 3),
    )


def run_monte_carlo(
    scenario: Scenario,
    environment: EnvironmentSpec,
    base_config: RunConfig,
    execute: Callable[[Scenario, EnvironmentSpec, RunConfig], RunResult],
    iterations: int = 100,
    readiness_range: tuple[int, int] = (30, 90),
) -> MonteCarloResult:
    lo, hi = readiness_range
    certified_count = 0
    score_samples: dict[str, list[float]] = {}
    kpi_samples: dict[str, list[float]] = {}

    for i in range(iterations):
        frac = _seeded_fraction(base_config.seed, scenario.id, i)
        readiness_i = round(lo + frac * (hi - lo))
        variant_config = base_config.model_copy(update={"readiness": readiness_i})

        result = execute(scenario, environment, variant_config)

        clearance = result.summary.get("clearance", {})
        if clearance.get("certified"):
            certified_count += 1

        for role, score in result.scores.items():
            score_samples.setdefault(role, []).append(float(score))
        for kpi, value in result.kpis.items():
            kpi_samples.setdefault(kpi, []).append(float(value))

    return MonteCarloResult(
        scenario_id=scenario.id,
        iterations=iterations,
        readiness_range=readiness_range,
        certified_rate=round(certified_count / iterations, 4) if iterations else 0.0,
        score_stats={role: _stats(vals) for role, vals in score_samples.items()},
        kpi_stats={kpi: _stats(vals) for kpi, vals in kpi_samples.items()},
    )
