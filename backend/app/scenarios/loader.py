"""Loads declarative scenario definitions into the runtime scenario library.

Persisted to the database (db/models.py::ScenarioORM) instead of the old in-memory
_LIBRARY dict. Scenarios are still versioned, importable Python modules under
scenarios/definitions/<domain>/ — load_all() imports them so their module-level
register_scenario(...) calls run, same as before.

TENANCY
-------
Every read takes an `org`. The visibility rule is one line and lives ONLY here:

    org_id IS NULL  OR  org_id = :org

  • org_id NULL  -> a shared seed (everything under definitions/). Every tenant sees it.
  • org_id set   -> authored or revised by that tenant. Only they see it.
  • org None     -> no tenant context (standalone): sees seeds and its own org-less work.

`org` defaults to None so the module-level register_scenario() calls in definitions/**
keep working untouched and land as seeds. That default is safe for reads too: the worst
case is seeing only the shared library, never another tenant's data.
"""
from __future__ import annotations

import importlib
import pkgutil

from sqlalchemy import or_

from ..db.base import SessionLocal
from ..db.models import ScenarioORM
from ..engine.catalog.spec import register_action
from ..engine.scenario import Scenario

_loaded = False


def _visible(query, org: str | None):
    """Scenarios this org may see: the shared seeds, plus its own."""
    return query.filter(or_(ScenarioORM.org_id.is_(None), ScenarioORM.org_id == org))


def register_scenario(scenario: Scenario, org: str | None = None) -> None:
    """Persist a scenario. `org=None` registers a shared seed — that is what the
    definitions/** modules do at import time.

    An update never lets one tenant overwrite another's row, or a tenant overwrite a seed:
    the write is refused unless the existing row is already theirs.
    """
    db = SessionLocal()
    try:
        row = db.get(ScenarioORM, scenario.id)
        data = scenario.model_dump(mode="json")
        if row is None:
            db.add(ScenarioORM(id=scenario.id, domain=scenario.domain, data=data, org_id=org))
        else:
            if row.org_id != org:
                # Guards two cases: org B mutating org A's scenario, and an org silently
                # overwriting a shared seed for everyone. Both are ownership violations,
                # not merges — refuse rather than reassign.
                raise PermissionError(
                    f"Scenario '{scenario.id}' belongs to another tenant and cannot be overwritten."
                )
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


def get_scenario(scenario_id: str, org: str | None = None) -> Scenario | None:
    """One scenario, if this org may see it. Another tenant's scenario reads as None —
    indistinguishable from "doesn't exist", which is what the caller should tell them.
    """
    db = SessionLocal()
    try:
        row = _visible(db.query(ScenarioORM).filter(ScenarioORM.id == scenario_id), org).first()
        return _materialise(row) if row else None
    finally:
        db.close()


def scenario_id_exists(scenario_id: str) -> bool:
    """Does this id exist for ANYONE? Deliberately unscoped, and the one place that is
    correct: `id` is the global primary key, so an insert collides across tenants even
    though a read would not. Authoring uses this to reject a duplicate id up front rather
    than fail on the INSERT.
    """
    db = SessionLocal()
    try:
        return db.get(ScenarioORM, scenario_id) is not None
    finally:
        db.close()


def scenarios_for_domain(domain: str, org: str | None = None) -> list[Scenario]:
    db = SessionLocal()
    try:
        rows = (
            _visible(db.query(ScenarioORM).filter(ScenarioORM.domain == domain), org)
            .order_by(ScenarioORM.id)
            .all()
        )
        return [_materialise(row) for row in rows]
    finally:
        db.close()


def resolver_for(org: str | None):
    """A `get_scenario(id) -> Scenario | None` bound to one org.

    The cascade engine (engine/graph.py) resolves triggers[].spawns[].scenario_id through a
    callable it is handed. Passing the bare get_scenario there would resolve every spawn
    with org=None — so an org's authored scenario could cascade into seeds but never into
    its OWN other scenarios, and the graph would silently come back short. Bind the org.
    """
    def _get(scenario_id: str) -> Scenario | None:
        return get_scenario(scenario_id, org)
    return _get


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
