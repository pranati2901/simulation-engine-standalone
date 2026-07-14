"""Scenario: operating room fire -> gas shutoff, patient evacuation."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="hospital.or_fire_v1",
    name="Operating Room Fire - Gas Shutoff and Evacuation",
    domain="hospital",
    description="A fire is detected in Operating Room 2 during a surgical procedure. "
                "The surgical team must execute the RACE protocol: Rescue the patient, "
                "Alarm, Contain the fire, and Extinguish. Medical gas supply must be "
                "shut off immediately to prevent oxygen-fed fire escalation.",
    node_kind="fault", category="safety", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="or_fire_detected", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="operating_room"),
                     label="Fire detected in Operating Room 2"),
        ScenarioStep(id="s2", action="medical_gas_shutoff", phase="diagnose", at_min=1.0,
                     target=TargetSelector(by="type", value="gas_zone_valve"),
                     label="Medical gas zone valve shut off"),
        ScenarioStep(id="s3", action="patient_evacuation", phase="respond", at_min=3.0,
                     target=TargetSelector(by="type", value="operating_room"),
                     label="Patient evacuated from operating room"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="OR Fire Response",
                     correct_action="Shut off medical gas, remove ignition source, evacuate patient, activate fire alarm.",
                     risk_level="extreme",
                     description="Life-safety critical: oxygen-rich OR environment accelerates fire rapidly.",
                     consequence_of_delay="Oxygen-fed fire engulfs the operating room, endangering patient and staff.",
                     delay_s=60),
    ],
    objectives=[
        ScenarioObjective(text="Medical gas shut off within 60 seconds of fire detection",
                           role="surgical_team_lead", condition="containment_rate == 1"),
        ScenarioObjective(text="Patient safely evacuated from the operating room",
                           role="surgical_team_lead", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="hospital",
        actors=[
            ActorSpec(id="or-2", type="operating_room", name="Operating Room 2"),
            ActorSpec(id="gzv-2", type="gas_zone_valve", name="Gas Zone Valve OR-2"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="fire_extinguisher", targets=["or-2"], scope="actor"),
            ResourceSpec(id="res-2", type="fire_alarm_system"),
        ],
    ),
    tags=["fire", "operating-room", "life-safety", "evacuation"],
)

register_scenario(SCENARIO)
