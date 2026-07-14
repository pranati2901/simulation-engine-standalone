"""Mutable world state: actor & resource instances plus the primary driver's progress.

The World is the live environment a run mutates. It is built from an EnvironmentSpec and
carried through the engine. All query helpers should stay deterministic (sorted where
order matters) so replay/rollback/fork stay possible later.

Generic replacement for GoalCert's engine/world.py (AssetInstance/ControlInstance/
AttackerState -> ActorInstance/ResourceInstance/DriverState).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .enums import ActorState, AuthorityScope, Health


class ActorInstance(BaseModel):
    """A thing in the world that can be affected: equipment, a person, a facility,
    a network node, a control system, etc. Was GoalCert's AssetInstance.
    """
    id: str
    type_key: str                     # references a domain-plugin-registered ActorType
    name: str
    role: str | None = None           # selector tag used by scenario steps (e.g. "primary_unit")
    zone: str = "default"             # spatial/logical grouping (network segment, ward, block)
    criticality: int = 3              # 1..5
    state: ActorState = ActorState.NOMINAL
    health: Health = Health.NOMINAL
    sensitivity: int = 1              # 1..5 — relevance for impact/consequence scoring
    props: dict[str, Any] = Field(default_factory=dict)

    @property
    def affected(self) -> bool:
        return self.state in (ActorState.AT_RISK, ActorState.DEGRADED, ActorState.FAILED)


class ResourceInstance(BaseModel):
    """A control, safeguard, or capability that can prevent/mitigate/detect an effect
    on an actor. Was GoalCert's ControlInstance (e.g. firewall, EDR -> now generic:
    redundancy system, safety interlock, maintenance crew, backup generator...).
    """
    id: str
    type_key: str
    name: str
    enabled: bool = True
    scope: str = "global"             # "global" | "zone" | "actor"
    targets: list[str] = Field(default_factory=list)  # actor ids (actor scope) / zones
    props: dict[str, Any] = Field(default_factory=dict)
    disabled_by_driver: bool = False  # was disabled_by_attacker

    @property
    def active(self) -> bool:
        return self.enabled and not self.disabled_by_driver

    def covers(self, actor: ActorInstance) -> bool:
        if self.scope == "global":
            return True
        if self.scope == "zone":
            return actor.zone in self.targets
        return actor.id in self.targets


class DriverState(BaseModel):
    """Progress of the primary driving force behind the scenario (an attacker, a
    failure cascade, an external event) through the world. Was GoalCert's
    AttackerState. Kept generic so 'foothold' works for both 'compromised host' and
    'affected subsystem'.
    """
    footholds: list[str] = Field(default_factory=list)   # actor ids under driver influence
    authority: AuthorityScope = AuthorityScope.NONE
    disabled_resource_types: list[str] = Field(default_factory=list)
    flags: dict[str, bool] = Field(default_factory=dict)  # domain-specific progress flags

    def has_foothold(self) -> bool:
        return len(self.footholds) > 0


class World(BaseModel):
    """The live, mutable simulation state for a single run."""
    actors: dict[str, ActorInstance] = Field(default_factory=dict)
    resources: dict[str, ResourceInstance] = Field(default_factory=dict)
    driver: DriverState = Field(default_factory=DriverState)

    def actor(self, actor_id: str) -> ActorInstance | None:
        return self.actors.get(actor_id)

    def actors_by_role(self, role: str) -> list[ActorInstance]:
        return sorted((a for a in self.actors.values() if a.role == role), key=lambda a: a.id)

    def actors_by_type(self, type_key: str) -> list[ActorInstance]:
        return sorted((a for a in self.actors.values() if a.type_key == type_key), key=lambda a: a.id)

    def foothold_zones(self) -> set[str]:
        return {self.actors[aid].zone for aid in self.driver.footholds if aid in self.actors}

    def resources_covering(self, actor: ActorInstance) -> list[ResourceInstance]:
        return [r for r in self.resources.values() if r.active and r.covers(actor)]
