"""Objective scoring — the Scenario Engine's value-add.

`compute_kpis` turns a simulated run into objective KPIs + a readiness score/grade (deterministic,
not the LLM's opinion). `grade_training` is the authoritative server-side grader for the interactive
trainer (perform/skip with safety & order penalties) — moved out of the demo's React component.
"""
from __future__ import annotations

from .models import (GradeLogEntry, Kpis, Procedure, ScenarioSpec, SimulationResult,
                     TrainAction, TrainingGrade)

_BAND_BASE = {"Contained": 88, "Degraded": 70, "Severe": 48, "Critical": 28}


def _grade_letter(score: int, bands=((85, "A"), (70, "B"), (55, "C"), (40, "D"))) -> str:
    for cut, letter in bands:
        if score >= cut:
            return letter
    return "F"


def compute_kpis(spec: ScenarioSpec, sim: SimulationResult) -> Kpis:
    m = sim.metrics
    detected = bool(sim.detections) or m.time_to_detect_min is not None
    mttd = m.time_to_detect_min or 0.0
    if m.time_to_impact_min is not None:
        lead = max(0.0, m.time_to_impact_min - mttd)
    else:
        # no hard impact within the horizon → the whole remaining window is "lead time"
        lead = max(0.0, spec.horizon_min - mttd)

    base = _BAND_BASE.get(sim.outcome_band, 60)
    horizon = max(1.0, spec.horizon_min)
    lead_bonus = min(10.0, (lead / horizon) * 14.0)                 # more warning window → better
    mit_bonus = min(8.0, len(sim.mitigations) * 2.0)               # more actionable mitigations → better
    downtime_pen = min(22.0, (m.downtime_min / horizon) * 30.0)    # more downtime → worse
    detect_pen = 0.0 if detected else 14.0
    score = round(max(0.0, min(100.0, base + lead_bonus + mit_bonus - downtime_pen - detect_pen)))

    return Kpis(
        outcome_band=sim.outcome_band, detected=detected, mttd_min=round(mttd, 1),
        lead_time_min=round(lead, 1), peak_severity_pct=round(m.peak_severity * 100),
        downtime_min=round(m.downtime_min, 1), affected_units=m.affected_units,
        mitigations_identified=len(sim.mitigations), readiness_score=score, grade=_grade_letter(score))


# ── Interactive training grading (authoritative, server-side) ─────────
START_HEALTH = 0.42
MAX_HEALTH = 0.97
SKIP_PENALTY = 0.06
ORDER_PENALTY = 0.09
SAFETY_PENALTY = 0.20


def grade_training(procedure: Procedure, actions: list[TrainAction]) -> TrainingGrade:
    steps = {s.id: s for s in procedure.steps}
    total = len(procedure.steps)
    recovery = (MAX_HEALTH - START_HEALTH) / total if total else 0.0

    applied: list[str] = []
    health = START_HEALTH
    violations = skips = 0
    log: list[GradeLogEntry] = []

    for act in actions:
        s = steps.get(act.step_id)
        if s is None or s.id in applied:
            continue
        if act.action == "skip":
            health = max(0.05, health - SKIP_PENALTY)
            skips += 1
            log.append(GradeLogEntry(step_id=s.id, ok=False, skipped=True,
                                     text="Skipped — " + (s.skip_consequence or "the fault persists."),
                                     health_after=round(health * 100)))
            continue
        # perform
        req_met = all(r in applied for r in s.requires)
        if req_met:
            applied.append(s.id)
            health = min(0.99, health + recovery)
            log.append(GradeLogEntry(step_id=s.id, ok=True,
                                     text=f"{s.title} done — {s.criteria or 'complete.'}",
                                     health_after=round(health * 100)))
        else:
            missing_safety = any(steps.get(r) and steps[r].safety and r not in applied for r in s.requires)
            pen = SAFETY_PENALTY if missing_safety else ORDER_PENALTY
            health = max(0.05, health - pen)
            violations += 1
            log.append(GradeLogEntry(
                step_id=s.id, ok=False, severe=missing_safety,
                text=("SAFETY VIOLATION — " if missing_safety else "Out of order — ")
                     + (s.wrong_order_consequence or "prerequisites not met."),
                health_after=round(health * 100)))

    score = max(0, 100 - violations * 12 - skips * 8)
    grade = _grade_letter(score, ((90, "A"), (75, "B"), (60, "C")))
    complete = len(applied) == total and total > 0
    if complete and violations == 0 and skips == 0:
        summary = "Flawless run — textbook flow."
    elif complete:
        summary = f"Complete with {violations} order/safety slip(s) and {skips} skip(s). Try a cleaner run."
    else:
        summary = f"{len(applied)}/{total} steps performed."
    return TrainingGrade(score=score, grade=grade, health_pct=round(health * 100), performed=len(applied),
                         total=total, violations=violations, skips=skips, complete=complete,
                         log=log, summary=summary)
