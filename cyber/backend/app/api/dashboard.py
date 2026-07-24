"""Dashboard & leaderboard aggregates."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.db.models import Run, Scenario as ScenarioRow

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_session)) -> dict:
    total_runs = db.scalar(select(func.count(Run.id))) or 0
    total_scenarios = db.scalar(select(func.count(ScenarioRow.id))) or 0
    recent = db.scalars(select(Run).order_by(Run.created_at.desc()).limit(6)).all()

    blue_scores = [r.scores.get("blue", 0) for r in recent]
    avg_blue = round(sum(blue_scores) / len(blue_scores)) if blue_scores else 0
    critical = sum(1 for r in recent if r.summary.get("ransomware") or r.summary.get("ot_impact"))

    recent_list = [{
        "id": r.id, "name": r.scenario_name,
        "type": _scenario_type(db, r.scenario_id),
        "created_at": r.created_at.isoformat(),
        "red": r.scores.get("red", 0), "blue": r.scores.get("blue", 0),
        "detection_rate": r.kpis.get("detection_rate", 0),
    } for r in recent]

    # threat coverage = which tactics our scenarios exercise (rough proxy)
    coverage = _threat_coverage(db)

    return {
        "total_runs": total_runs,
        "total_scenarios": total_scenarios,
        "avg_blue_score": avg_blue,
        "critical_findings": critical,
        "recent_runs": recent_list,
        "threat_coverage": coverage,
        # readiness radar derived from average KPIs across recent runs
        "readiness": _readiness(recent),
    }


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_session)) -> list[dict]:
    runs = db.scalars(select(Run).order_by(Run.created_at.desc()).limit(100)).all()
    ranked = sorted(runs, key=lambda r: r.scores.get("blue", 0), reverse=True)[:10]
    return [{
        "rank": i + 1,
        "operator": r.operator or "Operator",
        "scenario": r.scenario_name,
        "blue": r.scores.get("blue", 0),
        "red": r.scores.get("red", 0),
        "detection_rate": r.kpis.get("detection_rate", 0),
        "created_at": r.created_at.isoformat(),
    } for i, r in enumerate(ranked)]


def _scenario_type(db: Session, scenario_id: str) -> str:
    row = db.get(ScenarioRow, scenario_id)
    return row.type if row else "purple"


def _threat_coverage(db: Session) -> list[dict]:
    rows = db.scalars(select(ScenarioRow)).all()
    tactics: dict[str, int] = {}
    for r in rows:
        for t in r.definition.get("mitre_tactics", []):
            tactics[t] = tactics.get(t, 0) + 1
    total = max(1, len(rows))
    return [{"label": k, "pct": min(100, round(v / total * 100))}
            for k, v in sorted(tactics.items(), key=lambda kv: -kv[1])[:6]]


def _readiness(recent: list[Run]) -> dict:
    if not recent:
        return {"Detection": 0, "Response": 0, "Recovery": 0,
                "Prevention": 0, "Containment": 0, "Forensics": 0}

    def avg(fn) -> int:
        return round(sum(fn(r) for r in recent) / len(recent))

    return {
        "Detection": avg(lambda r: r.kpis.get("detection_rate", 0) * 100),
        "Response": avg(lambda r: 100 - min(100, r.kpis.get("mttr_s", 0) / 12)),
        "Recovery": avg(lambda r: 100 if r.summary.get("backups_enabled") else 40),
        "Prevention": avg(lambda r: r.kpis.get("prevention_rate", 0) * 100),
        "Containment": avg(lambda r: r.kpis.get("containment_rate", 0) * 100),
        "Forensics": avg(lambda r: r.kpis.get("detection_rate", 0) * 90),
    }
