"""GET /dashboard/* — aggregate views across runs (KPI trends, domain coverage, etc).

Stub — flesh out once db persistence (db/models.py) is wired in and there's more than
one run's worth of data to aggregate.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..services import run_manager

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary():
    return _build_summary()


@router.get("")
def dashboard_root():
    """GET /dashboard — alias for /dashboard/summary, expected by the Hub."""
    return _build_summary()


def _build_summary() -> dict:
    runs = run_manager.list_runs()
    domains: dict[str, int] = {}
    scenarios_seen: set[str] = set()
    for r in runs:
        scenarios_seen.add(r.scenario_id)
        domain = r.config.domain if r.config else "generic"
        domains[domain] = domains.get(domain, 0) + 1
    return {
        "total_runs": len(runs),
        "unique_scenarios": len(scenarios_seen),
        "by_status": {
            status: len([r for r in runs if r.status == status])
            for status in {"pending", "running", "complete", "failed"}
        },
        "by_domain": domains,
    }
