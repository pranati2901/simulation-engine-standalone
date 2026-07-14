"""Deterministic KPI computation from run records.

Domain-agnostic core metrics (detection speed, response speed, rates). Domain plugins
may layer additional KPIs on top (e.g. aerospace: dispatch-reliability impact; hospital:
patient-throughput impact) by extending `compute_kpis`'s result dict — see
plugins/base.py `DomainPlugin.extra_kpis()`.
"""
from __future__ import annotations


def _mean(xs: list[int]) -> float:
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def compute_kpis(
    *,
    attempts: int,
    successes: int,
    detected: int,
    contained: int,
    prevented: int,
    dwells: list[int],
    resolution_times: list[int],
    first_detection_t: int | None,
) -> dict[str, float]:
    return {
        "mean_time_to_detect_s": _mean(dwells),
        "mean_time_to_resolve_s": _mean(resolution_times),
        "detection_rate": round(detected / successes, 3) if successes else 0.0,
        "containment_rate": round(contained / detected, 3) if detected else 0.0,
        "prevention_rate": round(prevented / attempts, 3) if attempts else 0.0,
        "time_to_first_detection_s": float(first_detection_t) if first_detection_t is not None else 0.0,
        "false_positive_rate": 0.0,  # not modelled in the deterministic core yet
    }
