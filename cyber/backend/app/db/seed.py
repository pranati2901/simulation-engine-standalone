"""Seed the DB with the bundled scenarios (catalog is served live from code registries)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.scenarios.loader import load_seed_scenarios

from .models import Scenario as ScenarioRow


def seed_all(db: Session) -> None:
    for sc in load_seed_scenarios():
        row = db.get(ScenarioRow, sc.id)
        definition = sc.model_dump(mode="json")
        if row is None:
            db.add(ScenarioRow(
                id=sc.id, name=sc.name, type=sc.type, industry=sc.industry,
                badge=sc.badge, label=sc.label, description=sc.description,
                schema_version=sc.schema_version, is_seed=True, definition=definition,
            ))
        else:
            # keep seed scenarios in sync with code
            row.name, row.type, row.industry = sc.name, sc.type, sc.industry
            row.badge, row.label, row.description = sc.badge, sc.label, sc.description
            row.schema_version, row.definition, row.is_seed = sc.schema_version, definition, True
