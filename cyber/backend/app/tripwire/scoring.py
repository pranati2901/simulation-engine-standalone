"""Tripwire scoring — 5-dimension model from SRS §12.

Dimensions: Detection (25%), Response (30%), Containment (25%), Speed (10%), Knowledge (10%).
Modifiers: hint penalty, backup cap, hard-fail floor.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import TripwireSession

from .engine import Mode, ResponseQuality, SceneDecision


# Response quality → points (out of 100 per scene)
QUALITY_POINTS = {
    ResponseQuality.OPTIMAL.value: 100,
    ResponseQuality.ACCEPTABLE.value: 60,
    ResponseQuality.POOR.value: 0,
}

# Hint penalty per hint tier used (subtracted from detection score for that scene)
HINT_PENALTY = 10  # points per hint


def _classify_response(scene_def: dict, actions: list[str]) -> tuple[str, str]:
    """Determine response quality from the chosen actions.

    Returns (quality, feedback_key). The scene_def's respond.actions each have a quality tag.
    If multiple actions selected, overall quality = best selected quality, unless a 'poor' action
    is the ONLY one selected.
    """
    respond = scene_def.get("respond", {})
    action_defs = {a["id"]: a for a in respond.get("actions", [])}

    if not actions:
        return ResponseQuality.POOR.value, "no_action"

    qualities = []
    for aid in actions:
        adef = action_defs.get(aid)
        if adef:
            qualities.append(adef.get("quality", "poor"))

    if not qualities:
        return ResponseQuality.POOR.value, "unknown_actions"

    # Best quality wins (optimal > acceptable > poor)
    rank = {"optimal": 3, "acceptable": 2, "poor": 1}
    best = max(qualities, key=lambda q: rank.get(q, 0))
    return best, "mixed" if len(set(qualities)) > 1 else best


def score_decision(
    session: TripwireSession,
    scene_def: dict,
    identify_choice: str,
    actions: list[str],
    latency_ms: int,
    hints_used: int,
) -> dict:
    """Score a student's identify + respond decision for one scene.

    Returns dict with 'decision' (SceneDecision), 'effects' (network deltas), 'feedback' (dict).
    """
    scoring = scene_def.get("scoring", {})
    identify = scene_def.get("identify", {})
    effects_map = scene_def.get("effects", {})

    # --- Identify scoring ---
    correct_option = None
    for opt in identify.get("options", []):
        if opt.get("correct"):
            correct_option = opt["id"]
            break

    identify_correct = identify_choice == correct_option
    identify_points = scoring.get("identify_points", 100) if identify_correct else 0

    # Apply hint penalty
    hint_cost = hints_used * HINT_PENALTY
    identify_points = max(0, identify_points - hint_cost)

    session.scores.detection_points += identify_points
    session.scores.detection_max += scoring.get("identify_points", 100)

    # --- Response scoring ---
    quality, quality_detail = _classify_response(scene_def, actions)
    response_weights = scoring.get("response_weights", QUALITY_POINTS)
    response_points = response_weights.get(quality, 0)

    session.scores.response_points += response_points
    session.scores.response_max += 100

    # --- Speed scoring ---
    speed_max = scoring.get("speed_bonus_max_ms", 20000)
    speed_bonus_points = scoring.get("speed_bonus_points", 30)
    if session.mode == Mode.PRESSURE and latency_ms > 0 and speed_max > 0:
        speed_earned = max(0, speed_bonus_points * (1 - latency_ms / speed_max))
    elif session.mode == Mode.STANDARD and latency_ms > 0 and speed_max > 0:
        speed_earned = max(0, speed_bonus_points * 0.5 * (1 - latency_ms / speed_max))
    else:
        speed_earned = 0  # Guided mode: no speed scoring

    session.scores.speed_points += speed_earned
    session.scores.speed_max += speed_bonus_points if session.mode != Mode.GUIDED else 0

    # --- Network effects ---
    effects = effects_map.get(quality, effects_map.get("poor", {}))

    # --- Feedback ---
    feedback = _build_feedback(scene_def, identify_correct, identify_choice,
                               correct_option, quality, quality_detail)

    # --- Build decision record ---
    decision = SceneDecision(
        scene_index=session.scene_index,
        identify_choice=identify_choice,
        identify_correct=identify_correct,
        actions=actions,
        response_quality=quality,
        latency_ms=latency_ms,
        hints_used=hints_used,
        score_delta={
            "detection": identify_points,
            "response": response_points,
            "speed": round(speed_earned, 1),
        },
    )

    return {"decision": decision, "effects": effects, "feedback": feedback}


def _build_feedback(scene_def: dict, identify_correct: bool,
                    chosen: str, correct: str | None,
                    quality: str, quality_detail: str) -> dict:
    """Build scene feedback for the student."""
    identify = scene_def.get("identify", {})
    options_by_id = {o["id"]: o.get("text", "") for o in identify.get("options", [])}

    fb: dict = {
        "identify_correct": identify_correct,
        "response_quality": quality,
    }

    if identify_correct:
        fb["identify_message"] = "Correct. You identified the technique."
    else:
        fb["identify_message"] = (
            f"Incorrect. The correct answer was: {options_by_id.get(correct, correct)}."
        )

    if quality == "optimal":
        fb["response_message"] = "Optimal response. This is the best action for this stage."
    elif quality == "acceptable":
        fb["response_message"] = "Acceptable response, but a stronger option was available."
    else:
        fb["response_message"] = "Poor response. This allows the attack to progress unchecked."

    # Micro-teach from scene definition
    fb["micro_teach"] = scene_def.get("micro_teach", "")

    return fb


def score_quiz(
    session: TripwireSession,
    quiz_bank: list[dict],
    answers: list[dict],
) -> dict:
    """Score the knowledge assessment quiz.

    quiz_bank: list of {id, correct_id, ...}
    answers: list of {item_id, response}
    """
    bank_by_id = {q["id"]: q for q in quiz_bank}
    results = []
    correct_count = 0

    for ans in answers:
        item = bank_by_id.get(ans.get("item_id", ""))
        if item is None:
            results.append({"item_id": ans.get("item_id"), "correct": False, "error": "unknown item"})
            continue

        is_correct = ans.get("response") == item.get("correct_id")
        if is_correct:
            correct_count += 1
        results.append({
            "item_id": ans["item_id"],
            "response": ans.get("response"),
            "correct_id": item.get("correct_id"),
            "correct": is_correct,
            "rationale": item.get("rationale", ""),
        })

    total = len(answers) if answers else 1
    session.scores.knowledge_points = correct_count
    session.scores.knowledge_max = total

    return {"answers": results, "correct": correct_count, "total": total}
