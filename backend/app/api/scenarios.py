"""GET/POST /scenarios/* — the scenario library + NL authoring.

Per the porting guide: authoring delegates to Agentic AI, this layer never calls an
LLM directly.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..scenarios.loader import get_scenario, scenarios_for_domain
from ..services.agent_client import author_scenario_from_nl

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
    """Author a runnable scenario spec from natural language, via the Agentic AI."""
    response = await author_scenario_from_nl(req.domain, req.prompt)
    return response.result
