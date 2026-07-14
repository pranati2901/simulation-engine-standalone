"""GET /live/guided/* — guided training mode.

Walk learners through scenarios step by step, providing structured instructions,
expected actions, and hints at each stage. Scenarios are surfaced from the
existing scenario library with auto-generated guided steps derived from their
phases, decision gates, and scenario steps.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db.base import SessionLocal
from ..db.models import ScenarioORM
from ..engine.scenario import Scenario

router = APIRouter(prefix="/live", tags=["guided"])


def _build_guided_steps(scenario: Scenario) -> list[dict]:
    """Derive guided training steps from a scenario's phases, steps and decision gates."""
    guided_steps: list[dict] = []
    step_num = 1

    for phase in scenario.phases:
        phase_steps = [s for s in scenario.steps if s.phase == phase]
        phase_gates = [g for g in scenario.decision_gates if any(
            s.id == g.trigger for s in phase_steps
        )]

        if phase_steps:
            for sc_step in phase_steps:
                matching_gate = next(
                    (g for g in scenario.decision_gates if g.trigger == sc_step.id), None
                )
                hints = []
                if sc_step.expected_signals:
                    hints.append(
                        f"Look for {sc_step.expected_signals[0].indicator_type} "
                        f"indicators: {sc_step.expected_signals[0].signal or 'anomalous readings'}"
                    )
                if matching_gate:
                    hints.append(f"Risk level: {matching_gate.risk_level}")
                    if matching_gate.consequence_of_delay:
                        hints.append(f"If delayed: {matching_gate.consequence_of_delay}")
                hints.append(f"This step belongs to the '{phase}' phase of the scenario")

                guided_steps.append({
                    "step_number": step_num,
                    "phase": phase,
                    "instruction": sc_step.label or f"Execute action: {sc_step.action}",
                    "expected_action": matching_gate.correct_action if matching_gate else sc_step.action,
                    "hints": hints,
                    "action_key": sc_step.action,
                    "is_inject": sc_step.is_inject,
                    "at_min": sc_step.at_min,
                })
                step_num += 1
        else:
            guided_steps.append({
                "step_number": step_num,
                "phase": phase,
                "instruction": f"Progress through the '{phase}' phase and observe the environment",
                "expected_action": f"Monitor and assess during {phase}",
                "hints": [
                    f"Pay attention to all telemetry and alerts during the '{phase}' phase",
                    "Review any signals or indicators that emerge",
                ],
                "action_key": None,
                "is_inject": False,
                "at_min": 0.0,
            })
            step_num += 1

    return guided_steps


def _scenario_to_guided(scenario: Scenario) -> dict:
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
        "phases": scenario.phases,
        "total_steps": max(len(scenario.steps), len(scenario.phases)),
        "tags": scenario.tags,
        "objectives": [obj.text for obj in scenario.objectives],
    }


@router.get("/guided")
def list_guided():
    """List all scenarios available for guided training.

    Every scenario with phases and decision gates qualifies for guided mode.
    """
    db = SessionLocal()
    try:
        rows = db.query(ScenarioORM).order_by(ScenarioORM.id).all()
        results = []
        for row in rows:
            scenario = Scenario(**row.data)
            if scenario.phases and (scenario.steps or scenario.decision_gates):
                results.append(_scenario_to_guided(scenario))
        return results
    finally:
        db.close()


@router.get("/guided/{scenario_id:path}")
def guided_detail(scenario_id: str):
    """Get guided session details with step-by-step instructions."""
    db = SessionLocal()
    try:
        row = db.get(ScenarioORM, scenario_id)
        if row is None:
            raise HTTPException(404, f"Scenario '{scenario_id}' not found")
        scenario = Scenario(**row.data)
        if not scenario.phases:
            raise HTTPException(400, f"Scenario '{scenario_id}' has no phases for guided training")

        steps = _build_guided_steps(scenario)
        info = _scenario_to_guided(scenario)
        info["steps"] = steps
        info["decision_gates"] = [
            {
                "id": g.id,
                "name": g.name,
                "correct_action": g.correct_action,
                "risk_level": g.risk_level,
                "description": g.description,
                "delay_s": g.delay_s,
            }
            for g in scenario.decision_gates
        ]
        return info
    finally:
        db.close()
