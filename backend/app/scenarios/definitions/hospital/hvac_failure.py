"""Scenario: ward HVAC failure -> operating room delay."""
from __future__ import annotations

from ...factory import spawn, when
from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="hospital.hvac_failure_v1",
    name="Ward HVAC Failure - Operating Room Delay",
    domain="hospital",
    description="Ward B HVAC begins drifting out of temperature tolerance. The facilities "
                "engineer must restore climate control before it delays operating room readiness.",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="hvac_failure", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="ward_hvac"),
                     label="Ward B HVAC drifts out of tolerance"),
        ScenarioStep(id="s2", action="or_delay", phase="respond", at_min=30.0,
                     target=TargetSelector(by="type", value="operating_room"),
                     label="Operating room readiness delayed"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="HVAC Fault Response",
                     correct_action="Switch ward to backup generator power, restore climate control.",
                     risk_level="extreme",
                     description="Patient-safety critical: sustained drift risks surgical readiness.",
                     consequence_of_delay="Temperature drift persists into surgical scheduling window.",
                     delay_s=200),
    ],
    objectives=[
        ScenarioObjective(text="HVAC fault correctly resolved by the facilities engineer",
                           role="facilities_engineer", condition="containment_rate == 1"),
        ScenarioObjective(text="No fault-injection step was unexpectedly blocked by backup generator",
                           role="facilities_engineer", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="hospital",
        actors=[
            ActorSpec(id="hvac-b", type="ward_hvac", name="Ward B HVAC"),
            ActorSpec(id="or-1", type="operating_room", name="Operating Room 1"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="backup_generator", targets=["hvac-b"], scope="actor"),
            ResourceSpec(id="res-2", type="facilities_monitoring"),
        ],
    ),
    tags=["hvac", "patient-safety"],
    # Dynamic Scenario Graph — see scenarios/definitions/hospital/cascade.py.
    # The HVAC drift branches: the operating theatre loses positive pressure and the cold
    # chain drifts (both always); if it isn't contained, surgery is cancelled outright. The
    # branches reconverge on infection risk and a hospital-wide patient backlog.
    triggers=[
        when("always", spawn("hospital.or_pressure_loss_v1", delay_min=20)),
        when("always", spawn("hospital.cold_chain_excursion_v1", delay_min=15)),
        when("containment_rate < 1", spawn("hospital.surgery_cancellation_v1", delay_min=25)),
    ],
)

register_scenario(SCENARIO)
