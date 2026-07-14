"""ORM models — real persisted tables replacing the old in-memory dicts.

ScenarioORM backs scenarios/loader.py (both the Python-defined scenarios that
self-register at startup, and any dynamically-imported ones added later).
RunORM backs services/run_manager.py's single-run records.

Run *graphs* (services/run_manager.py::_GRAPHS, a DAG of RunResults from the
Dynamic Scenario Graph / cascade engine) are intentionally NOT covered here —
they don't fit this same id/data shape cleanly and need their own schema
decision. Flagged in run_manager.py rather than guessed at.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, String

from .base import Base


class ScenarioORM(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True)
    domain = Column(String, index=True, nullable=False)
    data = Column(JSON, nullable=False)  # full Scenario pydantic model, as JSON


class RunORM(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, index=True, nullable=False)
    data = Column(JSON, nullable=False)  # full RunRecord pydantic model, as JSON
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CustomActionORM(Base):
    """Actions authored at request time (AI scenario authoring) — persisted so the
    in-memory action catalog can be re-populated on startup (see app/main.py)."""
    __tablename__ = "custom_actions"

    key = Column(String, primary_key=True)
    domain = Column(String, index=True, nullable=False)
    data = Column(JSON, nullable=False)  # full ActionSpec pydantic model, as JSON


class TripwireSession(Base):
    __tablename__ = "tripwire_sessions"

    id = Column(String, primary_key=True)
    learner_name = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False)
    mode = Column(String, nullable=False)          # practice, assessment, certification
    status = Column(String, default="active")      # active, completed, failed
    score = Column(Float, nullable=True)
    answers = Column(JSON, default=[])
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)