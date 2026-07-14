"""Scenario: mass casualty influx -> triage protocol, resource surge."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="hospital.mass_casualty_v1",
    name="Mass Casualty Incident - Triage and Resource Surge",
    domain="hospital",
    description="A multi-vehicle accident generates 20+ casualties arriving at the ED "
                "simultaneously. The incident commander must activate the mass casualty "
                "plan, set up triage zones, and surge additional staff and resources.",
    node_kind="fault", category="operational", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="mci_notification", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="emergency_department"),
                     label="Mass casualty notification received from EMS"),
        ScenarioStep(id="s2", action="triage_setup", phase="diagnose", at_min=5.0,
                     target=TargetSelector(by="type", value="triage_area"),
                     label="START triage zones established at ED entrance"),
        ScenarioStep(id="s3", action="resource_surge", phase="respond", at_min=10.0,
                     target=TargetSelector(by="type", value="staff_pool"),
                     label="Off-duty staff recalled and additional resources deployed"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Mass Casualty Response",
                     correct_action="Activate MCI plan, establish triage zones, recall staff, defer elective procedures.",
                     risk_level="extreme",
                     description="Life-safety critical: delayed triage causes preventable deaths from treatable injuries.",
                     consequence_of_delay="ED overwhelmed, critical patients wait too long for intervention.",
                     delay_s=600),
    ],
    objectives=[
        ScenarioObjective(text="Triage zones operational before first casualties arrive",
                           role="incident_commander", condition="containment_rate == 1"),
        ScenarioObjective(text="All red-tag patients receive intervention within golden hour",
                           role="incident_commander", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="hospital",
        actors=[
            ActorSpec(id="ed-1", type="emergency_department", name="Emergency Department"),
            ActorSpec(id="triage-1", type="triage_area", name="Triage Area"),
            ActorSpec(id="staff-1", type="staff_pool", name="Staff Pool"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="mci_kit", targets=["triage-1"], scope="actor"),
            ResourceSpec(id="res-2", type="bed_management_system"),
        ],
    ),
    tags=["mass-casualty", "triage", "surge", "life-safety"],
)

register_scenario(SCENARIO)
