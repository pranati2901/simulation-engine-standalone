"""GET/POST /scenarios/* — the scenario library + NL authoring."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..scenarios.loader import get_scenario, scenarios_for_domain

# Try importing advanced authoring; fall back gracefully
try:
    from ..services.authoring import AuthoringError, author_scenario
    _HAS_AUTHORING = True
except ImportError:
    _HAS_AUTHORING = False

_DOMAIN_MAP = {
    "datacenter": "aerospace", "manufacturing": "aerospace", "edm-machine": "aerospace",
    "gas-turbine": "aerospace", "tram-network": "railway", "mrt-line": "railway",
    "ev-network": "railway", "naval-vessel": "defence",
}
def _resolve(d): return _DOMAIN_MAP.get(d, d)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
def list_scenarios(domain: str = "generic"):
    return scenarios_for_domain(_resolve(domain))


@router.get("/{scenario_id}")
def get_scenario_detail(scenario_id: str):
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    return scenario


class AuthorRequest(BaseModel):
    domain: str
    prompt: str


@router.post("/author")
async def author(req: AuthorRequest):
    """Author a runnable Scenario from natural language."""
    domain = _resolve(req.domain)
    if not _HAS_AUTHORING:
        raise HTTPException(501, "Scenario authoring service not available")
    try:
        return await author_scenario(domain, req.prompt)
    except AuthoringError as e:
        raise HTTPException(422, str(e))
