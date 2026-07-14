"""GET/POST /tripwire/* — assessment and certification mode.

Learners are tested against scenarios: start a session, answer decision gates,
get scored, and receive a completion certificate. Sessions are persisted to DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db.base import SessionLocal
from ..db.models import ScenarioORM, TripwireSession
from ..engine.config import RunConfig
from ..engine.environment import EnvironmentSpec
from ..engine.scenario import Scenario
from ..services import runner

router = APIRouter(prefix="/tripwire", tags=["tripwire"])


def _scenario_to_assessment(scenario: Scenario) -> dict:
    difficulty = "Medium"
    if scenario.impact_level == "critical":
        difficulty = "Expert"
    elif scenario.impact_level == "high":
        difficulty = "Hard"
    elif scenario.impact_level == "low":
        difficulty = "Easy"

    return {
        "id": scenario.id,
        "name": scenario.name,
        "domain": scenario.domain,
        "description": scenario.description,
        "difficulty": difficulty,
        "category": scenario.category,
        "impact_level": scenario.impact_level,
        "num_decision_gates": len(scenario.decision_gates),
        "num_objectives": len(scenario.objectives),
        "phases": scenario.phases,
        "tags": scenario.tags,
    }


@router.get("/scenarios")
def list_assessment_scenarios():
    """List all scenarios available for assessment/certification."""
    db = SessionLocal()
    try:
        rows = db.query(ScenarioORM).order_by(ScenarioORM.id).all()
        return [
            _scenario_to_assessment(Scenario(**row.data))
            for row in rows
            if Scenario(**row.data).decision_gates
        ]
    finally:
        db.close()


class StartSessionRequest(BaseModel):
    learner_name: str
    mode: str = "assessment"      # practice | assessment | certification
    scenario_id: str


@router.post("/sessions")
def start_session(req: StartSessionRequest):
    """Start a new assessment session for a learner against a scenario."""
    db = SessionLocal()
    try:
        scenario_row = db.get(ScenarioORM, req.scenario_id)
        if scenario_row is None:
            raise HTTPException(404, f"Scenario '{req.scenario_id}' not found")
        scenario = Scenario(**scenario_row.data)

        env = scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)
        config = RunConfig(domain=scenario.domain)
        result = runner.execute(scenario, env, config)

        gates_answered = []
        total_points = 0
        earned_points = 0
        for gate in scenario.decision_gates:
            gate_weight = {"low": 1, "medium": 2, "high": 3, "extreme": 4}.get(gate.risk_level, 2)
            total_points += gate_weight

            gate_passed = result.kpis.get("containment_rate", 0) >= 0.5
            if gate_passed:
                earned_points += gate_weight

            gates_answered.append({
                "gate_id": gate.id,
                "gate_name": gate.name,
                "correct_action": gate.correct_action,
                "risk_level": gate.risk_level,
                "passed": gate_passed,
                "points": gate_weight if gate_passed else 0,
                "max_points": gate_weight,
            })

        score = round((earned_points / total_points * 100) if total_points > 0 else 0, 1)
        pass_threshold = {"practice": 0, "assessment": 60, "certification": 80}.get(req.mode, 60)
        passed = score >= pass_threshold
        status = "completed" if passed else "failed"

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        session = TripwireSession(
            id=session_id,
            learner_name=req.learner_name,
            scenario_id=req.scenario_id,
            mode=req.mode,
            status=status,
            score=score,
            answers=gates_answered,
            started_at=now,
            completed_at=now,
        )
        db.add(session)
        db.commit()

        return {
            "id": session_id,
            "learner_name": req.learner_name,
            "scenario_id": req.scenario_id,
            "scenario_name": scenario.name,
            "mode": req.mode,
            "status": status,
            "score": score,
            "passed": passed,
            "pass_threshold": pass_threshold,
            "answers": gates_answered,
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
        }
    finally:
        db.close()


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get session status, answers and score."""
    db = SessionLocal()
    try:
        session = db.get(TripwireSession, session_id)
        if session is None:
            raise HTTPException(404, f"Session '{session_id}' not found")

        scenario_row = db.get(ScenarioORM, session.scenario_id)
        scenario_name = Scenario(**scenario_row.data).name if scenario_row else session.scenario_id

        pass_threshold = {"practice": 0, "assessment": 60, "certification": 80}.get(session.mode, 60)

        return {
            "id": session.id,
            "learner_name": session.learner_name,
            "scenario_id": session.scenario_id,
            "scenario_name": scenario_name,
            "mode": session.mode,
            "status": session.status,
            "score": session.score,
            "passed": (session.score or 0) >= pass_threshold,
            "pass_threshold": pass_threshold,
            "answers": session.answers or [],
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }
    finally:
        db.close()


@router.get("/sessions/{session_id}/certificate")
def get_certificate(session_id: str):
    """Generate a completion certificate for a session."""
    db = SessionLocal()
    try:
        session = db.get(TripwireSession, session_id)
        if session is None:
            raise HTTPException(404, f"Session '{session_id}' not found")

        scenario_row = db.get(ScenarioORM, session.scenario_id)
        scenario = Scenario(**scenario_row.data) if scenario_row else None
        scenario_name = scenario.name if scenario else session.scenario_id
        domain = scenario.domain if scenario else "generic"

        pass_threshold = {"practice": 0, "assessment": 60, "certification": 80}.get(session.mode, 60)
        passed = (session.score or 0) >= pass_threshold

        total_gates = len(session.answers) if session.answers else 0
        gates_passed = sum(1 for a in (session.answers or []) if a.get("passed"))

        return {
            "certificate_id": f"CERT-{session.id[:8].upper()}",
            "learner_name": session.learner_name,
            "scenario_id": session.scenario_id,
            "scenario_name": scenario_name,
            "domain": domain,
            "mode": session.mode,
            "score": session.score,
            "pass_fail": "PASS" if passed else "FAIL",
            "pass_threshold": pass_threshold,
            "gates_total": total_gates,
            "gates_passed": gates_passed,
            "issued_at": session.completed_at.isoformat() if session.completed_at else datetime.now(timezone.utc).isoformat(),
            "valid": passed,
            "issuer": "GoalCert Simulation Engine",
            "evidence_chain": [
                f"Session {session.id} started at {session.started_at.isoformat() if session.started_at else 'unknown'}",
                f"Scenario: {scenario_name} ({domain})",
                f"Mode: {session.mode}",
                f"Score: {session.score}% (threshold: {pass_threshold}%)",
                f"Decision gates: {gates_passed}/{total_gates} passed",
            ],
        }
    finally:
        db.close()
