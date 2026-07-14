"""POST /runs, GET /runs/{id} — execute and inspect scenario runs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..engine.config import RunConfig
from ..engine.environment import EnvironmentSpec
from ..engine.monte_carlo import MonteCarloResult, run_monte_carlo
from ..scenarios.loader import get_scenario
from ..services import run_manager, runner

router = APIRouter(prefix="/runs", tags=["runs"])


class StartRunRequest(BaseModel):
    scenario_id: str
    config: RunConfig = RunConfig()
    environment: EnvironmentSpec | None = None


@router.post("")
def start_run(req: StartRunRequest):
    try:
        record = run_manager.start_run(req.scenario_id, req.config, req.environment)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return record


@router.post("/graph")
def start_run_graph(req: StartRunRequest):
    """Run a scenario and the full cascade of scenarios its triggers spawn — the
    Dynamic Scenario Graph. Returns a RunGraph (nodes + edges + rollups)."""
    try:
        return run_manager.start_run_graph(req.scenario_id, req.config, req.environment)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/graph/{root_run_id}")
def get_run_graph(root_run_id: str):
    rg = run_manager.get_graph(root_run_id)
    if rg is None:
        raise HTTPException(404, f"Unknown run graph '{root_run_id}'")
    return rg


@router.get("/{run_id}/events")
def get_run_events(run_id: str):
    """Return events for a run from the engine's event log."""
    record = run_manager.get_run(run_id)
    if record is None:
        raise HTTPException(404, f"Unknown run '{run_id}'")
    if record.result is None:
        return []
    return [evt.model_dump(mode="json") for evt in record.result.events]


@router.get("/{run_id}")
def get_run(run_id: str):
    record = run_manager.get_run(run_id)
    if record is None:
        raise HTTPException(404, f"Unknown run '{run_id}'")
    return record


@router.get("")
def list_runs(scenario_id: str | None = None):
    return run_manager.list_runs(scenario_id)


class MonteCarloRequest(BaseModel):
    scenario_id: str
    config: RunConfig = RunConfig()
    environment: EnvironmentSpec | None = None
    iterations: int = 100
    readiness_range: tuple[int, int] = (30, 90)


@router.post("/monte-carlo")
def run_monte_carlo_endpoint(req: MonteCarloRequest) -> MonteCarloResult:
    """Mode 1 (Operational Intelligence): run the scenario N times across a
    readiness range and return probability/confidence-range style output instead
    of a single deterministic result. Not persisted yet — returned directly.
    """
    scenario = get_scenario(req.scenario_id)
    if scenario is None:
        raise HTTPException(404, f"Unknown scenario '{req.scenario_id}'")
    if not (1 <= req.iterations <= 1000):
        raise HTTPException(400, "iterations must be between 1 and 1000")
    env = req.environment or scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)
    return run_monte_carlo(
        scenario, env, req.config, runner.execute,
        iterations=req.iterations, readiness_range=req.readiness_range,
    )