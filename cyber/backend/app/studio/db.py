"""Scenario Studio ORM tables (separate from the cyber engine's tables).

Persisted (not the demo's flat in-memory lists): authored scenarios are versioned & shareable, runs
survive restart, and the Anthropic key/model are stored as settings.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class StudioScenario(Base):
    """An authored or curated what-if scenario (any sector)."""
    __tablename__ = "studio_scenarios"

    id: Mapped[str] = mapped_column(String(48), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(64), default="generic", index=True)
    kind: Mapped[str] = mapped_column(String(16), default="scenario")   # scenario | fault
    description: Mapped[str] = mapped_column(Text, default="")
    is_seed: Mapped[bool] = mapped_column(default=False)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)                  # full ScenarioSpec
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StudioRun(Base):
    """A simulated run of a scenario, with its timeline + KPI-scored result."""
    __tablename__ = "studio_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    scenario_id: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(64), default="generic")
    status: Mapped[str] = mapped_column(String(16), default="completed")
    spec: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # RunResult (events/kpis/score…)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
