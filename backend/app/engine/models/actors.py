"""Actor type registry — domain plugins declare the kinds of actors that can exist in
their world (e.g. aerospace: "aircraft", "hydraulic_system", "ground_crew"; railway:
"signal_block", "train_unit", "platform").

Was GoalCert's engine/models/assets.py, generalized and made a plugin-populated
registry rather than a hardcoded cyber asset catalog.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..enums import ActorCategory


class ActorType(BaseModel):
    key: str
    name: str
    category: ActorCategory
    domain: str = "generic"
    default_criticality: int = 3
    default_sensitivity: int = 1
    default_props_: dict = Field(default_factory=dict, alias="default_props")

    def default_props(self) -> dict:
        return dict(self.default_props_)


_REGISTRY: dict[str, ActorType] = {}


def register_actor_type(at: ActorType) -> None:
    _REGISTRY[at.key] = at


def get_actor_type(key: str) -> ActorType | None:
    return _REGISTRY.get(key)


def actor_types_for_domain(domain: str) -> list[ActorType]:
    return sorted((a for a in _REGISTRY.values() if a.domain == domain), key=lambda a: a.key)
