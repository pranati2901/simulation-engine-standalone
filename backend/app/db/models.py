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

    # Tenancy. NULL means a SHARED SEED — the scenarios that self-register from
    # scenarios/definitions/** at startup. Every org sees those; that is the product
    # (the tested cross-vertical library), not a leak.
    #
    # A non-null org_id means an org AUTHORED or REVISED it, and only that org sees it.
    # Visibility rule, applied in scenarios/loader.py:  org_id IS NULL OR org_id = :org
    #
    # `id` stays the GLOBAL primary key rather than a composite (id, org_id), because
    # scenarios reference each other by bare id — triggers[].spawns[].scenario_id — and a
    # composite key would make every cascade edge ambiguous about whose scenario it means.
    # Authored and revised ids already carry a uuid suffix, so cross-org id collision
    # isn't a practical concern, and authoring._validate rejects a duplicate id anyway.
    org_id = Column(String, index=True, nullable=True)


class RunORM(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, index=True, nullable=False)
    data = Column(JSON, nullable=False)  # full RunRecord pydantic model, as JSON
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Tenancy — STRICTER than scenarios: matched by equality, never shared. There is no
    # "seed run" concept; a run belongs to whoever executed it. A NULL org_id is a run made
    # without tenant context (standalone, or pre-tenancy data) and is visible only to a
    # request that likewise has no org.
    org_id = Column(String, index=True, nullable=True)


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