"""Scenario: code blue cardiac arrest -> crash team response, equipment readiness."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="hospital.code_blue_v1",
    name="Code Blue - Cardiac Arrest Response",
    domain="hospital",
    description="A patient in Ward D goes into cardiac arrest. The ward nurse must "
                "initiate CPR, call a Code Blue, and ensure the crash cart and "
                "defibrillator are at bedside before the crash team arrives.",
    node_kind="fault", category="human", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="cardiac_arrest_detected", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="patient_bed"),
                     label="Patient monitor shows asystole / pulseless VT"),
        ScenarioStep(id="s2", action="code_blue_called", phase="diagnose", at_min=1.0,
                     target=TargetSelector(by="type", value="nurse_station"),
                     label="Code Blue announced, crash team paged"),
        ScenarioStep(id="s3", action="crash_cart_deployed", phase="respond", at_min=2.0,
                     target=TargetSelector(by="type", value="crash_cart"),
                     label="Crash cart and defibrillator at bedside"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Code Blue Response",
                     correct_action="Start CPR, call Code Blue, retrieve crash cart, prepare defibrillator.",
                     risk_level="extreme",
                     description="Life-safety critical: survival drops 10% per minute without CPR and defibrillation.",
                     consequence_of_delay="Irreversible brain damage after 4-6 minutes without intervention.",
                     delay_s=120),
    ],
    objectives=[
        ScenarioObjective(text="CPR initiated and crash cart at bedside within 2 minutes",
                           role="ward_nurse", condition="containment_rate == 1"),
        ScenarioObjective(text="Crash team arrived and ACLS protocol initiated",
                           role="ward_nurse", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="hospital",
        actors=[
            ActorSpec(id="bed-d4", type="patient_bed", name="Ward D Bed 4"),
            ActorSpec(id="ns-d", type="nurse_station", name="Ward D Nurse Station"),
            ActorSpec(id="cart-1", type="crash_cart", name="Crash Cart 1"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="defibrillator", targets=["cart-1"], scope="actor"),
            ResourceSpec(id="res-2", type="patient_monitoring", targets=["bed-d4"], scope="actor"),
        ],
    ),
    tags=["code-blue", "cardiac-arrest", "life-safety", "crash-team"],
)

register_scenario(SCENARIO)
