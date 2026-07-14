"""Resource type registry — domain plugins declare the kinds of safeguards/controls/
capabilities that can exist in their world (e.g. redundant systems, safety interlocks,
backup crews, maintenance windows).

Was GoalCert's engine/models/controls.py, generalized the same way as actors.py.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ResourceType(BaseModel):
    key: str
    name: str
    domain: str = "generic"
    default_scope: str = "global"
    default_props_: dict = Field(default_factory=dict, alias="default_props")

    def default_props(self) -> dict:
        return dict(self.default_props_)


_REGISTRY: dict[str, ResourceType] = {}


def register_resource_type(rt: ResourceType) -> None:
    _REGISTRY[rt.key] = rt


def get_resource_type(key: str) -> ResourceType | None:
    return _REGISTRY.get(key)


def resource_types_for_domain(domain: str) -> list[ResourceType]:
    return sorted((r for r in _REGISTRY.values() if r.domain == domain), key=lambda r: r.key)
