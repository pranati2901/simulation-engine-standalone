"""POST /jilla/* — Jilla AI, the in-scenario AI assistant for learners.

Provides real-time guidance, answers questions, and gives hints during scenario
execution. Uses Claude Haiku for fast responses. Falls back to context-aware
template responses when the API key is not configured.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.settings import settings
from ..db.base import SessionLocal
from ..db.models import ScenarioORM
from ..engine.scenario import Scenario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jilla", tags=["jilla"])


def _get_scenario_context(scenario_id: str | None) -> dict:
    """Build context dict from a scenario for the AI to reference."""
    if not scenario_id:
        return {"available": False}
    db = SessionLocal()
    try:
        row = db.get(ScenarioORM, scenario_id)
        if row is None:
            return {"available": False, "scenario_id": scenario_id}
        scenario = Scenario(**row.data)
        return {
            "available": True,
            "scenario_id": scenario.id,
            "name": scenario.name,
            "domain": scenario.domain,
            "description": scenario.description,
            "phases": scenario.phases,
            "steps": [
                {"id": s.id, "action": s.action, "phase": s.phase, "label": s.label}
                for s in scenario.steps
            ],
            "decision_gates": [
                {
                    "id": g.id,
                    "name": g.name,
                    "correct_action": g.correct_action,
                    "risk_level": g.risk_level,
                    "description": g.description,
                }
                for g in scenario.decision_gates
            ],
            "objectives": [{"text": o.text, "role": o.role} for o in scenario.objectives],
        }
    finally:
        db.close()


def _call_anthropic(system_prompt: str, user_message: str) -> str:
    """Call Claude Haiku for a fast AI response."""
    if not settings.anthropic_api_key:
        return ""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text
    except ImportError:
        logger.warning("anthropic package not installed")
        return ""
    except Exception as e:
        logger.warning("Anthropic API call failed: %s", e)
        return ""


# ── POST /jilla/event ──────────────────────────────────────────────────────────

class EventRequest(BaseModel):
    scenario_id: str | None = None
    event_type: str = ""              # action, detection, phase, state, etc.
    event_data: dict = Field(default_factory=dict)
    current_phase: str | None = None
    learner_role: str = "response"


@router.post("/event")
def process_event(req: EventRequest):
    """Process a scenario event and return AI guidance for the learner."""
    ctx = _get_scenario_context(req.scenario_id)

    system_prompt = (
        "You are Jilla, an AI training assistant for the GoalCert simulation platform. "
        "A learner is in a live scenario exercise. An event just occurred. "
        "Provide brief, actionable guidance (2-3 sentences max). "
        "Be encouraging but direct. Focus on what the learner should do next. "
        f"Scenario context: {ctx}"
    )
    user_msg = (
        f"Event type: {req.event_type}. Phase: {req.current_phase}. "
        f"Role: {req.learner_role}. Event details: {req.event_data}"
    )

    ai_response = _call_anthropic(system_prompt, user_msg)

    if not ai_response:
        scenario_name = ctx.get("name", "this scenario")
        phase_info = f" during the '{req.current_phase}' phase" if req.current_phase else ""
        event_label = req.event_data.get("title", req.event_type)

        if req.event_type in ("action", "ACTION"):
            guidance = (
                f"A fault event ({event_label}) has been injected{phase_info}. "
                f"As the {req.learner_role} team, begin your diagnostic process. "
                "Check telemetry feeds and identify affected systems."
            )
        elif req.event_type in ("detection", "DETECTION"):
            guidance = (
                f"A detection alert has fired{phase_info}: {event_label}. "
                "Assess the severity, correlate with known indicators, and determine "
                "whether escalation is needed."
            )
        elif req.event_type in ("phase", "PHASE"):
            guidance = (
                f"The scenario has transitioned to the '{req.current_phase}' phase. "
                "Review your current situation awareness and adjust your response strategy."
            )
        elif req.event_type in ("decision", "DECISION"):
            guidance = (
                f"A decision gate has been reached{phase_info}. "
                "Evaluate the available options carefully. Consider the risk level "
                "and potential consequences of delay before acting."
            )
        else:
            guidance = (
                f"An event ({event_label}) occurred in {scenario_name}{phase_info}. "
                "Monitor the situation and prepare to respond if action is needed."
            )

        ai_response = guidance

    return {
        "guidance": ai_response,
        "event_type": req.event_type,
        "scenario_id": req.scenario_id,
        "current_phase": req.current_phase,
        "source": "anthropic" if settings.anthropic_api_key else "template",
    }


# ── POST /jilla/chat ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    scenario_id: str | None = None
    message: str
    current_phase: str | None = None
    learner_role: str = "response"
    history: list[dict] = Field(default_factory=list)


@router.post("/chat")
def chat(req: ChatRequest):
    """Learner asks a question during a scenario, AI responds with context-aware answer."""
    ctx = _get_scenario_context(req.scenario_id)

    system_prompt = (
        "You are Jilla, an AI training assistant for the GoalCert simulation platform. "
        "A learner is asking a question during a live scenario exercise. "
        "Answer clearly and concisely. Reference the scenario context when relevant. "
        "Do NOT give away answers to decision gates directly, but guide the learner's thinking. "
        f"Scenario context: {ctx}. "
        f"Current phase: {req.current_phase}. Learner role: {req.learner_role}."
    )

    ai_response = _call_anthropic(system_prompt, req.message)

    if not ai_response:
        scenario_name = ctx.get("name", "the current scenario")
        domain = ctx.get("domain", "generic")
        phases = ctx.get("phases", [])
        phase_info = f" You are currently in the '{req.current_phase}' phase." if req.current_phase else ""

        msg_lower = req.message.lower()
        if any(w in msg_lower for w in ["what should i do", "next step", "what now"]):
            if req.current_phase and req.current_phase in phases:
                phase_idx = phases.index(req.current_phase)
                next_phase = phases[phase_idx + 1] if phase_idx < len(phases) - 1 else None
                ai_response = (
                    f"In the '{req.current_phase}' phase of {scenario_name}, focus on "
                    f"the core objective for your role ({req.learner_role}).{phase_info}"
                )
                if next_phase:
                    ai_response += f" After this, you'll move to the '{next_phase}' phase."
            else:
                ai_response = (
                    f"Review the scenario objectives and current alerts. "
                    f"As the {req.learner_role} team, prioritize based on severity."
                )
        elif any(w in msg_lower for w in ["help", "stuck", "confused"]):
            objectives = ctx.get("objectives", [])
            obj_text = objectives[0]["text"] if objectives else "respond to the current situation"
            ai_response = (
                f"Take a step back and review the situation.{phase_info} "
                f"Your primary objective is: {obj_text}. "
                "Check the telemetry panel for clues about what's happening."
            )
        elif any(w in msg_lower for w in ["hint", "clue"]):
            gates = ctx.get("decision_gates", [])
            if gates:
                gate = gates[0]
                ai_response = (
                    f"Consider the '{gate['name']}' decision point. "
                    f"The risk level is {gate['risk_level']}. "
                    "Think about what the correct response procedure would be."
                )
            else:
                ai_response = (
                    f"Review the available data in {scenario_name}. "
                    "Look for patterns in the telemetry and alerts."
                )
        else:
            ai_response = (
                f"That's a good question about {scenario_name} ({domain} domain).{phase_info} "
                f"As {req.learner_role}, focus on the indicators and alerts in your dashboard. "
                "The scenario objectives panel shows what you need to achieve."
            )

    return {
        "response": ai_response,
        "scenario_id": req.scenario_id,
        "current_phase": req.current_phase,
        "source": "anthropic" if settings.anthropic_api_key else "template",
    }


# ── POST /jilla/hint ──────────────────────────────────────────────────────────

class HintRequest(BaseModel):
    scenario_id: str | None = None
    current_phase: str | None = None
    current_step: str | None = None
    learner_role: str = "response"
    difficulty: str = "Medium"


@router.post("/hint")
def get_hint(req: HintRequest):
    """Request a hint for the current scenario step."""
    ctx = _get_scenario_context(req.scenario_id)

    system_prompt = (
        "You are Jilla, an AI training assistant for the GoalCert simulation platform. "
        "The learner is requesting a hint. Provide a helpful but not too revealing hint. "
        "Scale the hint detail inversely with difficulty (more help on Easy, less on Expert). "
        f"Difficulty: {req.difficulty}. "
        f"Scenario context: {ctx}. "
        f"Current phase: {req.current_phase}. Current step: {req.current_step}."
    )
    user_msg = f"I need a hint. I'm playing as {req.learner_role}."

    ai_response = _call_anthropic(system_prompt, user_msg)

    if not ai_response:
        scenario_name = ctx.get("name", "this scenario")
        steps = ctx.get("steps", [])
        gates = ctx.get("decision_gates", [])

        current_step_data = next((s for s in steps if s["id"] == req.current_step), None)
        relevant_gate = None
        if current_step_data:
            relevant_gate = next(
                (g for g in gates if g.get("id") and any(
                    s["id"] == current_step_data["id"] for s in steps
                )),
                gates[0] if gates else None,
            )
        elif gates:
            relevant_gate = gates[0]

        if req.difficulty in ("Easy", "easy"):
            if relevant_gate:
                ai_response = (
                    f"Here's a strong hint: for the '{relevant_gate['name']}' decision, "
                    f"the expected response involves: {relevant_gate['correct_action'][:80]}... "
                    "Focus on executing this correctly."
                )
            elif current_step_data:
                ai_response = (
                    f"The current step involves '{current_step_data.get('label', current_step_data['action'])}'. "
                    f"Look at the {current_step_data['phase']} phase procedures for guidance."
                )
            else:
                ai_response = (
                    f"In {scenario_name}, start by reviewing all available telemetry data. "
                    "The alerts panel will show you what needs attention first."
                )
        elif req.difficulty in ("Expert", "expert"):
            ai_response = (
                "Review your standard operating procedures for this type of incident. "
                "The answer is in the data available to you."
            )
        else:
            if relevant_gate:
                ai_response = (
                    f"Focus on the '{relevant_gate['name']}' decision. "
                    f"Risk level: {relevant_gate['risk_level']}. "
                    "Consider what the standard response procedure would be for this type of fault."
                )
            elif current_step_data:
                ai_response = (
                    f"Pay attention to the indicators related to '{current_step_data['action']}'. "
                    "What does the telemetry tell you about the current state?"
                )
            else:
                ai_response = (
                    f"In {scenario_name}, check the current phase objectives. "
                    "The scenario is designed to test your response to the injected fault."
                )

    return {
        "hint": ai_response,
        "scenario_id": req.scenario_id,
        "current_phase": req.current_phase,
        "current_step": req.current_step,
        "difficulty": req.difficulty,
        "source": "anthropic" if settings.anthropic_api_key else "template",
    }
