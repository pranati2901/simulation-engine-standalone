"""Scenario: base perimeter breach -> force protection response."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="defence.base_attack_v1",
    name="Base Attack - Perimeter Breach Response",
    domain="defence",
    description="Perimeter intrusion detection system triggers on Sector 3 fence line. "
                "The force protection officer must verify the threat, activate the "
                "Quick Reaction Force, and secure the breach point.",
    node_kind="fault", category="safety", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="perimeter_breach_detected", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="perimeter_sector"),
                     label="Perimeter intrusion alarm on Sector 3"),
        ScenarioStep(id="s2", action="threat_verification", phase="diagnose", at_min=2.0,
                     target=TargetSelector(by="type", value="surveillance_system"),
                     label="Threat verified via thermal imaging"),
        ScenarioStep(id="s3", action="qrf_deployment", phase="respond", at_min=5.0,
                     target=TargetSelector(by="type", value="quick_reaction_force"),
                     label="Quick Reaction Force deployed to breach point"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Perimeter Breach Response",
                     correct_action="Verify threat, sound FPCON alert, deploy QRF, lock down affected sector.",
                     risk_level="extreme",
                     description="Force protection critical: uncontained breach threatens base personnel and assets.",
                     consequence_of_delay="Intruders penetrate inner perimeter, threatening critical infrastructure.",
                     delay_s=180),
    ],
    objectives=[
        ScenarioObjective(text="Threat verified and QRF deployed within 5 minutes",
                           role="force_protection_officer", condition="containment_rate == 1"),
        ScenarioObjective(text="Breach point secured and perimeter integrity restored",
                           role="force_protection_officer", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="defence",
        actors=[
            ActorSpec(id="sec-3", type="perimeter_sector", name="Perimeter Sector 3"),
            ActorSpec(id="surv-1", type="surveillance_system", name="Thermal Surveillance"),
            ActorSpec(id="qrf-1", type="quick_reaction_force", name="QRF Alpha"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="intrusion_detection_system", targets=["sec-3"], scope="actor"),
            ResourceSpec(id="res-2", type="floodlight_system", targets=["sec-3"], scope="actor"),
        ],
    ),
    tags=["perimeter", "force-protection", "base-defence"],
)

register_scenario(SCENARIO)
