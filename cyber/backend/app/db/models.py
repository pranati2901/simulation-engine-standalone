"""ORM models. Portable JSON columns (map to JSON on Postgres, TEXT-JSON on SQLite)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(32), default="purple")
    industry: Mapped[str] = mapped_column(String(64), default="generic")
    badge: Mapped[str] = mapped_column(String(32), default="badge-purple")
    label: Mapped[str] = mapped_column(String(64), default="Scenario")
    description: Mapped[str] = mapped_column(Text, default="")
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    is_seed: Mapped[bool] = mapped_column(default=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)  # full Scenario model
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    scenario_id: Mapped[str] = mapped_column(String(64), index=True)
    scenario_name: Mapped[str] = mapped_column(String(200))
    operator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ready", index=True)
    focus_role: Mapped[str] = mapped_column(String(16), default="blue")
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    environment_spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    duration_s: Mapped[int] = mapped_column(Integer, default=0)
    scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)   # per-role {red,blue,soc,mgmt,ot}
    kpis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    objectives: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    workflows: Mapped[list] = mapped_column(JSON, default=list)     # bound team workflows
    role_tasks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # final per-role task status
    environment: Mapped[list] = mapped_column(JSON, default=list)   # initial asset snapshot
    final_assets: Mapped[list] = mapped_column(JSON, default=list)
    events: Mapped[list] = mapped_column(JSON, default=list)        # full precomputed timeline
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    report: Mapped["Report | None"] = relationship(back_populates="run", uselist=False)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped[Run] = relationship(back_populates="report")
