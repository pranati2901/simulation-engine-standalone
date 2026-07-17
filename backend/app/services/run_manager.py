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
from ..scenarios.loader import get_scenario, resolver_for
from . import runner

# Run graphs, keyed by root_run_id. In-memory on purpose — see the module docstring.
#
# TENANCY: the VALUE carries its owner (org, graph) rather than the key, so a lookup can
# check ownership. Keying by (org, id) would look equivalent and isn't: get_graph would
# then need the org to build the key, and any caller that forgot would silently miss
# instead of being refused.
#
# ⚠ HORIZONTAL SCALING (read before raising the ECS task count above 1):
# This dict is PER PROCESS. A graph created on task A is invisible to task B, so
# GET /runs/graph/{root_run_id} would 404 for whichever task the load balancer happened to
# pick — intermittently, and only under load, which is the worst way to find out.
#
# It is safe TODAY only because nothing reads it back: POST /runs/graph returns the whole
# graph in its own response, and no frontend calls the GET. So the engine scales out fine
# as long as that stays true.
#
# The moment anything wants to re-open a past run graph, this needs to be persisted (its
# own table, or a JSON blob per graph — see the module docstring for why RunORM's shape
# doesn't fit) or the service pinned to one task. Do not assume "it works in staging with
# one task" generalises.
_GRAPHS: dict[str, tuple[str | None, RunGraph]] = {}


class RunRecord(BaseModel):
    id: str
    scenario_id: str
    status: str = "pending"   # pending | running | complete | failed
    config: RunConfig
    environment: EnvironmentSpec | None = None
    result: RunResult | None = None
    created_at: str
    parent_run_id: str | None = None   # Phase 2 — Dynamic Scenario Graph fork/spawn lineage


def _save(record: RunRecord, org: str | None) -> None:
    db = SessionLocal()
    try:
        row = db.get(RunORM, record.id)
        data = record.model_dump(mode="json")
        if row is None:
            db.add(RunORM(id=record.id, scenario_id=record.scenario_id, data=data, org_id=org))
        else:
            row.scenario_id = record.scenario_id
            row.data = data
        db.commit()
    finally:
        db.close()


def start_run(scenario_id: str, config: RunConfig, environment: EnvironmentSpec | None = None,
              org: str | None = None) -> RunRecord:
    scenario = get_scenario(scenario_id, org)
    if scenario is None:
        raise KeyError(f"Unknown scenario '{scenario_id}'")

    env = environment or scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)
    record = RunRecord(
        id=str(uuid.uuid4()), scenario_id=scenario_id, status="running",
        config=config, environment=env, created_at=datetime.now(timezone.utc).isoformat(),
    )

    record.result = runner.execute(scenario, env, config)
    record.status = "complete"
    _save(record, org)
    return record


def start_run_graph(scenario_id: str, config: RunConfig,
                    environment: EnvironmentSpec | None = None,
                    org: str | None = None) -> RunGraph:
    """Run a scenario AND every scenario its triggers cascade into — a run graph.

    Deterministic: the same (scenario, config) always produces the same graph. See
    engine/graph.py for why (no RNG / wall-clock; child ids derived from the root).
    """
    scenario = get_scenario(scenario_id, org)
    if scenario is None:
        raise KeyError(f"Unknown scenario '{scenario_id}'")
    env = environment or scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)
    root_run_id = str(uuid.uuid4())
    rg = graph_engine.run_graph(
        scenario, env, config,
        # Org-bound: cascades must resolve within what this tenant can see, or an org's
        # authored scenario could never cascade into its own other scenarios.
        root_run_id=root_run_id, get_scenario=resolver_for(org), execute=runner.execute,
    )
    _GRAPHS[rg.root_run_id] = (org, rg)
    return rg


def get_graph(root_run_id: str, org: str | None = None) -> RunGraph | None:
    """Another tenant's graph reads as None — same as a run they can't see."""
    entry = _GRAPHS.get(root_run_id)
    if entry is None:
        return None
    owner, rg = entry
    return rg if owner == org else None


def get_run(run_id: str, org: str | None = None) -> RunRecord | None:
    db = SessionLocal()
    try:
        row = db.get(RunORM, run_id)
        if row is None or row.org_id != org:
            return None   # not found, or not yours — same answer either way
        return RunRecord(**row.data)
    finally:
        db.close()


def list_runs(scenario_id: str | None = None, org: str | None = None) -> list[RunRecord]:
    db = SessionLocal()
    try:
        # Equality, not the scenarios' "IS NULL OR mine" rule: runs are never shared.
        # `== None` compiles to `IS NULL` in SQLAlchemy, which is what we want for the
        # org-less standalone case.
        q = db.query(RunORM).filter(RunORM.org_id == org)
        if scenario_id:
            q = q.filter(RunORM.scenario_id == scenario_id)
        runs = [RunRecord(**row.data) for row in q.all()]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)
    finally:
        db.close()