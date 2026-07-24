"""Seed-scenario registry. Python builders are the authoring tool; their output is the
seed content stored in the DB and exported to JSON for interchange / the builder UI."""
from __future__ import annotations

from app.engine.scenario import Scenario

from .definitions import operation_black_phoenix as _obp
from .definitions import operation_black_phoenix_red as _obp_red
from .definitions import operation_black_phoenix_soc as _obp_soc
from .definitions import operation_black_phoenix_blue as _obp_blue

# Register seed scenario builders here. New seed scenario = add its builder.
_BUILDERS = [_obp.build, _obp_red.build, _obp_soc.build, _obp_blue.build]


def load_seed_scenarios() -> list[Scenario]:
    return [build() for build in _BUILDERS]


def get_seed_scenario(scenario_id: str) -> Scenario | None:
    for s in load_seed_scenarios():
        if s.id == scenario_id:
            return s
    return None
