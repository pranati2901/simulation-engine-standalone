"""Generic action catalog.

Was GoalCert's engine/catalog/techniques.py (a hardcoded MITRE ATT&CK technique
catalog). Replaced with a domain-agnostic ActionSpec + a registry that domain plugins
populate at import time — the engine core ships with zero built-in actions.

Example: the aerospace plugin registers "hydraulic_leak", "bird_strike_damage",
"gate_reassignment"; the railway plugin registers "signal_failure", "track_obstruction";
the same ActionSpec shape and resolver logic handles all of them.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..events import Emit


class ActionSpec(BaseModel):
    key: str                                   # unique action id, e.g. "hydraulic_leak"
    name: str
    category: str = "generic"                  # "spread" | "detection" | "response" | ...
    domain: str = "generic"                    # owning plugin
    requires_target: bool = True
    preconditions: list[str] = Field(default_factory=list)
    prevention: dict[str, int] = Field(default_factory=dict)   # resource_type -> difficulty threshold
    telemetry: list[Emit] = Field(default_factory=list)
    props: dict = Field(default_factory=dict)


_CATALOG: dict[str, ActionSpec] = {}


def register_action(spec: ActionSpec) -> None:
    _CATALOG[spec.key] = spec


def get_action(key: str) -> ActionSpec:
    if key not in _CATALOG:
        raise KeyError(f"Unknown action '{key}' — is the owning domain plugin registered?")
    return _CATALOG[key]


def actions_for_domain(domain: str) -> list[ActionSpec]:
    return sorted((a for a in _CATALOG.values() if a.domain == domain), key=lambda a: a.key)
