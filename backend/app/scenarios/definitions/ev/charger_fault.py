"""Scenario: DC fast-charger fault -> load redistribution."""
from __future__ import annotations

from ...factory import spawn, when
from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="ev.charger_fault_v1",
    name="DC Fast-Charger Fault - Load Redistribution",
    domain="ev",
    description="A DC fast-charger trips offline mid-session. The grid operator must "
                "redistribute load and isolate the unit before the transformer overheats.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="charger_fault", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="dc_charger"),
                     label="DC charger DCFC-07 trips offline"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Charger Fault Response",
                     correct_action="Redistribute load across healthy chargers and isolate the faulted unit.",
                     risk_level="high",
                     description="Time-critical: unmanaged load spikes the substation transformer.",
                     consequence_of_delay="Load piles onto the remaining units and the transformer.",
                     delay_s=220),
    ],
    objectives=[
        ScenarioObjective(text="Charger fault correctly resolved by the grid operator",
                           role="grid_operator", condition="containment_rate == 1"),
        ScenarioObjective(text="No fault-injection step was unexpectedly blocked by the backup feed",
                           role="grid_operator", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="ev",
        actors=[
            ActorSpec(id="dcfc-7", type="dc_charger", name="DC Charger DCFC-07"),
            ActorSpec(id="txf-a", type="transformer", name="Transformer A"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="backup_feed", targets=["dcfc-7"], scope="actor"),
            ResourceSpec(id="res-2", type="thermal_monitoring"),
        ],
    ),
    tags=["ev", "grid", "charging"],
    # Dynamic Scenario Graph — see scenarios/definitions/ev/cascade.py.
    triggers=[
        when("always", spawn("ev.charging_session_dropouts_v1", delay_min=8)),
        when("always", spawn("ev.dc_load_imbalance_v1", delay_min=12)),
        when("containment_rate < 1", spawn("ev.thermal_runaway_v1", delay_min=20)),
    ],
)

register_scenario(SCENARIO)
