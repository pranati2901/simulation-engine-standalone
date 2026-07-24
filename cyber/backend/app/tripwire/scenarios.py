"""Scenario registry — maps scenario IDs to their definitions.

Adding a new scenario: create a scenario_xxx.py file with SCENARIO_META, SCENES, QUIZ_BANK,
then register it here.
"""
from __future__ import annotations

from . import scenario as w1
from . import scenario_r5 as r5
from . import scenario_c5 as c5

# All registered scenarios
REGISTRY: dict[str, dict] = {
    "scn-wannacry-w1": {
        "meta": w1.SCENARIO_META,
        "scenes": w1.SCENES,
        "quiz_bank": w1.QUIZ_BANK,
        "segments": w1.NETWORK_SEGMENTS,
        "get_scene": w1.get_scene,
        "get_quiz_subset": w1.get_quiz_subset,
    },
    "scn-r5-phish2enc": {
        "meta": r5.SCENARIO_META,
        "scenes": r5.SCENES,
        "quiz_bank": r5.QUIZ_BANK,
        "segments": r5.NETWORK_SEGMENTS,
        "get_scene": r5.get_scene,
        "get_quiz_subset": r5.get_quiz_subset,
    },
    "scn-c5-edr-outage": {
        "meta": c5.SCENARIO_META,
        "scenes": c5.SCENES,
        "quiz_bank": c5.QUIZ_BANK,
        "segments": c5.NETWORK_SEGMENTS,
        "get_scene": c5.get_scene,
        "get_quiz_subset": c5.get_quiz_subset,
    },
}


def get_scenario(scenario_id: str) -> dict:
    """Get a scenario by ID. Raises KeyError if not found."""
    if scenario_id not in REGISTRY:
        raise KeyError(f"Unknown scenario: {scenario_id}. Available: {list(REGISTRY.keys())}")
    return REGISTRY[scenario_id]


def list_scenarios() -> list[dict]:
    """List all registered scenarios (meta only)."""
    return [
        {**v["meta"], "scenes_count": len(v["scenes"]), "quiz_count": len(v["quiz_bank"])}
        for v in REGISTRY.values()
    ]
