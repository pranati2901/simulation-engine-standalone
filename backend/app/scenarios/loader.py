"""Loads declarative scenario definitions into the runtime scenario library.

Persisted to Postgres (db/models.py::ScenarioORM) instead of the old in-memory
_LIBRARY dict. Scenarios are still versioned, importable Python modules under
scenarios/definitions/<domain>/ — load_all() imports them so their module-level
register_scenario(...) calls run, same as before. The only thing that changed
is register_scenario/get_scenario/scenarios_for_domain now read/write the DB,
which also means a future "procedure import" (dynamic, non-Python scenario
creation) can call register_scenario() at request time, not just at startup.
"""
from __future__ import annotations

import importlib
import pkgutil

from ..db.base import SessionLocal
from ..db.models import ScenarioORM
from ..engine.catalog.spec import register_action
from ..engine.scenario import Scenario

_loaded = False


def register_scenario(scenario: Scenario) -> None:
    db = SessionLocal()
    try:
        row = db.get(ScenarioORM, scenario.id)
        data = scenario.model_dump(mode="json")
        if row is None:
            db.add(ScenarioORM(id=scenario.id, domain=scenario.domain, data=data))
        else:
            row.domain = scenario.domain
            row.data = data
        db.commit()
    finally:
        db.close()


def _materialise(row: ScenarioORM) -> Scenario:
    """Rebuild a Scenario from its row — and re-register any vocabulary it carries.

    Scenarios are persisted; the action catalog is an in-memory dict rebuilt at import
    time from the domain plugins. So a scenario that introduced its own action (an
    authored one — see services/authoring.py) would come back from the database with a
    step referencing an action the catalog has never heard of, and the run would die with
    `KeyError: Unknown action '...'`. Re-registering here closes that gap: the scenario's
    vocabulary is restored at exactly the moment the scenario is.

    register_action() is an idempotent dict write, so doing this on every load is cheap
    and safe.
    """
    scenario = Scenario(**row.data)
    for action in scenario.custom_actions:
        register_action(action)
    return scenario


def get_scenario(scenario_id: str) -> Scenario | None:
    db = SessionLocal()
    try:
        row = db.get(ScenarioORM, scenario_id)
        return _materialise(row) if row else None
    finally:
        db.close()


def scenarios_for_domain(domain: str) -> list[Scenario]:
    db = SessionLocal()
    try:
        rows = (
            db.query(ScenarioORM)
            .filter(ScenarioORM.domain == domain)
            .order_by(ScenarioORM.id)
            .all()
        )
        return [_materialise(row) for row in rows]
    finally:
        db.close()


def load_all() -> None:
    """Import every module under scenarios/definitions/** so their module-level
    register_scenario(...) calls run. Mirrors plugins/registry.py's load_all pattern.
    """
    global _loaded
    if _loaded:
        return
    from . import definitions
    for _, module_name, is_pkg in pkgutil.walk_packages(definitions.__path__, definitions.__name__ + "."):
        if not is_pkg:
            importlib.import_module(module_name)
    _loaded = True