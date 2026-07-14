"""Timeline events — the single, unified record the engine produces and streams.

A run's output is an ordered list of SimEvent. Any frontend (or the Digital Twin's own
viewer) derives everything from it: console log, alert feed, phase tracker, world/map
view, scoreboard, objectives. Unchanged in spirit from GoalCert's engine/events.py —
this pattern is fully domain-agnostic already.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import EventType, Severity, Side


class SimEvent(BaseModel):
    seq: int                              # global monotonic order
    t: int                                # sim-time offset in seconds
    type: EventType
    side: Side = Side.SYSTEM
    actor: str = "engine"                 # role/actor attributed with the event
    phase: str | None = None
    severity: Severity = Severity.INFO
    title: str = ""
    message: str = ""
    action: str | None = None             # catalog action id, when applicable (was `technique`)
    actor_id: str | None = None           # world ActorInstance id, when applicable
    actor_label: str | None = None
    channel: str | None = None            # console channel: telemetry|alerts|ops|comms|...
    data: dict[str, Any] = Field(default_factory=dict)
    scenario_id: str | None = None        # which scenario node emitted this (Dynamic Scenario Graph)


class Emit(BaseModel):
    """A telemetry line an action or actor produces. Becomes a TELEMETRY SimEvent."""
    channel: str = "sys"
    severity: Severity = Severity.INFO
    text: str
