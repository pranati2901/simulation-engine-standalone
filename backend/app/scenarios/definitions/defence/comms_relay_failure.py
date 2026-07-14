"""Scenario: comms relay failure -> forward post coordination delay."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="defence.comms_relay_failure_v1",
    name="Comms Relay Failure - Coordination Delay",
    domain="defence",
    description="Comms relay CR-7 reports signal loss. The signals operator must restore "
                "the link before forward post coordination is compromised.",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="comms_relay_failure", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="comms_relay"),
                     label="Comms Relay CR-7 reports signal loss"),
        ScenarioStep(id="s2", action="coordination_delay", phase="respond", at_min=15.0,
                     target=TargetSelector(by="type", value="forward_post"),
                     label="Forward post coordination delayed"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Comms Fault Response",
                     correct_action="Run diagnostics, activate backup comms link.",
                     risk_level="extreme",
                     description="Mission-critical: unresolved comms loss isolates the forward post.",
                     consequence_of_delay="Forward post loses coordination with command.",
                     delay_s=150),
    ],
    objectives=[
        ScenarioObjective(text="Comms fault correctly resolved by the signals operator",
                           role="signals_operator", condition="containment_rate == 1"),
        ScenarioObjective(text="No fault-injection step was unexpectedly blocked by backup link",
                           role="signals_operator", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="defence",
        actors=[
            ActorSpec(id="cr-7", type="comms_relay", name="Comms Relay CR-7"),
            ActorSpec(id="fp-3", type="forward_post", name="Forward Post 3"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="backup_comms_link", targets=["cr-7"], scope="actor"),
            ResourceSpec(id="res-2", type="signal_monitoring"),
        ],
    ),
    tags=["comms", "mission-critical"],
)

register_scenario(SCENARIO)
