"""Scenario: grid transformer thermal limit -> load shedding sequence."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="ev.grid_overload_v1",
    name="Grid Overload - Transformer Load Shedding",
    domain="ev",
    description="The site distribution transformer TX-1 approaches thermal limit due to "
                "sustained high charging load. The grid operator must initiate load "
                "shedding to prevent transformer trip and site-wide blackout.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="transformer_thermal_alarm", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="distribution_transformer"),
                     label="Transformer TX-1 winding temperature exceeds 85%% rated limit"),
        ScenarioStep(id="s2", action="load_shedding", phase="respond", at_min=10.0,
                     target=TargetSelector(by="type", value="charging_network"),
                     label="Non-critical chargers curtailed to reduce transformer load"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Grid Overload Response",
                     correct_action="Curtail low-priority sessions, reduce max power on active chargers, monitor TX temp.",
                     risk_level="high",
                     description="Infrastructure-critical: transformer trip blacks out entire charging site.",
                     consequence_of_delay="Transformer protection relay trips, causing site-wide power loss.",
                     delay_s=600),
    ],
    objectives=[
        ScenarioObjective(text="Transformer load reduced below thermal limit without full trip",
                           role="grid_operator", condition="containment_rate == 1"),
        ScenarioObjective(text="Active high-priority sessions maintained through shedding",
                           role="grid_operator", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="ev",
        actors=[
            ActorSpec(id="tx-1", type="distribution_transformer", name="Transformer TX-1"),
            ActorSpec(id="net-1", type="charging_network", name="Site Charging Network"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="transformer_monitoring", targets=["tx-1"], scope="actor"),
            ResourceSpec(id="res-2", type="load_management_system"),
        ],
    ),
    tags=["grid", "transformer", "load-shedding"],
)

register_scenario(SCENARIO)
