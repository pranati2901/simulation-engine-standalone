"""Scenario: battery thermal runaway -> cell isolation, fire suppression."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="ev.battery_thermal_runaway_v1",
    name="Battery Thermal Runaway - Cell Isolation",
    domain="ev",
    description="Battery management system detects cell over-temperature in a vehicle "
                "connected to charger bay CB-2. The site operator must disconnect the "
                "vehicle, activate fire suppression, and evacuate the charging area.",
    node_kind="fault", category="safety", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="cell_overtemp_alarm", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="charger_bay"),
                     label="BMS reports cell over-temperature at charger bay CB-2"),
        ScenarioStep(id="s2", action="emergency_disconnect", phase="diagnose", at_min=1.0,
                     target=TargetSelector(by="type", value="dc_fast_charger"),
                     label="Emergency disconnect initiated"),
        ScenarioStep(id="s3", action="fire_suppression", phase="respond", at_min=3.0,
                     target=TargetSelector(by="type", value="suppression_system"),
                     label="Fire suppression system activated over charger bay"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Thermal Runaway Response",
                     correct_action="Emergency disconnect, activate suppression, evacuate area, call SCDF.",
                     risk_level="extreme",
                     description="Life-safety critical: thermal runaway can escalate to fire and toxic gas within minutes.",
                     consequence_of_delay="Cell-to-cell propagation leads to full battery fire with toxic HF gas release.",
                     delay_s=90),
    ],
    objectives=[
        ScenarioObjective(text="Vehicle disconnected and suppression activated before fire propagation",
                           role="site_operator", condition="containment_rate == 1"),
        ScenarioObjective(text="Area evacuated with no personnel exposure to toxic gas",
                           role="site_operator", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="ev",
        actors=[
            ActorSpec(id="cb-2", type="charger_bay", name="Charger Bay CB-2"),
            ActorSpec(id="dcfc-2", type="dc_fast_charger", name="DC Fast Charger 2"),
            ActorSpec(id="supp-1", type="suppression_system", name="Fire Suppression System"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="bms_telemetry", targets=["cb-2"], scope="actor"),
            ResourceSpec(id="res-2", type="thermal_camera"),
        ],
    ),
    tags=["battery", "thermal-runaway", "fire", "life-safety"],
)

register_scenario(SCENARIO)
