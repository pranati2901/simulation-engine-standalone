"""Scenario: passenger medical emergency -> station response, ambulance dispatch."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="railway.medical_emergency_v1",
    name="Passenger Medical Emergency - Station Response",
    domain="railway",
    description="A passenger collapses on the platform. Station staff must provide "
                "first aid, deploy the AED if needed, and coordinate with emergency "
                "services while managing train service around the incident.",
    node_kind="fault", category="human", impact_level="high",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="passenger_collapse", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="platform"),
                     label="Passenger collapses on platform"),
        ScenarioStep(id="s2", action="first_aid_response", phase="respond", at_min=2.0,
                     target=TargetSelector(by="type", value="first_aid_point"),
                     label="Station staff deploy AED and administer first aid"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Medical Emergency Response",
                     correct_action="Deploy AED, call 995, cordon incident area, hold/skip trains at platform.",
                     risk_level="extreme",
                     description="Life-safety critical: cardiac events require AED within 3 minutes for survival.",
                     consequence_of_delay="Survival rate drops 10% per minute without defibrillation.",
                     delay_s=180),
    ],
    objectives=[
        ScenarioObjective(text="First aid and AED deployed within 3 minutes",
                           role="station_staff", condition="containment_rate == 1"),
        ScenarioObjective(text="Emergency services notified and ambulance dispatched",
                           role="station_staff", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="railway",
        actors=[
            ActorSpec(id="plat-5", type="platform", name="Platform 5"),
            ActorSpec(id="fap-1", type="first_aid_point", name="First Aid Point 1"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="aed_unit", targets=["fap-1"], scope="actor"),
            ResourceSpec(id="res-2", type="cctv_monitoring"),
        ],
    ),
    tags=["medical", "life-safety", "passenger"],
)

register_scenario(SCENARIO)
