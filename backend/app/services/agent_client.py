"""Client for the AUTOMIND Agentic AI service.

Per the integration contract: the Scenario Engine never calls an LLM directly. Natural-
language scenario authoring, outcome narration, and training coaching are all delegated
to the Agentic AI platform — this engine orchestrates and scores, it doesn't reason in
prose. The Agentic AI repo owns the actual LLM calls; this is the thin client.

Wire protocol (AUTOMIND's hub facade, auth-free behind the hub gateway):

    POST {AGENTIC_AI_BASE_URL}/api/v1/agents/run
         {"capability": "<id>", "context": {...}}
      -> {"capability": "<id>", "mode": "agent|stub", "result": {...}, ...}

AUTOMIND itself falls back to a deterministic stub when it has no model key, so
these calls only fail when the service is unreachable — which we surface as
AgentUnavailable so the API layer can return a readable 503/422.
"""
from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel

from ..core.settings import settings

Capability = Literal["author", "analyze", "coach", "procedure"]

# engine-side verb -> AUTOMIND capability id
_CAPABILITY_MAP = {
    "author": "author-scenario-graph",
    "analyze": "analyze-outcome",
    "coach": "scenario-chat",
    "procedure": "procedure",
}


class AgentUnavailable(RuntimeError):
    """The Agentic AI service could not be reached or rejected the request."""


class AgentRequest(BaseModel):
    capability: Capability
    domain: str
    prompt: str | None = None
    context: dict = {}


class AgentResponse(BaseModel):
    capability: Capability
    result: dict
    mode: str = "agent"          # "agent" (real LLM) or "stub" (deterministic)


async def run_capability(request: AgentRequest) -> AgentResponse:
    """Delegate an authoring/analysis/coaching task to the Agentic AI service."""
    upstream = _CAPABILITY_MAP[request.capability]
    context = dict(request.context or {})
    context.setdefault("domain", request.domain)
    if request.prompt is not None:
        context.setdefault("description", request.prompt)
        context.setdefault("prompt", request.prompt)

    url = settings.agentic_ai_base_url.rstrip("/") + "/api/v1/agents/run"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
            resp = await client.post(url, json={"capability": upstream, "context": context})
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("detail", "")
        except Exception:  # noqa: BLE001
            detail = exc.response.text[:200]
        raise AgentUnavailable(
            f"Agentic AI rejected '{upstream}' ({exc.response.status_code}): {detail}") from exc
    except httpx.HTTPError as exc:
        raise AgentUnavailable(
            f"Agentic AI service unreachable at {settings.agentic_ai_base_url}: {exc}") from exc

    result = payload.get("result")
    if not isinstance(result, dict):
        raise AgentUnavailable(f"Agentic AI returned no result for '{upstream}'")
    return AgentResponse(capability=request.capability, result=result,
                         mode=payload.get("mode", "agent"))


async def author_scenario_from_nl(domain: str, prompt: str, context: dict | None = None) -> AgentResponse:
    return await run_capability(AgentRequest(capability="author", domain=domain,
                                             prompt=prompt, context=context or {}))


async def narrate_outcome(domain: str, run_result: dict) -> AgentResponse:
    return await run_capability(AgentRequest(capability="analyze", domain=domain, context=run_result))
