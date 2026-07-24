"""Structured result of a deterministic run."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .events import SimEvent


class ObjectiveStatus(BaseModel):
    text: str
    met: bool


class RunResult(BaseModel):
    scenario_id: str
    duration_s: int
    focus_role: str = "blue"
    events: list[SimEvent] = Field(default_factory=list)
    scores: dict[str, int] = Field(default_factory=dict)          # {red, blue, soc, mgmt, ot}
    kpis: dict[str, float] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    objectives: dict[str, list[ObjectiveStatus]] = Field(default_factory=dict)  # {red, blue}
    environment: list[dict] = Field(default_factory=list)         # initial asset snapshot (map)
    final_assets: list[dict] = Field(default_factory=list)        # end-state asset snapshot
    workflows: list[dict] = Field(default_factory=list)           # bound team workflows (sub-reports)
    role_tasks: dict[str, list[dict]] = Field(default_factory=dict)  # final per-role task status
