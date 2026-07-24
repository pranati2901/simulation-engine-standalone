"""Scenario Studio orchestration — author, run (simulate + score), train, and persist.

A run is a saga: resolve/author a spec → simulate it in-context → score it against objective KPIs →
persist the timeline + result. Training turns a fault into a graded interactive procedure.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ai, catalog, scoring
from .db import StudioRun, StudioScenario
from .models import Procedure, RunResult, ScenarioSpec, TrainAction, TrainingGrade
from .settings_store import get_config


# ── Scenario library ──────────────────────────────────────────────────
def _seed_entry(s: dict) -> dict:
    return {"id": s["id"], "name": s["name"], "domain": s["domain"], "kind": s["kind"],
            "description": s["description"], "is_seed": True, "spec": s["spec"],
            "created_at": None}


def list_scenarios(db: Session, domain: str | None = None) -> list[dict]:
    seeds = [_seed_entry(s) for s in catalog.SEED_SCENARIOS
             if not domain or s["domain"] == domain]
    q = select(StudioScenario).order_by(StudioScenario.created_at.desc())
    if domain:
        q = q.where(StudioScenario.domain == domain)
    authored = [{"id": r.id, "name": r.name, "domain": r.domain, "kind": r.kind,
                 "description": r.description, "is_seed": False, "spec": r.spec,
                 "created_at": r.created_at.isoformat()} for r in db.scalars(q).all()]
    return authored + seeds


def get_spec(db: Session, scenario_id: str) -> ScenarioSpec | None:
    for s in catalog.SEED_SCENARIOS:
        if s["id"] == scenario_id:
            return ScenarioSpec.model_validate(s["spec"])
    row = db.get(StudioScenario, scenario_id)
    return ScenarioSpec.model_validate(row.spec) if row else None


def author_and_save(db: Session, description: str, domain: str, kind: str,
                    horizon_min: float = 60.0, save: bool = True) -> dict:
    cfg = get_config()
    spec = ai.author_scenario(cfg, description, domain, kind, horizon_min)
    entry = None
    if save:
        row = StudioScenario(name=spec.name, domain=domain, kind=kind,
                             description=description, is_seed=False, spec=spec.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        entry = {"id": row.id, "name": row.name, "domain": row.domain, "kind": row.kind,
                 "description": row.description, "is_seed": False, "spec": row.spec,
                 "created_at": row.created_at.isoformat()}
    return {"spec": spec.model_dump(), "scenario": entry, "ai_mode": ai.ai_mode(cfg)}


def delete_scenario(db: Session, scenario_id: str) -> bool:
    row = db.get(StudioScenario, scenario_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


# ── Run (simulate + score) ────────────────────────────────────────────
def run_scenario(db: Session, *, scenario_id: str | None = None,
                 spec: ScenarioSpec | None = None, analyze: bool = True) -> RunResult:
    cfg = get_config()
    if spec is None and scenario_id:
        spec = get_spec(db, scenario_id)
    if spec is None:
        raise KeyError("scenario not found")

    sim = ai.simulate(cfg, spec)
    kpis = scoring.compute_kpis(spec, sim)
    narrative = ai.analyze(cfg, spec, sim) if analyze else ""

    result = RunResult(
        scenario_id=scenario_id, name=spec.name, domain=spec.domain, system=spec.system,
        status="completed", duration_min=spec.horizon_min, spec=spec,
        outcome_band=sim.outcome_band, headline=sim.headline, events=sim.timeline,
        metrics=sim.metrics, detections=sim.detections, mitigations=sim.mitigations,
        risks=sim.risks, kpis=kpis, narrative=narrative, ai_mode=ai.ai_mode(cfg),
        created_at=datetime.utcnow().isoformat())

    row = StudioRun(scenario_id=scenario_id, name=spec.name, domain=spec.domain,
                    status="completed", spec=spec.model_dump(), result=result.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    result.id = row.id
    row.result = result.model_dump()
    db.commit()
    return result


def get_run(db: Session, run_id: str) -> RunResult | None:
    row = db.get(StudioRun, run_id)
    return RunResult.model_validate(row.result) if row else None


def list_runs(db: Session, limit: int = 25, domain: str | None = None) -> list[dict]:
    q = select(StudioRun).order_by(StudioRun.created_at.desc()).limit(limit)
    if domain:
        q = q.where(StudioRun.domain == domain)
    out = []
    for r in db.scalars(q).all():
        res = r.result or {}
        out.append({"id": r.id, "name": r.name, "domain": r.domain,
                    "outcome_band": res.get("outcome_band"),
                    "readiness_score": (res.get("kpis") or {}).get("readiness_score"),
                    "grade": (res.get("kpis") or {}).get("grade"),
                    "created_at": r.created_at.isoformat()})
    return out


# ── Training ───────────────────────────────────────────────────────────
def build_procedure(db: Session, domain: str, system: str, fault: str,
                    title: str = "", context: str = "") -> Procedure:
    return ai.build_procedure(get_config(), domain, system, fault, title, context)


def grade_training(procedure: Procedure, actions: list[TrainAction]) -> TrainingGrade:
    return scoring.grade_training(procedure, actions)


def coach(db: Session, messages: list[dict], context: dict) -> str:
    return ai.coach_reply(get_config(), messages, context)


def director(db: Session, procedure: Procedure) -> list[dict]:
    return ai.director_beats(get_config(), procedure)
