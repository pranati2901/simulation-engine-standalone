"""Scenario: geofence breach -> forced landing sequence."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="droneforce.airspace_violation_v1",
    name="Airspace Violation - Forced Landing Sequence",
    domain="droneforce",
    description="Drone DF-7 breaches the programmed geofence boundary and enters "
                "restricted airspace near an airport CTR. The pilot must immediately "
                "halt forward flight, initiate forced landing, and coordinate with "
                "air traffic control to deconflict manned aircraft.",
    node_kind="fault", category="operational", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="geofence_breach", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="geofence_boundary"),
                     label="Drone DF-7 breaches geofence into restricted airspace"),
        ScenarioStep(id="s2", action="flight_halt", phase="diagnose", at_min=0.5,
                     target=TargetSelector(by="type", value="drone_autopilot"),
                     label="Forward flight halted, drone enters hover"),
        ScenarioStep(id="s3", action="forced_landing", phase="respond", at_min=2.0,
                     target=TargetSelector(by="type", value="drone_platform"),
                     label="Forced landing sequence initiated"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Airspace Violation Response",
                     correct_action="Halt flight, initiate forced landing, contact ATC, log violation for CAAS.",
                     risk_level="extreme",
                     description="Aviation safety critical: drone in CTR risks collision with manned aircraft.",
                     consequence_of_delay="Near-miss or collision with manned aircraft in controlled airspace.",
                     delay_s=30),
    ],
    objectives=[
        ScenarioObjective(text="Drone flight halted and forced landing initiated immediately",
                           role="drone_pilot", condition="containment_rate == 1"),
        ScenarioObjective(text="ATC notified and no conflict with manned traffic",
                           role="drone_pilot", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="droneforce",
        actors=[
            ActorSpec(id="gf-1", type="geofence_boundary", name="Airport CTR Geofence"),
            ActorSpec(id="ap-7", type="drone_autopilot", name="DF-7 Autopilot"),
            ActorSpec(id="df-7", type="drone_platform", name="Drone Platform DF-7"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="geofence_monitor"),
            ResourceSpec(id="res-2", type="ads_b_transponder"),
        ],
    ),
    tags=["geofence", "airspace", "forced-landing", "aviation-safety"],
)

register_scenario(SCENARIO)
