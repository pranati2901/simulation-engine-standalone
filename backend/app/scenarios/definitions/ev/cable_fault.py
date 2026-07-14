"""Scenario: charging cable fault -> earth fault detection, connector isolation."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="ev.cable_fault_v1",
    name="Charging Cable Fault - Earth Fault Detection",
    domain="ev",
    description="Residual current monitoring on charger DCFC-6 detects an earth fault "
                "indicating connector damage or insulation breakdown. The site technician "
                "must isolate the charger and inspect the cable assembly before clearing "
                "it for service.",
    node_kind="fault", category="equipment", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="earth_fault_detected", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="charging_cable"),
                     label="Earth fault detected on DCFC-6 cable assembly"),
        ScenarioStep(id="s2", action="charger_isolation", phase="respond", at_min=2.0,
                     target=TargetSelector(by="type", value="dc_fast_charger"),
                     label="Charger DCFC-6 isolated and locked out"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Cable Fault Response",
                     correct_action="Isolate charger, lock out connector, inspect cable for damage, test insulation resistance.",
                     risk_level="high",
                     description="Safety-critical: earth fault indicates potential electric shock hazard to users.",
                     consequence_of_delay="Continued use risks electric shock to next user connecting the cable.",
                     delay_s=120),
    ],
    objectives=[
        ScenarioObjective(text="Faulted charger isolated before next user connection attempt",
                           role="site_technician", condition="containment_rate == 1"),
        ScenarioObjective(text="Cable inspected and fault root-cause identified",
                           role="site_technician", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="ev",
        actors=[
            ActorSpec(id="cable-6", type="charging_cable", name="DCFC-6 Cable Assembly"),
            ActorSpec(id="dcfc-6", type="dc_fast_charger", name="DC Fast Charger DCFC-6"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="residual_current_monitor", targets=["cable-6"], scope="actor"),
            ResourceSpec(id="res-2", type="insulation_tester"),
        ],
    ),
    tags=["cable", "earth-fault", "electrical-safety"],
)

register_scenario(SCENARIO)
