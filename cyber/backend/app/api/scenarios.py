"""Scenario endpoints: list, detail, recommended topology, and create-custom (builder)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.db.models import Scenario as ScenarioRow
from app.engine.scenario import Scenario

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _summary(row: ScenarioRow) -> dict:
    d = row.definition
    return {
        "id": row.id, "name": row.name, "type": row.type, "industry": row.industry,
        "badge": row.badge, "label": row.label, "description": row.description,
        "is_seed": row.is_seed,
        "phases": d.get("phases", []),
        "nominal_duration_min": d.get("nominal_duration_min"),
        "difficulties": d.get("difficulties", []),
        "objectives": d.get("objectives", {}),
        "step_count": len(d.get("playbook", [])),
        "mitre_tactics": d.get("mitre_tactics", []),
    }


@router.get("")
def list_scenarios(db: Session = Depends(get_session)) -> list[dict]:
    rows = db.scalars(select(ScenarioRow).order_by(ScenarioRow.created_at.desc())).all()
    return [_summary(r) for r in rows]


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str, db: Session = Depends(get_session)) -> dict:
    row = db.get(ScenarioRow, scenario_id)
    if row is None:
        raise HTTPException(404, "scenario not found")
    return row.definition


@router.get("/{scenario_id}/topology")
def get_topology(scenario_id: str, db: Session = Depends(get_session)) -> dict:
    row = db.get(ScenarioRow, scenario_id)
    if row is None:
        raise HTTPException(404, "scenario not found")
    return row.definition.get("recommended_topology", {"assets": [], "controls": []})


@router.delete("/{scenario_id}", status_code=200)
def delete_scenario(scenario_id: str, db: Session = Depends(get_session)) -> dict:
    """Delete a custom (non-seed) scenario from the library. Seed scenarios are protected."""
    row = db.get(ScenarioRow, scenario_id)
    if row is None:
        raise HTTPException(404, "scenario not found")
    if row.is_seed:
        raise HTTPException(403, "seed scenarios cannot be deleted")
    db.delete(row)
    db.commit()
    return {"id": scenario_id, "deleted": True}


@router.post("", status_code=201)
def create_scenario(scenario: Scenario, db: Session = Depends(get_session)) -> dict:
    """Builder endpoint — validate a custom scenario against the schema and store it."""
    if db.get(ScenarioRow, scenario.id) is not None:
        raise HTTPException(409, "scenario id already exists")
    row = ScenarioRow(
        id=scenario.id, name=scenario.name, type=scenario.type, industry=scenario.industry,
        badge=scenario.badge, label=scenario.label, description=scenario.description,
        schema_version=scenario.schema_version, is_seed=False,
        definition=scenario.model_dump(mode="json"),
    )
    db.add(row)
    db.commit()
    return {"id": scenario.id}
