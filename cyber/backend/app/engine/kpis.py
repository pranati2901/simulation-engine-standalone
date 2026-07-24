"""Deterministic KPI computation from run records (MTTD, MTTR, rates)."""
from __future__ import annotations


def _mean(xs: list[int]) -> float:
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def compute_kpis(
    *,
    attempts: int,
    successes: int,
    detected: int,
    contained: int,
    blocked: int,
    dwells: list[int],
    mttrs: list[int],
    first_detection_t: int | None,
) -> dict[str, float]:
    return {
        "mttd_s": _mean(dwells),
        "mttr_s": _mean(mttrs),
        "detection_rate": round(detected / successes, 3) if successes else 0.0,
        "containment_rate": round(contained / detected, 3) if detected else 0.0,
        "prevention_rate": round(blocked / attempts, 3) if attempts else 0.0,
        "time_to_first_detection_s": float(first_detection_t) if first_detection_t is not None else 0.0,
        # No false positives are modelled in the deterministic core.
        "fp_rate": 0.0,
    }
