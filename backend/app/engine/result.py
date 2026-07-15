"""Structured result of a deterministic run."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .events import SimEvent


class ObjectiveStatus(BaseModel):
    text: str
    met: bool


class ClearanceRecord(BaseModel):
    """The certification/clearance output of a competency-check run — mirrors the user
    flow doc's Step 5 ("You are cleared for procedure X on asset Y") and Rule 7
    ("every competency claim has an evidence chain"). Not cryptographically signed in
    this scaffold; add real signing when this feeds an actual compliance system.
    """
    certified: bool
    procedure: str
    domain: str
    readiness_used: int
    difficulty: str
    evidence: list[str] = Field(default_factory=list)


class RunResult(BaseModel):
    scenario_id: str
    duration_s: int
    focus_role: str = "response"
    events: list[SimEvent] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)           # {role: score} (0–100, may be fractional)
    kpis: dict[str, float] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    objectives: dict[str, list[ObjectiveStatus]] = Field(default_factory=dict)
    environment: list[dict] = Field(default_factory=list)            # initial actor snapshot
    final_actors: list[dict] = Field(default_factory=list)           # end-state actor snapshot
    workflows: list[dict] = Field(default_factory=list)              # bound role workflows
    role_tasks: dict[str, list[dict]] = Field(default_factory=dict)  # final per-role task status

    # Phase 2 — Dynamic Scenario Graph:
    child_run_ids: list[str] = Field(default_factory=list)           # runs this one spawned
    parent_run_id: str | None = None
