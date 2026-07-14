"""GET/POST /scenarios/* — the scenario library + NL authoring.

Per the porting guide: authoring delegates to Agentic AI, this layer never calls an
LLM directly.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..scenarios.loader import get_scenario, scenarios_for_domain
from ..services.authoring import AuthoringError, author_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
def list_scenarios(domain: str = "generic"):
    return scenarios_for_domain(domain)


@router.get("/{scenario_id}")
def get_one(scenario_id: str):
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(404, f"Unknown scenario '{scenario_id}'")
    return scenario


class AuthorRequest(BaseModel):
    domain: str
    prompt: str


@router.post("/author")
async def author(req: AuthorRequest):
    """Author a runnable Scenario from natural language, and register it.

    The model writes the SPEC — the fault, the decision gate, the objectives, and the
    cascade triggers. It does not simulate: once registered, engine/graph.py computes
    the cascade deterministically, exactly as it does for a hand-written scenario. The
    returned scenario is immediately runnable via POST /runs/graph.

    422 (not 500) on an authoring failure: an unusable prompt or a model that kept
    naming actions this domain doesn't have is a request problem, not a server fault,
    and the detail says which.
    """
    try:
        return await author_scenario(req.domain, req.prompt)
    except AuthoringError as e:
        raise HTTPException(422, str(e))
