"""EnvironmentSpec — the operator/plugin-composed environment — and the World builder.

An EnvironmentSpec says which actors exist, their zones/criticality, and which
resources are enabled/where. build_world() instantiates it into a live World, applying
actor/resource type defaults from whichever domain plugin is active.

Generic replacement for GoalCert's engine/environment.py.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import ActorState, Health
from .world import ActorInstance, ResourceInstance, World


class BindingSpec(BaseModel):
    """Optional: maps a modeled actor to a real external system (a live PLC, a real
    VM, a real sensor feed) for live/hybrid simulation. Was GoalCert's VMBindingSpec.
    """
    endpoint: str
    protocol: str = "rest"            # "rest" | "opcua" | "mqtt" | "winrm" | "ssh" | ...
    credential_ref: str = ""          # key into a secrets store — never store secrets inline
    props: dict = Field(default_factory=dict)


class ActorSpec(BaseModel):
    id: str
    type: str                         # domain-plugin-registered ActorType key
    name: str | None = None
    role: str | None = None
    zone: str | None = None
    criticality: int | None = None
    sensitivity: int | None = None
    props: dict | None = None
    binding: BindingSpec | None = None


class ResourceSpec(BaseModel):
    id: str
    type: str
    name: str | None = None
    enabled: bool = True
    scope: str | None = None
    targets: list[str] | None = None
    props: dict | None = None


class EnvironmentSpec(BaseModel):
    domain: str = "generic"           # which plugin's actor/resource types this refers to
    actors: list[ActorSpec] = Field(default_factory=list)
    resources: list[ResourceSpec] = Field(default_factory=list)

    def actor_types(self) -> set[str]:
        return {a.type for a in self.actors}


def _build_actor(spec: ActorSpec, get_actor_type) -> ActorInstance:
    at = get_actor_type(spec.type)
    props = dict(at.default_props()) if at else {}
    if spec.props:
        props.update(spec.props)
    return ActorInstance(
        id=spec.id,
        type_key=spec.type,
        name=spec.name or (at.name if at else spec.type),
        role=spec.role,
        zone=spec.zone or "default",
        criticality=spec.criticality if spec.criticality is not None else (at.default_criticality if at else 3),
        sensitivity=spec.sensitivity if spec.sensitivity is not None else (at.default_sensitivity if at else 1),
        state=ActorState.NOMINAL,
        health=Health.NOMINAL,
        props=props,
    )


def _build_resource(spec: ResourceSpec, get_resource_type) -> ResourceInstance:
    rt = get_resource_type(spec.type)
    props = dict(rt.default_props()) if rt else {}
    if spec.props:
        props.update(spec.props)
    return ResourceInstance(
        id=spec.id,
        type_key=spec.type,
        name=spec.name or (rt.name if rt else spec.type),
        enabled=spec.enabled,
        scope=spec.scope or (rt.default_scope if rt else "global"),
        targets=spec.targets or [],
        props=props,
    )


def build_world(env: EnvironmentSpec, get_actor_type, get_resource_type) -> World:
    """Instantiate an EnvironmentSpec into a live World.

    get_actor_type / get_resource_type are plugin registry lookups
    (see plugins/registry.py) so this function never hardcodes a domain.
    """
    world = World()
    for a_spec in env.actors:
        actor = _build_actor(a_spec, get_actor_type)
        world.actors[actor.id] = actor
    for r_spec in env.resources:
        resource = _build_resource(r_spec, get_resource_type)
        world.resources[resource.id] = resource
    return world
