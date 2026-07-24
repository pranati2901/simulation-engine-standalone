"""Tripwire REST API — session lifecycle, decisions, quiz, results."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .engine import TripwireSession
from .scenarios import get_scenario, list_scenarios

router = APIRouter(prefix="/api/tripwire", tags=["tripwire"])

# In-memory session store (replace with DB persistence for production)
_sessions: dict[str, TripwireSession] = {}


def _get(session_id: str) -> TripwireSession:
    s = _sessions.get(session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    return s


# ---- Request models ----
class StartRequest(BaseModel):
    learner_name: str
    mode: str = "standard"
    scenario_id: str = "scn-wannacry-w1"


class DecisionRequest(BaseModel):
    scene_index: int
    identify_choice: str
    actions: list[str]
    latency_ms: int = 0
    hints_used: int = 0


class QuizAnswer(BaseModel):
    item_id: str
    response: str


class QuizRequest(BaseModel):
    answers: list[QuizAnswer]


# ---- Endpoints ----

@router.get("/scenarios")
def list_all_scenarios() -> list[dict]:
    """List all available educational scenarios."""
    return list_scenarios()


@router.get("/scenarios/{scenario_id}")
def get_scenario_detail(scenario_id: str) -> dict:
    """Get scenario metadata + scene list."""
    scn = get_scenario(scenario_id)
    return {
        **scn["meta"],
        "scenes_count": len(scn["scenes"]),
        "scenes": [{"index": s["index"], "title": s["title"], "mitre": s["mitre"]} for s in scn["scenes"]],
    }


@router.post("/sessions", status_code=201)
def start_session(req: StartRequest) -> dict:
    """Start a new simulation session."""
    get_scenario(req.scenario_id)  # validate scenario exists
    session = TripwireSession(learner_name=req.learner_name, mode=req.mode, scenario_id=req.scenario_id)
    _sessions[session.id] = session
    session.start_briefing()
    return session.snapshot()


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    """Get current session state."""
    return _get(session_id).snapshot()


@router.post("/sessions/{session_id}/start-scene")
def start_scene(session_id: str, scene_index: int) -> dict:
    """Advance to a scene. Call with scene_index=0 after briefing, then 1, 2, etc."""
    session = _get(session_id)
    try:
        session.start_scene(scene_index)
    except ValueError as e:
        raise HTTPException(400, str(e))

    scene_def = get_scenario(session.scenario_id)["get_scene"](scene_index)
    # Auto-advance through ENTER → OBSERVE → IDENTIFY
    session.advance_sub("observe")
    session.advance_sub("identify")

    return {
        "session": session.snapshot(),
        "scene": {
            "index": scene_def["index"],
            "title": scene_def["title"],
            "mitre": scene_def["mitre"],
            "story": scene_def["story"],
            "telemetry": scene_def["telemetry"],
            "identify": scene_def["identify"],
        },
    }


@router.post("/sessions/{session_id}/identify")
def submit_identify(session_id: str, identify_choice: str) -> dict:
    """Submit the identify answer. Advances to RESPOND and reveals response options."""
    session = _get(session_id)
    try:
        session.advance_sub("respond")
    except ValueError as e:
        raise HTTPException(400, str(e))

    scene_def = get_scenario(session.scenario_id)["get_scene"](session.scene_index)
    return {
        "session": session.snapshot(),
        "respond": scene_def["respond"],
    }


@router.post("/sessions/{session_id}/decision")
def submit_decision(session_id: str, req: DecisionRequest) -> dict:
    """Submit identify + respond decision for a scene. Scores and applies effects."""
    session = _get(session_id)

    if session.scene_index != req.scene_index:
        raise HTTPException(400, f"Expected scene {session.scene_index}, got {req.scene_index}")

    # Ensure we're in RESPOND state
    if session.scene_sub and session.scene_sub.value == "identify":
        session.advance_sub("respond")

    scene_def = get_scenario(session.scenario_id)["get_scene"](req.scene_index)
    try:
        result = session.submit_decision(
            scene_def, req.identify_choice, req.actions,
            req.latency_ms, req.hints_used,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "session": session.snapshot(),
        "result": result,
        "scene_micro_teach": scene_def.get("micro_teach", ""),
    }


@router.post("/sessions/{session_id}/finish-scene")
def finish_scene(session_id: str) -> dict:
    """Finish the current scene and prepare for next (or debrief)."""
    session = _get(session_id)
    try:
        session.finish_scene()
    except ValueError as e:
        raise HTTPException(400, str(e))
    return session.snapshot()


@router.get("/sessions/{session_id}/debrief")
def get_debrief(session_id: str) -> dict:
    """Get the debrief timeline (all decisions + network state progression)."""
    session = _get(session_id)
    timeline = []
    for d in session.decisions:
        scene_def = get_scenario(session.scenario_id)["get_scene"](d.scene_index)
        timeline.append({
            "scene_index": d.scene_index,
            "title": scene_def["title"],
            "mitre": scene_def["mitre"],
            "identify_correct": d.identify_correct,
            "response_quality": d.response_quality,
            "score_delta": d.score_delta,
            "latency_ms": d.latency_ms,
        })
    return {
        "session": session.snapshot(),
        "timeline": timeline,
        "network_final": session.network.snapshot(),
    }


@router.post("/sessions/{session_id}/start-assessment")
def start_assessment(session_id: str) -> dict:
    """Move from DEBRIEF to ASSESSMENT. Returns quiz questions."""
    session = _get(session_id)
    try:
        session.start_assessment()
    except ValueError as e:
        raise HTTPException(400, str(e))

    scn = get_scenario(session.scenario_id)
    quiz = scn["get_quiz_subset"](10)
    # Strip correct answers before sending to client
    client_quiz = []
    for q in quiz:
        client_quiz.append({
            "id": q["id"],
            "question": q["question"],
            "options": [{"id": o["id"], "text": o["text"]} for o in q["options"]],
        })

    return {
        "session": session.snapshot(),
        "quiz": client_quiz,
        "quiz_ids": [q["id"] for q in quiz],  # server tracks which items were served
    }


@router.post("/sessions/{session_id}/quiz")
def submit_quiz(session_id: str, req: QuizRequest) -> dict:
    """Submit quiz answers. Scores and finalizes the session."""
    session = _get(session_id)
    answers = [{"item_id": a.item_id, "response": a.response} for a in req.answers]
    scn = get_scenario(session.scenario_id)
    try:
        result = session.submit_quiz(scn["quiz_bank"], answers)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {
        "session": session.snapshot(),
        "result": result,
    }


@router.get("/sessions/{session_id}/events")
def get_events(session_id: str) -> list[dict]:
    """Get the full event log for the session (for audit/replay)."""
    return _get(session_id).events


@router.get("/sessions")
def list_sessions(limit: int = 20) -> list[dict]:
    """List recent sessions."""
    sessions = sorted(_sessions.values(), key=lambda s: s.created_at, reverse=True)
    return [s.snapshot() for s in sessions[:limit]]


@router.get("/sessions/{session_id}/certificate")
def get_certificate(session_id: str) -> dict:
    """Get the certificate for a completed, passing session."""
    session = _get(session_id)
    if session.certificate is None:
        raise HTTPException(404, "No certificate — session not completed or not passing")
    return session.certificate


@router.get("/learner/{learner_name}/attempts")
def get_learner_attempts(learner_name: str, scenario_id: str = "scn-wannacry-w1") -> dict:
    """Get attempt history for a learner on a scenario. Best score is retained."""
    attempts = [
        s for s in _sessions.values()
        if s.learner_name == learner_name and s.scenario_id == scenario_id
        and s.status.value in ("completed", "failed")
    ]
    attempts.sort(key=lambda s: s.created_at)

    best = max((s.scores.composite(s.mode) for s in attempts), default=0)
    best_grade = ""
    for s in attempts:
        if s.scores.composite(s.mode) == best:
            best_grade = s.scores.grade(s.mode)[0]
            break

    needs_remediation = len(attempts) > 0 and best < 60

    return {
        "learner_name": learner_name,
        "scenario_id": scenario_id,
        "attempt_count": len(attempts),
        "max_attempts": 3,
        "best_composite": round(best, 1),
        "best_grade": best_grade,
        "can_retry": len(attempts) < 3,
        "needs_remediation": needs_remediation,
        "attempts": [
            {
                "session_id": s.id,
                "composite": round(s.scores.composite(s.mode), 1),
                "grade": s.scores.grade(s.mode)[0],
                "passed": s.scores.grade(s.mode)[1],
                "outcome": s._outcome_label(),
                "created_at": s.created_at,
            }
            for s in attempts
        ],
    }


@router.get("/sessions/{session_id}/xapi")
def get_xapi_statements(session_id: str) -> list[dict]:
    """Generate xAPI statement stubs for a session (for LRS integration)."""
    session = _get(session_id)
    statements = []
    for ev in session.events:
        verb = None
        if ev["type"] == "scene_entered":
            verb = "experienced"
        elif ev["type"] == "decision_submitted":
            verb = "responded"
        elif ev["type"] == "session_completed":
            verb = "completed"

        if verb:
            statements.append({
                "actor": {"name": session.learner_name, "mbox": f"mailto:{session.learner_name}@goalcert.local"},
                "verb": {"id": f"http://adlnet.gov/expapi/verbs/{verb}", "display": {"en-US": verb}},
                "object": {
                    "id": f"https://goalcert.com/scenarios/{session.scenario_id}/event/{ev['seq']}",
                    "definition": {"name": {"en-US": ev["type"]}, "description": {"en-US": str(ev.get("payload", {}))}},
                },
                "result": ev.get("payload", {}),
                "timestamp": ev.get("ts"),
            })
    return statements
