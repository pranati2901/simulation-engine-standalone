"""Scenario: medical gas pipeline rupture -> zone isolation, manual supply."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="hospital.medical_gas_leak_v1",
    name="Medical Gas Leak - Zone Isolation",
    domain="hospital",
    description="An oxygen pipeline rupture is detected in Ward C corridor. The "
                "facilities engineer must isolate the affected zone valve, switch "
                "ventilator-dependent patients to portable cylinder supply, and "
                "coordinate pipeline repair.",
    node_kind="fault", category="equipment", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="gas_leak_alarm", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="gas_pipeline"),
                     label="O2 pipeline pressure drop alarm in Ward C"),
        ScenarioStep(id="s2", action="zone_valve_isolation", phase="diagnose", at_min=3.0,
                     target=TargetSelector(by="type", value="gas_zone_valve"),
                     label="Zone valve isolated to contain the leak"),
        ScenarioStep(id="s3", action="manual_cylinder_supply", phase="respond", at_min=5.0,
                     target=TargetSelector(by="type", value="oxygen_cylinder"),
                     label="Patients switched to portable O2 cylinders"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Gas Leak Response",
                     correct_action="Isolate zone valve, switch patients to portable O2, ventilate corridor, dispatch repair.",
                     risk_level="extreme",
                     description="Life-safety critical: ventilator-dependent patients lose O2 supply.",
                     consequence_of_delay="Ventilator patients desaturate, oxygen-enriched corridor becomes fire hazard.",
                     delay_s=180),
    ],
    objectives=[
        ScenarioObjective(text="Zone valve isolated and patients switched to backup O2",
                           role="facilities_engineer", condition="containment_rate == 1"),
        ScenarioObjective(text="No patient desaturation event during switchover",
                           role="facilities_engineer", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="hospital",
        actors=[
            ActorSpec(id="pipe-c", type="gas_pipeline", name="Ward C O2 Pipeline"),
            ActorSpec(id="gzv-c", type="gas_zone_valve", name="Ward C Zone Valve"),
            ActorSpec(id="cyl-1", type="oxygen_cylinder", name="Portable O2 Cylinder"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="gas_pressure_monitor", targets=["pipe-c"], scope="actor"),
            ResourceSpec(id="res-2", type="cylinder_inventory"),
        ],
    ),
    tags=["medical-gas", "oxygen", "pipeline", "life-safety"],
)

register_scenario(SCENARIO)
