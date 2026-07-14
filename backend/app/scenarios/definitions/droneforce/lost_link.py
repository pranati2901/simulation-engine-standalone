"""Scenario: communication loss -> return-to-home protocol."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="droneforce.lost_link_v1",
    name="Lost Link - Return-to-Home Protocol",
    domain="droneforce",
    description="Drone DF-3 loses its C2 datalink while operating 2.5 km from the "
                "ground control station. The pilot must verify loss-of-link, confirm "
                "the autopilot engages the return-to-home (RTH) protocol, and prepare "
                "for manual takeover once the link is re-established.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="datalink_loss", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="c2_datalink"),
                     label="C2 datalink lost on drone DF-3"),
        ScenarioStep(id="s2", action="rth_activation", phase="diagnose", at_min=1.0,
                     target=TargetSelector(by="type", value="drone_autopilot"),
                     label="Autopilot engages return-to-home protocol"),
        ScenarioStep(id="s3", action="link_reestablishment", phase="respond", at_min=5.0,
                     target=TargetSelector(by="type", value="ground_control_station"),
                     label="C2 link re-established, manual control resumed"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Lost Link Response",
                     correct_action="Verify loss-of-link, confirm RTH engagement, notify airspace authority, prepare manual takeover.",
                     risk_level="high",
                     description="Flight safety critical: uncontrolled drone in shared airspace is a collision risk.",
                     consequence_of_delay="Drone continues on last heading into restricted or populated airspace.",
                     delay_s=60),
    ],
    objectives=[
        ScenarioObjective(text="RTH protocol engaged within 60 seconds of link loss",
                           role="drone_pilot", condition="containment_rate == 1"),
        ScenarioObjective(text="Drone returned safely to home point without airspace violation",
                           role="drone_pilot", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="droneforce",
        actors=[
            ActorSpec(id="link-3", type="c2_datalink", name="C2 Datalink DF-3"),
            ActorSpec(id="ap-3", type="drone_autopilot", name="DF-3 Autopilot"),
            ActorSpec(id="gcs-1", type="ground_control_station", name="Ground Control Station"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="backup_frequency", targets=["link-3"], scope="actor"),
            ResourceSpec(id="res-2", type="ads_b_transponder"),
        ],
    ),
    tags=["lost-link", "rth", "flight-safety"],
)

register_scenario(SCENARIO)
