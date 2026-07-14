"""Authoring helpers for cascade scenario graphs.

Child scenarios in a cascade come in two shapes, and hand-writing each as a full
Scenario (env + steps + gates + objectives) is 40+ lines of boilerplate. These two
factories capture the two shapes so a domain's cascade reads as a list of nodes:

* fault_node       — a scored competency check: one fault injected on one asset, one
                     decision gate. Certifies iff operator readiness clears the gate;
                     its `containment_rate` is what downstream triggers branch on.
* consequence_node — a downstream impact that simply *occurs* and is logged (flight
                     delayed, gate congested, financial loss). Not scored/certified;
                     rendered as a severity-coloured consequence in the graph.

NOT auto-imported as a scenario module (it lives outside scenarios/definitions/), so
the loader's package walk never treats it as a definition.
"""
from __future__ import annotations

from ..engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ..engine.scenario import (
    CascadeSpawn, DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector, Trigger,
)


def spawn(scenario_id: str, *, delay_min: float = 0.0, probability: float = 1.0,
          condition: str | None = None) -> CascadeSpawn:
    return CascadeSpawn(scenario_id=scenario_id, delay_min=delay_min,
                        probability=probability, condition=condition)


def when(condition: str, *spawns: CascadeSpawn, kind: str = "state") -> Trigger:
    """A trigger: when `condition` holds on this node's result, fire every `spawn`.
    Use condition='always' for an inherent consequence, or a comparison like
    'containment_rate < 1' for a consequence that only happens when the fault wasn't
    contained (i.e. a *preventable* one)."""
    return Trigger(kind=kind, condition=condition, spawns=list(spawns))


def fault_node(
    *, id: str, name: str, domain: str, action: str, actor_type: str, actor_id: str,
    actor_name: str, gate_name: str, correct_action: str, description: str = "",
    risk: str = "high", category: str = "equipment", impact: str = "high",
    tags: list[str] | None = None, prevention_resource: str | None = None,
    monitor_resource: str | None = None, consequence_of_delay: str = "",
    triggers: list[Trigger] | None = None,
) -> Scenario:
    resources: list[ResourceSpec] = []
    if prevention_resource:
        resources.append(ResourceSpec(id=f"{id}-prev", type=prevention_resource,
                                      targets=[actor_id], scope="actor"))
    if monitor_resource:
        resources.append(ResourceSpec(id=f"{id}-mon", type=monitor_resource, scope="global"))
    return Scenario(
        id=id, name=name, domain=domain, description=description,
        node_kind="fault", category=category, impact_level=impact,
        phases=["detect", "respond"],
        steps=[ScenarioStep(id="s1", action=action, phase="respond", at_min=0.0,
                            target=TargetSelector(by="type", value=actor_type), label=name)],
        decision_gates=[DecisionGate(id="g1", trigger="s1", name=gate_name,
                                     correct_action=correct_action, risk_level=risk,
                                     consequence_of_delay=consequence_of_delay)],
        objectives=[ScenarioObjective(text=f"{name} correctly contained",
                                      condition="containment_rate == 1")],
        recommended_environment=EnvironmentSpec(
            domain=domain,
            actors=[ActorSpec(id=actor_id, type=actor_type, name=actor_name)],
            resources=resources,
        ),
        tags=tags or [],
        triggers=triggers or [],
    )


def consequence_node(
    *, id: str, name: str, domain: str, action: str, description: str = "",
    category: str = "operational", impact: str = "medium", tags: list[str] | None = None,
    target_type: str | None = None, target_id: str | None = None, target_name: str | None = None,
    triggers: list[Trigger] | None = None,
) -> Scenario:
    target = TargetSelector(by="type", value=target_type) if target_type else None
    actors = ([ActorSpec(id=target_id or f"{id}-a", type=target_type, name=target_name or name)]
              if target_type else [])
    return Scenario(
        id=id, name=name, domain=domain, description=description,
        node_kind="consequence", category=category, impact_level=impact,
        phases=["impact"],
        steps=[ScenarioStep(id="s1", action=action, phase="impact", at_min=0.0,
                            target=target, label=name)],
        objectives=[ScenarioObjective(text=f"{name} occurred and was attributed to the cascade",
                                      condition="successes >= 1")],
        recommended_environment=EnvironmentSpec(domain=domain, actors=actors),
        tags=tags or [],
        triggers=triggers or [],
    )
