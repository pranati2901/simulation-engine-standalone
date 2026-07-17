"""Tiny idempotent schema migrations, run at startup.

There is no Alembic in this repo, and `Base.metadata.create_all()` only ever CREATEs
tables that don't exist — it never ALTERs one that does. So adding a column to a model is
invisible to any database that already has the old table: every query then dies with
`no such column: scenarios.org_id`, including on the seeded simulation_engine.db that
ships in this repo.

This closes that gap for the one kind of change we actually make (add a nullable column),
without pulling in a migration framework. It is deliberately not a general migration tool:
if a change needs more than ADD COLUMN, that is the moment to add Alembic rather than
grow this file.

Safe to run on every boot — each step checks the live schema first.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from .base import engine

log = logging.getLogger(__name__)

# (table, column, DDL type). Nullable only — an existing row must be able to take it.
_ADD_COLUMNS: list[tuple[str, str, str]] = [
    ("scenarios", "org_id", "VARCHAR"),
    ("runs", "org_id", "VARCHAR"),
]

# (index name, table, column)
_ADD_INDEXES: list[tuple[str, str, str]] = [
    ("ix_scenarios_org_id", "scenarios", "org_id"),
    ("ix_runs_org_id", "runs", "org_id"),
]


def run_migrations() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, column, ddl_type in _ADD_COLUMNS:
            if table not in tables:
                continue  # create_all() will build it fresh, with the column already on it
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column in existing:
                continue
            log.info("migrate: adding %s.%s", table, column)
            # Both SQLite and Postgres accept this form. Nullable, no default: existing
            # rows become NULL, which is exactly the intended meaning — a scenario that
            # predates tenancy is a shared seed, and a run that predates it has no owner.
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))

        # Re-inspect: the columns above may have only just appeared.
        fresh = inspect(engine)
        for index_name, table, column in _ADD_INDEXES:
            if table not in tables:
                continue
            if column not in {c["name"] for c in fresh.get_columns(table)}:
                continue
            if index_name in {i["name"] for i in fresh.get_indexes(table)}:
                continue
            log.info("migrate: creating index %s", index_name)
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"))
