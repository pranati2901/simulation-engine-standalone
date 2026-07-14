"""Client for the NextXR Digital Twin service.

Per the integration contract: the Scenario Engine never simulates physics itself. Any
run that needs a physics what-if projection calls out to the Twin so results stay
consistent with live monitoring. Your teammate's Digital Twin repo owns the actual
physics; this is just the thin client + the response shape we expect back.

Endpoint contract (confirm exact path/shape with the Digital Twin team once their repo
is up in Goalcert_Hub): POST /twins/{tenant}/project
"""
from __future__ import annotations

import httpx
from pydantic import BaseModel

from ..core.settings import settings


class ProjectionRequest(BaseModel):
    tenant: str
    domain: str
    world_snapshot: dict
    fault_or_event: dict
    horizon_min: int = 60


class ProjectionResult(BaseModel):
    world_snapshot: dict
    telemetry: list[dict] = []
    raw: dict = {}


async def project(request: ProjectionRequest) -> ProjectionResult:
    """Call the Digital Twin for a physics-based what-if projection.

    TODO: once the Digital Twin service is live in Goalcert_Hub, confirm the request/
    response schema and replace this stub with a real call, e.g.:

        async with httpx.AsyncClient(base_url=settings.digital_twin_base_url) as client:
            resp = await client.post(f"/twins/{request.tenant}/project", json=request.model_dump())
            resp.raise_for_status()
            return ProjectionResult(**resp.json())
    """
    raise NotImplementedError(
        "Digital Twin service not yet wired up — see services/twin_client.py TODO. "
        "Until then, run() falls back to the engine's own deterministic resolver."
    )
