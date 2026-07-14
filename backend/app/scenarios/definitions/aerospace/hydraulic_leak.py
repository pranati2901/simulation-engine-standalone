"""Scenario: hydraulic leak -> flight delay -> gate congestion.

A competency-check scenario per the User Flow doc's Part A.3: one fault-injected
event, scored against whether the maintenance crew (readiness-modelled, not a live
player in v1) responds correctly and in time. Two objectives are wired to real,
computable conditions so changing the readiness/difficulty sliders in the UI visibly
changes whether the run certifies -- that's the point of exposing them.
"""
from __future__ import annotations

from ...factory import spawn, when
from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="aerospace.hydraulic_leak_v1",
    name="Hydraulic Leak - Cascading Delay",
    domain="aerospace",
    description="A hydraulic leak degrades pressure on N12345. The maintenance crew must "
                "diagnose and repair it before it cascades into a flight delay and gate congestion.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="hydraulic_leak", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="aircraft_hydraulic_system"),
                     label="Hydraulic pressure begins dropping on N12345"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Hydraulic Fault Response",
                     correct_action="Isolate the leaking line and switch to the redundant hydraulic path.",
                     risk_level="high",
                     description="Time-critical: an unresolved hydraulic fault risks an in-flight failure.",
                     consequence_of_delay="Fault remains unresolved into departure window.",
                     delay_s=300),
    ],
    objectives=[
        ScenarioObjective(text="Hydraulic fault correctly resolved by the maintenance crew",
                           role="maintenance", condition="containment_rate == 1"),
        ScenarioObjective(text="No fault-injection step was unexpectedly blocked by redundancy hardware",
                           role="maintenance", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="aerospace",
        actors=[
            ActorSpec(id="ac-1", type="aircraft_hydraulic_system", name="N12345 Hydraulic Sys"),
            ActorSpec(id="gate-b12", type="gate", name="Gate B12"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="redundant_hydraulic_line", targets=["ac-1"], scope="actor"),
            ResourceSpec(id="res-2", type="predictive_maintenance"),
        ],
    ),
    tags=["hydraulic", "maintenance", "delay-cascade"],
    # Dynamic Scenario Graph — see scenarios/definitions/aerospace/cascade.py.
    # An uncontained leak spawns the severe pump-failure branch; any leak delays the flight.
    triggers=[
        when("always", spawn("aerospace.flight_delay_cascade_v1", delay_min=25)),
        when("containment_rate < 1", spawn("aerospace.pump_failure_v1", delay_min=20)),
    ],
)

register_scenario(SCENARIO)
