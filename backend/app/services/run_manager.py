"""Run lifecycle orchestration.

A scenario run is a saga across (up to) three services, per the integration contract:
  1. The Scenario Engine (this repo) owns the scenario spec, run lifecycle and scoring.
  2. For physics what-ifs, it calls the Digital Twin (services/twin_client.py).
  3. For NL authoring / narration / coaching, it calls Agentic AI (services/agent_client.py).

run_manager persists runs to Postgres (db/models.py::RunORM) and exposes lifecycle
operations to the API layer; runner.py (below) does the actual execution step.

NOTE — run graphs are still in-memory (_GRAPHS below), on purpose, not by oversight:
a RunGraph is a DAG of RunResults (root + every cascaded child run), not a single
RunRecord, so it doesn't fit RunORM's id/data shape without its own schema decision
(e.g. a graph table + a run-in-graph join table, or a single JSON blob per graph).
Flagging this rather than picking a shape and guessing — do this as its own pass.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from ..db.base import SessionLocal
from ..db.models import RunORM
from ..engine import graph as graph_engine
from ..engine.config import RunConfig
from ..engine.environment import EnvironmentSpec
from ..engine.graph import RunGraph
from ..engine.result import RunResult
from ..scenarios.loader import get_scenario
from . import runner

_GRAPHS: dict[str, RunGraph] = {}  # see module docstring — intentionally not persisted yet


class RunRecord(BaseModel):
    id: str
    scenario_id: str
    status: str = "pending"   # pending | running | complete | failed
    config: RunConfig
    environment: EnvironmentSpec | None = None
    result: RunResult | None = None
    created_at: str
    parent_run_id: str | None = None   # Phase 2 — Dynamic Scenario Graph fork/spawn lineage


def _save(record: RunRecord) -> None:
    db = SessionLocal()
    try:
        row = db.get(RunORM, record.id)
        data = record.model_dump(mode="json")
        if row is None:
            db.add(RunORM(id=record.id, scenario_id=record.scenario_id, data=data))
        else:
            row.scenario_id = record.scenario_id
            row.data = data
        db.commit()
    finally:
        db.close()


def start_run(scenario_id: str, config: RunConfig, environment: EnvironmentSpec | None = None) -> RunRecord:
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise KeyError(f"Unknown scenario '{scenario_id}'")

    env = environment or scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)
    record = RunRecord(
        id=str(uuid.uuid4()), scenario_id=scenario_id, status="running",
        config=config, environment=env, created_at=datetime.now(timezone.utc).isoformat(),
    )

    record.result = runner.execute(scenario, env, config)
    record.status = "complete"
    _save(record)
    return record


def start_run_graph(scenario_id: str, config: RunConfig,
                    environment: EnvironmentSpec | None = None) -> RunGraph:
    """Run a scenario AND every scenario its triggers cascade into — a run graph.

    Deterministic: the same (scenario, config) always produces the same graph. See
    engine/graph.py for why (no RNG / wall-clock; child ids derived from the root).
    """
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise KeyError(f"Unknown scenario '{scenario_id}'")
    env = environment or scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)
    root_run_id = str(uuid.uuid4())
    rg = graph_engine.run_graph(
        scenario, env, config,
        root_run_id=root_run_id, get_scenario=get_scenario, execute=runner.execute,
    )
    _GRAPHS[rg.root_run_id] = rg
    return rg


def get_graph(root_run_id: str) -> RunGraph | None:
    return _GRAPHS.get(root_run_id)


def get_run(run_id: str) -> RunRecord | None:
    db = SessionLocal()
    try:
        row = db.get(RunORM, run_id)
        return RunRecord(**row.data) if row else None
    finally:
        db.close()


def list_runs(scenario_id: str | None = None) -> list[RunRecord]:
    db = SessionLocal()
    try:
        q = db.query(RunORM)
        if scenario_id:
            q = q.filter(RunORM.scenario_id == scenario_id)
        runs = [RunRecord(**row.data) for row in q.all()]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)
    finally:
        db.close()