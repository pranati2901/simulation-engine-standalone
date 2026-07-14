"""Scenario: signal block failure -> platform overcrowding."""
from __future__ import annotations

from ...factory import spawn, when
from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="railway.signal_failure_v1",
    name="Signal Block Failure - Platform Overcrowding",
    domain="railway",
    description="A signal block enters fail-safe state, halting a train unit. The signal "
                "technician must restore it before platform crowding builds.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="signal_failure", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="signal_block"),
                     label="Signal block SB-14 enters fail-safe state"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Signal Fault Response",
                     correct_action="Dispatch technician, reset relay, confirm fail-safe clear.",
                     risk_level="high",
                     description="Time-critical: unresolved signal fault halts service on the line.",
                     consequence_of_delay="Service disruption extends into peak hours.",
                     delay_s=240),
    ],
    objectives=[
        ScenarioObjective(text="Signal fault correctly resolved by the technician",
                           role="signal_technician", condition="containment_rate == 1"),
        ScenarioObjective(text="No fault-injection step was unexpectedly blocked by backup relay",
                           role="signal_technician", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="railway",
        actors=[
            ActorSpec(id="sb-14", type="signal_block", name="Signal Block SB-14"),
            ActorSpec(id="plat-2", type="platform", name="Platform 2"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="backup_signal_relay", targets=["sb-14"], scope="actor"),
            ResourceSpec(id="res-2", type="cctv_monitoring"),
        ],
    ),
    tags=["signal", "service-disruption"],
    triggers=[
        when("always", spawn("railway.platform_overcrowding_cascade_v1", delay_min=20)),
        when("containment_rate < 1", spawn("railway.service_suspension_v1", delay_min=30)),
    ],
)

register_scenario(SCENARIO)
