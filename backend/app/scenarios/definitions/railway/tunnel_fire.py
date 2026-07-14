"""Scenario: tunnel fire -> smoke detection, ventilation response, evacuation."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="railway.tunnel_fire_v1",
    name="Tunnel Fire - Smoke Detection and Evacuation",
    domain="railway",
    description="Smoke is detected in tunnel section T-4. The OCC must activate tunnel "
                "ventilation fans, halt approaching trains, and initiate passenger "
                "evacuation before smoke density becomes life-threatening.",
    node_kind="fault", category="safety", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="smoke_detection", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="tunnel_section"),
                     label="Smoke detected in tunnel section T-4"),
        ScenarioStep(id="s2", action="ventilation_activation", phase="diagnose", at_min=2.0,
                     target=TargetSelector(by="type", value="tunnel_ventilation"),
                     label="Tunnel ventilation fans activated"),
        ScenarioStep(id="s3", action="passenger_evacuation", phase="respond", at_min=5.0,
                     target=TargetSelector(by="type", value="train_unit"),
                     label="Passenger evacuation from tunnel initiated"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Tunnel Fire Response",
                     correct_action="Activate ventilation, halt all tunnel traffic, dispatch SCDF, begin evacuation.",
                     risk_level="extreme",
                     description="Life-safety critical: smoke in confined tunnel space is immediately dangerous.",
                     consequence_of_delay="Smoke density rises to untenable levels for trapped passengers.",
                     delay_s=120),
    ],
    objectives=[
        ScenarioObjective(text="Ventilation activated within 2 minutes of smoke detection",
                           role="occ_controller", condition="containment_rate == 1"),
        ScenarioObjective(text="All trains halted before entering affected tunnel section",
                           role="occ_controller", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="railway",
        actors=[
            ActorSpec(id="tun-4", type="tunnel_section", name="Tunnel Section T-4"),
            ActorSpec(id="vent-4", type="tunnel_ventilation", name="Tunnel Ventilation T-4"),
            ActorSpec(id="tu-8", type="train_unit", name="Train Unit 8"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="fire_suppression", targets=["tun-4"], scope="actor"),
            ResourceSpec(id="res-2", type="smoke_detection_system"),
            ResourceSpec(id="res-3", type="emergency_lighting", targets=["tun-4"], scope="actor"),
        ],
    ),
    tags=["fire", "evacuation", "life-safety", "tunnel"],
)

register_scenario(SCENARIO)
