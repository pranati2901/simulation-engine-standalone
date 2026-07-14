"""Scenario: platform screen door malfunction -> train hold at station."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="railway.door_malfunction_v1",
    name="Platform Screen Door Malfunction - Train Hold",
    domain="railway",
    description="Platform screen door PSD-3 is stuck open/closed, preventing safe "
                "boarding. The station controller must isolate the faulty door and "
                "coordinate train hold before service backs up.",
    node_kind="fault", category="equipment", impact_level="medium",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="door_malfunction", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="platform_screen_door"),
                     label="Platform screen door PSD-3 stuck open"),
        ScenarioStep(id="s2", action="train_hold", phase="respond", at_min=5.0,
                     target=TargetSelector(by="type", value="train_unit"),
                     label="Train held at platform pending door resolution"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Door Fault Response",
                     correct_action="Isolate faulty PSD, switch to manual boarding mode, notify OCC.",
                     risk_level="high",
                     description="Safety-critical: open PSD creates fall-to-track risk during boarding.",
                     consequence_of_delay="Train dwell time extends, upstream services queue.",
                     delay_s=180),
    ],
    objectives=[
        ScenarioObjective(text="Door fault correctly isolated by the station controller",
                           role="station_controller", condition="containment_rate == 1"),
        ScenarioObjective(text="No passenger safety incident during manual boarding",
                           role="station_controller", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="railway",
        actors=[
            ActorSpec(id="psd-3", type="platform_screen_door", name="Platform Screen Door PSD-3"),
            ActorSpec(id="tu-12", type="train_unit", name="Train Unit 12"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="manual_door_override", targets=["psd-3"], scope="actor"),
            ResourceSpec(id="res-2", type="cctv_monitoring"),
        ],
    ),
    tags=["door", "platform-safety", "service-disruption"],
)

register_scenario(SCENARIO)
