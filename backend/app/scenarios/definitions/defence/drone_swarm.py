"""Scenario: UAS drone swarm detection -> C-UAS response, airspace denial."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="defence.drone_swarm_v1",
    name="Drone Swarm - C-UAS Response",
    domain="defence",
    description="Air defence radar detects a swarm of 12+ small UAS approaching the "
                "installation from the north. The air defence officer must classify "
                "the threat, activate counter-UAS systems (jamming and kinetic), and "
                "enforce airspace denial over the protected zone.",
    node_kind="fault", category="safety", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="swarm_detection", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="air_defence_radar"),
                     label="UAS swarm detected on air defence radar"),
        ScenarioStep(id="s2", action="threat_classification", phase="diagnose", at_min=2.0,
                     target=TargetSelector(by="type", value="ew_system"),
                     label="Swarm classified as hostile via RF signature analysis"),
        ScenarioStep(id="s3", action="cuas_engagement", phase="respond", at_min=4.0,
                     target=TargetSelector(by="type", value="cuas_system"),
                     label="C-UAS jamming and kinetic effectors engaged"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Drone Swarm Response",
                     correct_action="Classify threat, activate EW jamming, engage kinetic C-UAS, enforce airspace denial.",
                     risk_level="extreme",
                     description="Force protection critical: swarm can conduct ISR or deliver munitions.",
                     consequence_of_delay="Swarm penetrates defended airspace, compromising installation security.",
                     delay_s=120),
    ],
    objectives=[
        ScenarioObjective(text="C-UAS systems engaged before swarm reaches installation",
                           role="air_defence_officer", condition="containment_rate == 1"),
        ScenarioObjective(text="Airspace denial maintained over protected zone",
                           role="air_defence_officer", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="defence",
        actors=[
            ActorSpec(id="radar-1", type="air_defence_radar", name="Air Defence Radar"),
            ActorSpec(id="ew-1", type="ew_system", name="Electronic Warfare System"),
            ActorSpec(id="cuas-1", type="cuas_system", name="C-UAS Effector"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="rf_jammer", targets=["ew-1"], scope="actor"),
            ResourceSpec(id="res-2", type="air_picture_display"),
        ],
    ),
    tags=["drone", "swarm", "c-uas", "air-defence"],
)

register_scenario(SCENARIO)
