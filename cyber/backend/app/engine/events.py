"""Timeline events — the single, unified record the engine produces and streams.

A run's output is an ordered list of SimEvent. The frontend derives everything from it:
console (TELEMETRY), alert feed (DETECTION), phase tracker (PHASE), network map (STATE),
scoreboard (SCORE), objectives (OBJECTIVE).
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
    technique: str | None = None          # MITRE technique id, when applicable
    asset_id: str | None = None
    asset_label: str | None = None
    channel: str | None = None            # console channel: siem|edr|dns|auth|email|net|ot|sys
    data: dict[str, Any] = Field(default_factory=dict)


class Emit(BaseModel):
    """A telemetry line a technique or asset produces. Becomes a TELEMETRY SimEvent."""

    channel: str = "sys"
    severity: Severity = Severity.INFO
    text: str
