"""Scenario: traction power failure -> degraded mode operation."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="railway.power_failure_v1",
    name="Traction Power Failure - Degraded Mode Operation",
    domain="railway",
    description="Traction substation TS-2 trips offline, cutting power to a section of "
                "track. The power controller must switch to backup feed and coordinate "
                "degraded-mode train operation until full restoration.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="substation_trip", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="traction_substation"),
                     label="Traction substation TS-2 trips offline"),
        ScenarioStep(id="s2", action="degraded_mode", phase="respond", at_min=10.0,
                     target=TargetSelector(by="type", value="train_unit"),
                     label="Trains switch to degraded-mode operation"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Power Failure Response",
                     correct_action="Switch to backup feeder, coordinate degraded-mode running, dispatch maintenance.",
                     risk_level="high",
                     description="Service-critical: stranded trains and signal failures cascade from power loss.",
                     consequence_of_delay="Trains stall on mainline, cascading delays across the network.",
                     delay_s=300),
    ],
    objectives=[
        ScenarioObjective(text="Backup feeder activated and degraded service established",
                           role="power_controller", condition="containment_rate == 1"),
        ScenarioObjective(text="No train stranded without power for more than 15 minutes",
                           role="power_controller", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="railway",
        actors=[
            ActorSpec(id="ts-2", type="traction_substation", name="Traction Substation TS-2"),
            ActorSpec(id="tu-3", type="train_unit", name="Train Unit 3"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="backup_feeder", targets=["ts-2"], scope="actor"),
            ResourceSpec(id="res-2", type="scada_monitoring"),
        ],
    ),
    tags=["power", "traction", "degraded-mode"],
)

register_scenario(SCENARIO)
