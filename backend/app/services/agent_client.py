"""Client for the AUTOMIND Agentic AI service.

Per the integration contract: the Scenario Engine never calls an LLM directly. Natural-
language scenario authoring, outcome narration, and training coaching are all delegated
to the Agentic AI platform — this engine orchestrates and scores, it doesn't reason in
prose. Your teammate's Agentic AI repo owns the actual LLM calls; this is the thin
client + capability names we expect.

Endpoint contract (confirm with the Agentic AI team once their repo is up):
    POST /agents/run {capability: "author" | "analyze" | "coach" | "procedure", ...}
"""
from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel

from ..core.settings import settings

Capability = Literal["author", "analyze", "coach", "procedure"]


class AgentRequest(BaseModel):
    capability: Capability
    domain: str
    prompt: str | None = None
    context: dict = {}


class AgentResponse(BaseModel):
    capability: Capability
    result: dict


async def run_capability(request: AgentRequest) -> AgentResponse:
    """Delegate an authoring/analysis/coaching task to the Agentic AI service.

    TODO: once the Agentic AI service is live in Goalcert_Hub, replace with a real call:

        async with httpx.AsyncClient(base_url=settings.agentic_ai_base_url) as client:
            resp = await client.post("/agents/run", json=request.model_dump())
            resp.raise_for_status()
            return AgentResponse(**resp.json())
    """
    raise NotImplementedError(
        "Agentic AI service not yet wired up — see services/agent_client.py TODO."
    )


async def author_scenario_from_nl(domain: str, prompt: str) -> AgentResponse:
    return await run_capability(AgentRequest(capability="author", domain=domain, prompt=prompt))


async def narrate_outcome(domain: str, run_result: dict) -> AgentResponse:
    return await run_capability(AgentRequest(capability="analyze", domain=domain, context=run_result))
