"""Scenario: DC fast charger fault -> load redistribution across charging network."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="ev.charger_malfunction_v1",
    name="DC Fast Charger Fault - Load Redistribution",
    domain="ev",
    description="DC fast charger DCFC-4 reports a ground fault and shuts down mid-session. "
                "The network operator must isolate the fault, redirect queued vehicles to "
                "adjacent chargers, and rebalance load across the site.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="charger_ground_fault", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="dc_fast_charger"),
                     label="DC fast charger DCFC-4 reports ground fault"),
        ScenarioStep(id="s2", action="load_redistribution", phase="respond", at_min=5.0,
                     target=TargetSelector(by="type", value="charging_network"),
                     label="Charging load redistributed to adjacent units"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Charger Fault Response",
                     correct_action="Isolate faulted charger, redirect vehicles, redistribute load to remaining units.",
                     risk_level="high",
                     description="Safety-critical: ground fault may indicate insulation breakdown or cable damage.",
                     consequence_of_delay="Queued vehicles back up, remaining chargers risk thermal overload.",
                     delay_s=300),
    ],
    objectives=[
        ScenarioObjective(text="Faulted charger isolated and load redistributed",
                           role="network_operator", condition="containment_rate == 1"),
        ScenarioObjective(text="No secondary charger trips from overload",
                           role="network_operator", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="ev",
        actors=[
            ActorSpec(id="dcfc-4", type="dc_fast_charger", name="DC Fast Charger DCFC-4"),
            ActorSpec(id="net-1", type="charging_network", name="Site Charging Network"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="ground_fault_interrupter", targets=["dcfc-4"], scope="actor"),
            ResourceSpec(id="res-2", type="load_management_system"),
        ],
    ),
    tags=["charger", "ground-fault", "load-balancing"],
)

register_scenario(SCENARIO)
