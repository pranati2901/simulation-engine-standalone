"""GET/POST /scenarios/* — the scenario library, NL authoring, and NL revision.

Every route is tenant-scoped via the `org` dependency (core/tenancy.py). An org sees the
shared seed library plus whatever it authored; another tenant's scenario 404s exactly as a
nonexistent one does.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core.tenancy import current_org
from ..scenarios.loader import get_scenario, scenarios_for_domain

# Try importing advanced authoring; fall back gracefully
try:
    from ..services.authoring import AuthoringError, author_scenario
    from ..services.revision import commit_scenario, revise_scenario
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
def list_scenarios(domain: str = "generic", org: str | None = Depends(current_org)):
    return scenarios_for_domain(_resolve(domain), org)


@router.get("/{scenario_id}")
def get_scenario_detail(scenario_id: str, org: str | None = Depends(current_org)):
    scenario = get_scenario(scenario_id, org)
    if scenario is None:
        raise HTTPException(404, f"Scenario '{scenario_id}' not found")
    return scenario


class AuthorRequest(BaseModel):
    domain: str
    prompt: str


@router.post("/author")
async def author(req: AuthorRequest, org: str | None = Depends(current_org)):
    """Author a runnable Scenario from natural language. It belongs to the calling org."""
    domain = _resolve(req.domain)
    if not _HAS_AUTHORING:
        raise HTTPException(501, "Scenario authoring service not available")
    try:
        return await author_scenario(domain, req.prompt, org=org)
    except AuthoringError as e:
        raise HTTPException(422, str(e))


class ReviseRequest(BaseModel):
    instruction: str
    # The spec to revise. Omit to revise the STORED scenario; pass the previous proposal
    # to keep revising it, so a chat conversation compounds instead of each turn starting
    # over from the seed.
    scenario: dict[str, Any] | None = None


@router.post("/{scenario_id}/revise")
async def revise(scenario_id: str, req: ReviseRequest, org: str | None = Depends(current_org)):
    """Propose a revision of a scenario from a plain-English instruction.

    Registers NOTHING — returns {scenario, changes, base_id} for the operator to approve.
    Hand `scenario` back to POST /scenarios/commit to make it real.
    """
    if not _HAS_AUTHORING:
        raise HTTPException(501, "Scenario authoring service not available")
    try:
        return await revise_scenario(scenario_id, req.instruction, req.scenario, org=org)
    except AuthoringError as e:
        raise HTTPException(422, str(e))


class CommitRequest(BaseModel):
    scenario: dict[str, Any]


@router.post("/commit")
async def commit(req: CommitRequest, org: str | None = Depends(current_org)):
    """Register a previewed revision as a new scenario owned by the calling org. The
    original — seed or otherwise — is never touched."""
    if not _HAS_AUTHORING:
        raise HTTPException(501, "Scenario authoring service not available")
    try:
        return await commit_scenario(req.scenario, org=org)
    except AuthoringError as e:
        raise HTTPException(422, str(e))
