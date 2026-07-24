"""Run endpoints: launch (compute+persist), list, detail, events, report."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.db.models import Report, Run
from app.engine.config import RunConfig
from app.engine.environment import EnvironmentSpec
from app.services.runner import create_run

router = APIRouter(prefix="/api/runs", tags=["runs"])


class LaunchRequest(BaseModel):
    scenario_id: str
    environment_spec: EnvironmentSpec | None = None
    config: RunConfig | None = None
    operator: str | None = None


def _run_summary(run: Run) -> dict:
    return {
        "id": run.id, "scenario_id": run.scenario_id, "scenario_name": run.scenario_name,
        "operator": run.operator, "status": run.status, "duration_s": run.duration_s,
        "focus_role": run.focus_role, "scores": run.scores, "kpis": run.kpis,
        "summary": run.summary, "created_at": run.created_at.isoformat(),
    }


@router.post("", status_code=201)
def launch_run(req: LaunchRequest, db: Session = Depends(get_session)) -> dict:
    try:
        run = create_run(
            db, scenario_id=req.scenario_id,
            environment_spec=req.environment_spec.model_dump() if req.environment_spec else None,
            config=req.config.model_dump() if req.config else None,
            operator=req.operator,
        )
    except KeyError:
        raise HTTPException(404, "scenario not found")
    detail = _run_summary(run)
    detail["environment"] = run.environment
    detail["objectives"] = run.objectives
    detail["workflows"] = run.workflows
    detail["role_tasks"] = run.role_tasks
    return detail


@router.get("")
def list_runs(limit: int = 20, db: Session = Depends(get_session)) -> list[dict]:
    rows = db.scalars(select(Run).order_by(Run.created_at.desc()).limit(limit)).all()
    return [_run_summary(r) for r in rows]


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_session)) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    detail = _run_summary(run)
    detail["environment"] = run.environment
    detail["final_assets"] = run.final_assets
    detail["objectives"] = run.objectives
    detail["workflows"] = run.workflows
    detail["role_tasks"] = run.role_tasks
    detail["config"] = run.config
    return detail


@router.get("/{run_id}/events")
def get_run_events(run_id: str, db: Session = Depends(get_session)) -> list[dict]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run.events


@router.get("/{run_id}/report")
def get_run_report(run_id: str, db: Session = Depends(get_session)) -> dict:
    report = db.scalars(select(Report).where(Report.run_id == run_id)).first()
    if report is None:
        raise HTTPException(404, "report not found")
    return report.content


@router.post("/{run_id}/validate")
def validate_run_live_fire(run_id: str, db: Session = Depends(get_session)) -> dict:
    """Run live-fire validation on a completed simulation.

    Replays successful attacks on a real lab and compares model vs actual results.
    Requires the lab to be up (POST /api/lab/up first).
    """
    from app.lab.manager import get_lab
    from app.engine.live_fire_runner import run_live_fire_validation
    from app.engine.result import RunResult

    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")

    lab = get_lab()
    lab_status = lab.status()
    if not lab_status.up:
        raise HTTPException(400, "Lab is not running. Start it with POST /api/lab/up first.")

    # Reconstruct a minimal RunResult from the DB row
    run_result = RunResult(
        id=run.id, scenario_id=run.scenario_id, scenario_name=run.scenario_name,
        duration_s=run.duration_s, scores=run.scores, kpis=run.kpis,
        summary=run.summary, events=run.events, final_assets=run.final_assets or [],
        objectives={}, role_tasks={},
    )

    validation = run_live_fire_validation(run_result, lab)

    # Store validation in the report
    report = db.scalars(select(Report).where(Report.run_id == run_id)).first()
    if report and isinstance(report.content, dict):
        report.content["live_fire_validation"] = validation.summary()
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(report, "content")
        db.commit()

    return validation.summary()
