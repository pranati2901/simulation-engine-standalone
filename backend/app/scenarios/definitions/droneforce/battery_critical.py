"""Scenario: low battery in flight -> emergency landing protocol."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="droneforce.battery_critical_v1",
    name="Battery Critical - Emergency Landing",
    domain="droneforce",
    description="Drone DF-5 reports battery state-of-charge below 15% while 1.8 km "
                "from the nearest designated landing zone. The pilot must select an "
                "emergency landing site, initiate controlled descent, and notify "
                "local authorities of the unplanned landing.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="battery_critical_alarm", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="battery_system"),
                     label="Battery SoC drops below 15% critical threshold"),
        ScenarioStep(id="s2", action="landing_site_selection", phase="diagnose", at_min=1.0,
                     target=TargetSelector(by="type", value="drone_autopilot"),
                     label="Emergency landing site selected from terrain database"),
        ScenarioStep(id="s3", action="controlled_descent", phase="respond", at_min=3.0,
                     target=TargetSelector(by="type", value="drone_platform"),
                     label="Controlled descent initiated to emergency landing site"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Battery Critical Response",
                     correct_action="Select nearest safe landing site, initiate descent, notify airspace authority.",
                     risk_level="extreme",
                     description="Flight safety critical: total battery depletion causes uncontrolled crash.",
                     consequence_of_delay="Battery depletes in flight, drone crashes in uncontrolled area.",
                     delay_s=120),
    ],
    objectives=[
        ScenarioObjective(text="Emergency landing site selected and descent initiated",
                           role="drone_pilot", condition="containment_rate == 1"),
        ScenarioObjective(text="Drone landed safely without damage to persons or property",
                           role="drone_pilot", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="droneforce",
        actors=[
            ActorSpec(id="bat-5", type="battery_system", name="DF-5 Battery Pack"),
            ActorSpec(id="ap-5", type="drone_autopilot", name="DF-5 Autopilot"),
            ActorSpec(id="df-5", type="drone_platform", name="Drone Platform DF-5"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="terrain_database"),
            ResourceSpec(id="res-2", type="bms_telemetry", targets=["bat-5"], scope="actor"),
        ],
    ),
    tags=["battery", "emergency-landing", "flight-safety"],
)

register_scenario(SCENARIO)
