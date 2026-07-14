"""Scenario: torpedo attack -> countermeasure deployment, damage control."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="defence.torpedo_attack_v1",
    name="Torpedo Attack - Countermeasure Deployment",
    domain="defence",
    description="Sonar detects an incoming torpedo bearing 045. The warfare officer "
                "must deploy countermeasures (decoys and noisemakers), execute evasive "
                "manoeuvres, and prepare damage control parties in case of impact.",
    node_kind="fault", category="equipment", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="torpedo_detection", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="sonar_system"),
                     label="Incoming torpedo detected on sonar bearing 045"),
        ScenarioStep(id="s2", action="countermeasure_deployment", phase="diagnose", at_min=1.0,
                     target=TargetSelector(by="type", value="countermeasure_launcher"),
                     label="Decoys and noisemakers deployed"),
        ScenarioStep(id="s3", action="damage_control_standby", phase="respond", at_min=3.0,
                     target=TargetSelector(by="type", value="damage_control_party"),
                     label="Damage control parties at action stations"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Torpedo Attack Response",
                     correct_action="Deploy countermeasures, execute evasive turn, set condition Zulu, prepare DC parties.",
                     risk_level="extreme",
                     description="Ship survival critical: torpedo impact can cause catastrophic hull breach.",
                     consequence_of_delay="Countermeasures deployed too late to seduce torpedo away from ship.",
                     delay_s=60),
    ],
    objectives=[
        ScenarioObjective(text="Countermeasures deployed and evasive action taken",
                           role="warfare_officer", condition="containment_rate == 1"),
        ScenarioObjective(text="Damage control parties ready at action stations",
                           role="warfare_officer", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="defence",
        actors=[
            ActorSpec(id="sonar-1", type="sonar_system", name="Hull-Mounted Sonar"),
            ActorSpec(id="cm-1", type="countermeasure_launcher", name="Countermeasure Launcher"),
            ActorSpec(id="dc-1", type="damage_control_party", name="DC Party 1"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="torpedo_decoy", targets=["cm-1"], scope="actor"),
            ResourceSpec(id="res-2", type="combat_management_system"),
        ],
    ),
    tags=["torpedo", "naval", "countermeasure", "damage-control"],
)

register_scenario(SCENARIO)
