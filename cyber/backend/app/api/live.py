"""REST endpoints for live multiplayer sessions (create / list / join / detail).

Live *play* happens over the WebSocket (ws/live.py); these endpoints exist so the lobby works
before a socket is open: a host starts a session, it appears in the open list, and others join by
clicking it and entering a name. No accounts — a player is just a name + a server-issued id.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_session
from app.db.models import Scenario as ScenarioRow
from app.engine.scenario import Objectives, Scenario
from app.live import guided as guided_mod
from app.live import guided_runtime as gr
from app.live import missions as mp
from app.live.manager import manager

router = APIRouter(prefix="/api/live", tags=["live"])


class CreateSessionRequest(BaseModel):
    host_name: str = "host"
    mission_id: str | None = None     # launch a dedicated, self-contained mission
    scenario_id: str | None = None    # OR launch a pre-built scenario (e.g. Black Phoenix)


class CreateGuidedRequest(BaseModel):
    host_name: str = "host"
    scenario_id: str                  # a guided scenario id, e.g. "scn-wannacry-w1"
    mode: str = "teach"               # "teach" (Live Scenario) | "practice" (Scenario Library)


class JoinRequest(BaseModel):
    name: str = "operator"


def _load_scenario(db: Session, scenario_id: str) -> Scenario:
    row = db.get(ScenarioRow, scenario_id)
    if row is None:
        raise HTTPException(404, "scenario not found")
    return Scenario.model_validate(row.definition)


@router.get("/missions")
def list_missions() -> list[dict]:
    """The dedicated, standalone mission catalog (offensive/validation family)."""
    return [mp.public(m) for m in mp.MISSIONS]


@router.post("/sessions", status_code=201)
def create_session(req: CreateSessionRequest, db: Session = Depends(get_session)) -> dict:
    if req.mission_id:
        if req.mission_id not in mp.MISSION_BY_ID:
            raise HTTPException(404, "mission not found")
        scenario = mp.scenario_for(req.mission_id)
        session, host = manager.create(scenario, scenario.recommended_topology, req.host_name)
        session.mission = req.mission_id
        session.mission_locked = True
    elif req.scenario_id:
        scenario = _load_scenario(db, req.scenario_id)
        session, host = manager.create(scenario, scenario.recommended_topology, req.host_name)
    else:
        raise HTTPException(422, "provide a mission_id or a scenario_id")
    return {"session_id": session.id, "player_id": host.id,
            "scenario_name": session.scenario_name, "status": session.status}


@router.get("/guided")
def list_guided_scenarios() -> list[dict]:
    """The 3 guided demo scenarios (W1/R5/C5) — what the frontend offers."""
    return guided_mod.list_guided()


@router.get("/guided/{scenario_id}")
def get_guided_scenario(scenario_id: str) -> dict:
    """Full guided scenario script: phases + per-role Red/Blue/SOC tasks + decision points."""
    scn = guided_mod.get_guided(scenario_id)
    if scn is None:
        raise HTTPException(404, "guided scenario not found")
    return scn.public()


@router.post("/guided/sessions", status_code=201)
def create_guided_session(req: CreateGuidedRequest) -> dict:
    """Start a guided walkthrough: a multi-user live session driven by the scenario's phase script.

    Builds a corp+data world for the map, starts the session (so empty seats auto-drive), and attaches
    the GuidedRun (which auto-arms real-tool live-fire against the Docker range).
    """
    scn = guided_mod.get_guided(req.scenario_id)
    if scn is None:
        raise HTTPException(404, "guided scenario not found")
    env = mp.environment_for("ransomware_sim")   # corp + data + SOC terrain for the map
    scenario = Scenario(
        id=scn.id, name=scn.name, type="red", label="Guided",
        description=scn.summary, recommended_topology=env, phases=[],
        objectives=Objectives(red=[], blue=[]),
    )
    session, host = manager.create(scenario, env, req.host_name)
    with manager.lock(session.id):
        session.start()
        # Immersive sim workspace if this scenario has a sim catalog (W1…); else the guided room.
        from app.live.sim import tools as sim_tools
        if sim_tools.catalog(scn.id):
            from app.live.sim.engine import ScenarioSim
            session.sim = ScenarioSim(scn.id)
            session.sim.session = session
            session.sim.configure_mode(req.mode, None)   # teach (live) vs practice (library)
            session.arm_live_fire(True)        # real recon/enum tools fire against the lab when up
            mode = "sim"
        else:
            gr.attach(session, scn.id)
            mode = "guided"
    return {"session_id": session.id, "player_id": host.id, "scenario_id": scn.id,
            "scenario_name": session.scenario_name, "status": session.status,
            "guided": True, "mode": mode}


@router.get("/sessions")
def list_sessions() -> list[dict]:
    return manager.list_open()


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str) -> dict:
    session = manager.get(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    s = session.list_summary()
    s["players"] = [p.public() for p in session.players.values()]
    return s


@router.get("/sessions/{session_id}/report")
def get_session_report(session_id: str) -> dict:
    """The all-teams After-Action Report for a concluded live mission."""
    session = manager.get(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    if session.report is None:
        raise HTTPException(409, "report not ready — the mission has not concluded yet")
    return session.report


@router.post("/sessions/{session_id}/join", status_code=201)
def join_session(session_id: str, req: JoinRequest) -> dict:
    session = manager.get(session_id)
    if session is None:
        raise HTTPException(404, "session not found")
    with manager.lock(session_id):
        player = session.add_player(req.name)
    return {"session_id": session.id, "player_id": player.id,
            "scenario_name": session.scenario_name, "status": session.status}
