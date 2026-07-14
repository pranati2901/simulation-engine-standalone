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
    runs = run_manager.list_runs()
    return {
        "total_runs": len(runs),
        "by_status": {
            status: len([r for r in runs if r.status == status])
            for status in {"pending", "running", "complete", "failed"}
        },
    }
