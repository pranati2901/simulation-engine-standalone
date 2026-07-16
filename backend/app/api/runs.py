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
    mode: str = "decision"        # decision | training | twin — one engine, mode-tailored view


# One execution, three lenses. The engine runs the same deterministic cascade; `mode`
# only changes the *summary view* attached to the result — Prem's unified execution API.
_IMPACT_W = {"low": 0.4, "medium": 1.0, "high": 2.2, "critical": 4.0}


def _downstream_counts(nodes: list[dict], edges: list[dict]) -> dict[str, int]:
    kids: dict[str, list[str]] = {}
    for e in edges:
        kids.setdefault(e["parent_run_id"], []).append(e["child_run_id"])

    def reach(rid: str, seen: set[str]) -> set[str]:
        for c in kids.get(rid, []):
            if c not in seen:
                seen.add(c)
                reach(c, seen)
        return seen

    return {n["run_id"]: len(reach(n["run_id"], set())) for n in nodes}


def _mode_view(nodes: list[dict], edges: list[dict], mode: str) -> dict:
    def w(n: dict) -> float:
        return _IMPACT_W.get(n.get("impact_level"), 1.0)

    if mode == "training":
        pts = [
            {"name": n["scenario_name"], "kind": n["node_kind"],
             "why": ("Root decision — contain this to stop the cascade."
                     if n["node_kind"] == "fault"
                     else "Avoidable consequence if the response is late.")}
            for n in nodes if n["node_kind"] == "fault"
        ]
        return {"lens": "training", "headline": "Decisions to get right",
                "decision_points": pts[:6], "count": len(pts),
                "avoidable_consequences": sum(1 for e in edges if e.get("preventable"))}

    if mode == "twin":
        dc = _downstream_counts(nodes, edges)
        ranked = sorted(nodes, key=lambda n: (dc[n["run_id"]], w(n)), reverse=True)
        return {"lens": "twin", "headline": "Critical assets — most sits downstream",
                "critical_assets": [
                    {"name": n["scenario_name"], "impact_level": n["impact_level"],
                     "downstream": dc[n["run_id"]]} for n in ranked[:5]]}

    ranked = sorted(nodes, key=w, reverse=True)
    return {"lens": "decision", "headline": "Exposure & preventability",
            "top_drivers": [
                {"name": n["scenario_name"], "impact_level": n["impact_level"],
                 "weight": round(w(n), 1)} for n in ranked[:5]],
            "preventable_links": sum(1 for e in edges if e.get("preventable")),
            "total_weight": round(sum(w(n) for n in nodes), 1)}


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
    Dynamic Scenario Graph. Returns a RunGraph (nodes + edges + rollups) plus a
    `mode_view` tailored to req.mode (decision | training | twin)."""
    try:
        rg = run_manager.start_run_graph(req.scenario_id, req.config, req.environment)
    except KeyError as e:
        raise HTTPException(404, str(e))
    data = rg.model_dump(mode="json") if hasattr(rg, "model_dump") else dict(rg)
    data["mode"] = req.mode
    data["mode_view"] = _mode_view(data.get("nodes", []), data.get("edges", []), req.mode)
    return data


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