"""Scenario: track intrusion -> emergency braking, service suspension."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="railway.track_intrusion_v1",
    name="Track Intrusion - Emergency Braking",
    domain="railway",
    description="A person is detected on the track between stations. The OCC must "
                "trigger emergency braking on approaching trains and suspend service "
                "on the affected section until the track is cleared.",
    node_kind="fault", category="human", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="track_intrusion_detected", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="track_section"),
                     label="Person detected on track via CCTV / track circuit"),
        ScenarioStep(id="s2", action="emergency_braking", phase="respond", at_min=1.0,
                     target=TargetSelector(by="type", value="train_unit"),
                     label="Emergency braking applied to approaching train"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Track Intrusion Response",
                     correct_action="Trigger emergency stop, suspend service on affected section, dispatch ground team.",
                     risk_level="extreme",
                     description="Life-safety critical: person on track with approaching train.",
                     consequence_of_delay="Potential fatality if train is not stopped in time.",
                     delay_s=60),
    ],
    objectives=[
        ScenarioObjective(text="Emergency braking applied before train reaches intrusion point",
                           role="occ_controller", condition="containment_rate == 1"),
        ScenarioObjective(text="Track cleared and service resumed safely",
                           role="occ_controller", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="railway",
        actors=[
            ActorSpec(id="trk-7", type="track_section", name="Track Section 7"),
            ActorSpec(id="tu-5", type="train_unit", name="Train Unit 5"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="track_intrusion_detection", targets=["trk-7"], scope="actor"),
            ResourceSpec(id="res-2", type="cctv_monitoring"),
        ],
    ),
    tags=["intrusion", "emergency-braking", "life-safety"],
)

register_scenario(SCENARIO)
