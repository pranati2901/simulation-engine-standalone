"""Lab API — real-infrastructure status, control, and the tool registry.

Drives the frontend's "real lab" indicator and Tools panel. Lab control (up/down) is gated by
`settings.allow_lab_control` so it can be disabled in shared/cloud deployments.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.lab import tools as tool_registry
from app.lab.live_fire import FIRE_SPECS
from app.lab.manager import get_lab, lab_status
from app.lab.pool import get_pool

router = APIRouter(prefix="/api/lab", tags=["lab"])


@router.get("/status")
def status() -> dict:
    """Is the lab backend present, is it up, and which targets exist?"""
    return lab_status().public()


@router.get("/tools")
def tools() -> dict:
    """The tool registry — integrated (live), planned (roadmap), provided (reserved slot)."""
    return tool_registry.registry_public()


@router.get("/live-fire")
def live_fire_map() -> list[dict]:
    """Which live Red actions are backed by a real tool, and whether they run on the active lab."""
    try:
        roles = {t.role for t in get_lab().targets()}
    except Exception:
        roles = set()
    rows = []
    for f in FIRE_SPECS:
        available = f.target_role == "any" or f.target_role in roles
        rows.append({
            "action_id": f.action_id, "tool": f.tool, "function": f.function,
            "label": f.label or f.action_id, "target_role": f.target_role,
            "available": available,
            "requires": None if available else f.target_role,
        })
    return rows


@router.post("/up")
def lab_up() -> dict:
    """Provision/start the lab (local dev convenience)."""
    if not settings.allow_lab_control:
        raise HTTPException(403, "lab control is disabled (settings.allow_lab_control=False)")
    result = get_lab().up()
    return {"ok": result.success, "detail": result.output, "command": result.command}


@router.post("/down")
def lab_down() -> dict:
    """Tear the lab down."""
    if not settings.allow_lab_control:
        raise HTTPException(403, "lab control is disabled (settings.allow_lab_control=False)")
    result = get_lab().down()
    return {"ok": result.success, "detail": result.output, "command": result.command}


# ---- per-session isolated ranges (Phase 3 multi-tenant) ----------------------
@router.post("/session/{session_id}/up")
def session_lab_up(session_id: str) -> dict:
    """Provision an isolated range dedicated to this session (its own network + ports)."""
    if not settings.allow_lab_control:
        raise HTTPException(403, "lab control is disabled")
    lab, err = get_pool().provision(session_id)
    if lab is None:
        raise HTTPException(409, err)
    return {"ok": not err, "detail": err or "session range up", **lab.status().public()}


@router.post("/session/{session_id}/down")
def session_lab_down(session_id: str) -> dict:
    """Tear down this session's isolated range."""
    existed = get_pool().teardown(session_id)
    return {"ok": True, "existed": existed}


@router.get("/session/{session_id}/status")
def session_lab_status(session_id: str) -> dict:
    """Status of this session's isolated range (falls back to 'not provisioned')."""
    lab = get_pool().get(session_id)
    if lab is None:
        return {"backend": "docker", "available": True, "up": False, "provisioned": False,
                "active_ranges": len(get_pool().active())}
    return {**lab.status().public(), "provisioned": True,
            "active_ranges": len(get_pool().active())}
