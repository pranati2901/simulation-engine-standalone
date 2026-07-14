"""Persistence for request-time authored actions (AI scenario authoring).

register_action() writes into an in-memory catalog that is rebuilt from the domain
plugins on every boot — so a custom fault key authored at runtime must ALSO be stored
in the DB and re-registered at startup, or every scenario referencing it would break
after a restart.
"""
from __future__ import annotations

import logging

from ..db.base import SessionLocal
from ..db.models import CustomActionORM
from ..engine.catalog.spec import ActionSpec, register_action

logger = logging.getLogger(__name__)


def persist_custom_action(spec: ActionSpec) -> None:
    """Register into the live catalog AND persist for future boots."""
    register_action(spec)
    db = SessionLocal()
    try:
        row = db.get(CustomActionORM, spec.key)
        data = spec.model_dump(mode="json")
        if row is None:
            db.add(CustomActionORM(key=spec.key, domain=spec.domain, data=data))
        else:
            row.domain = spec.domain
            row.data = data
        db.commit()
    finally:
        db.close()


def load_custom_actions() -> int:
    """Re-register every persisted custom action. Called once at startup, after the
    domain plugins have populated the catalog."""
    db = SessionLocal()
    try:
        rows = db.query(CustomActionORM).all()
        for row in rows:
            try:
                register_action(ActionSpec(**row.data))
            except Exception:  # noqa: BLE001 — one bad row must not block startup
                logger.warning("skipping bad custom action %s", row.key)
        return len(rows)
    finally:
        db.close()
