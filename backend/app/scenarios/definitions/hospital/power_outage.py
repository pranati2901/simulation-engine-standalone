"""Scenario: mains power failure -> generator start, UPS bridge."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="hospital.power_outage_v1",
    name="Power Outage - Generator Start and UPS Bridge",
    domain="hospital",
    description="Mains power supply fails across the hospital campus. UPS systems "
                "provide bridge power to critical loads while the backup diesel "
                "generator starts. The facilities engineer must verify generator "
                "pickup, confirm life-safety loads are energised, and manage non-critical "
                "load shedding.",
    node_kind="fault", category="equipment", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="mains_failure", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="main_switchboard"),
                     label="Mains power loss detected at main switchboard"),
        ScenarioStep(id="s2", action="ups_bridge", phase="diagnose", at_min=0.5,
                     target=TargetSelector(by="type", value="ups_system"),
                     label="UPS systems bridging critical loads"),
        ScenarioStep(id="s3", action="generator_start", phase="respond", at_min=2.0,
                     target=TargetSelector(by="type", value="diesel_generator"),
                     label="Backup diesel generator started and on load"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Power Outage Response",
                     correct_action="Verify UPS bridging, confirm generator auto-start, validate life-safety loads, shed non-critical.",
                     risk_level="extreme",
                     description="Life-safety critical: ventilators, monitors, and OR lights depend on uninterrupted power.",
                     consequence_of_delay="UPS battery exhaustion before generator pickup causes life-support interruption.",
                     delay_s=120),
    ],
    objectives=[
        ScenarioObjective(text="Generator on load before UPS battery exhaustion",
                           role="facilities_engineer", condition="containment_rate == 1"),
        ScenarioObjective(text="All life-safety loads maintained without interruption",
                           role="facilities_engineer", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="hospital",
        actors=[
            ActorSpec(id="msb-1", type="main_switchboard", name="Main Switchboard"),
            ActorSpec(id="ups-1", type="ups_system", name="UPS System 1"),
            ActorSpec(id="gen-1", type="diesel_generator", name="Backup Generator 1"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="power_monitoring", targets=["msb-1"], scope="actor"),
            ResourceSpec(id="res-2", type="fuel_reserve", targets=["gen-1"], scope="actor"),
        ],
    ),
    tags=["power", "generator", "ups", "life-safety"],
)

register_scenario(SCENARIO)
