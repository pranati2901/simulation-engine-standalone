"""Scenario: charging network cyber attack -> session hijack prevention."""
from __future__ import annotations

from ...loader import register_scenario
from ....engine.environment import ActorSpec, EnvironmentSpec, ResourceSpec
from ....engine.scenario import DecisionGate, Scenario, ScenarioObjective, ScenarioStep, TargetSelector

SCENARIO = Scenario(
    id="ev.cyber_attack_v1",
    name="Charging Network Cyber Attack - Session Hijack Prevention",
    domain="ev",
    description="The OCPP management system detects anomalous session commands indicating "
                "a man-in-the-middle attack on charger communications. The SOC analyst "
                "must isolate compromised nodes and prevent billing fraud or unsafe "
                "charge profile injection.",
    node_kind="fault", category="cyber", impact_level="critical",
    phases=["detect", "diagnose", "respond"],
    steps=[
        ScenarioStep(id="s1", action="anomalous_ocpp_commands", phase="detect", at_min=0.0,
                     target=TargetSelector(by="type", value="ocpp_gateway"),
                     label="Anomalous OCPP commands detected on management gateway"),
        ScenarioStep(id="s2", action="session_isolation", phase="diagnose", at_min=5.0,
                     target=TargetSelector(by="type", value="dc_fast_charger"),
                     label="Compromised charger sessions isolated"),
        ScenarioStep(id="s3", action="certificate_rotation", phase="respond", at_min=15.0,
                     target=TargetSelector(by="type", value="ocpp_gateway"),
                     label="TLS certificates rotated on affected nodes"),
    ],
    decision_gates=[
        DecisionGate(id="g1", trigger="s1", name="Cyber Attack Response",
                     correct_action="Isolate compromised nodes, block spoofed sessions, rotate certificates, notify CERT.",
                     risk_level="extreme",
                     description="Safety and financial risk: hijacked sessions can inject unsafe charge profiles.",
                     consequence_of_delay="Attacker escalates to injecting overcharge profiles, risking battery damage.",
                     delay_s=300),
    ],
    objectives=[
        ScenarioObjective(text="Compromised sessions isolated before charge profile manipulation",
                           role="soc_analyst", condition="containment_rate == 1"),
        ScenarioObjective(text="No billing fraud or unsafe charge profile injected",
                           role="soc_analyst", condition="prevented == 0"),
    ],
    recommended_environment=EnvironmentSpec(
        domain="ev",
        actors=[
            ActorSpec(id="gw-1", type="ocpp_gateway", name="OCPP Gateway"),
            ActorSpec(id="dcfc-3", type="dc_fast_charger", name="DC Fast Charger 3"),
        ],
        resources=[
            ResourceSpec(id="res-1", type="intrusion_detection_system", targets=["gw-1"], scope="actor"),
            ResourceSpec(id="res-2", type="siem_monitoring"),
        ],
    ),
    tags=["cyber", "ocpp", "session-hijack", "safety"],
)

register_scenario(SCENARIO)
