"""Operation Black Phoenix — Red Team scenario.

Adversary emulation: execute the full APT kill chain from recon to OT impact.
Compressed timing, reduced defensive controls, attack-focused objectives.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.engine.environment import AssetSpec, ControlSpec, EnvironmentSpec
from app.engine.scenario import Objectives, PlaybookStep, Scenario, TargetSelector

PHASES = [
    "Reconnaissance", "Initial Compromise", "Privilege Escalation", "Lateral Movement",
    "Persistence", "Data Exfiltration", "Ransomware", "OT Attack",
]


def _topology() -> EnvironmentSpec:
    assets = [
        AssetSpec(id="ws-ceo", type="endpoint", name="WS-CEO", role="primary_endpoint", zone="corp",
                  criticality=2, props={"user_susceptibility": 4}),
        AssetSpec(id="ws-fin", type="endpoint", name="WS-FINANCE", zone="corp"),
        AssetSpec(id="dc-01", type="domain_controller", name="DC-01", zone="corp"),
        AssetSpec(id="mail-01", type="email_server", name="MAIL-01", zone="corp"),
        AssetSpec(id="file-eng", type="file_share", name="FILE-ENG", role="sensitive_share",
                  zone="corp", criticality=5, data_sensitivity=5),
        AssetSpec(id="erp-01", type="erp", name="ERP-01", zone="corp"),
        AssetSpec(id="mes-01", type="mes", name="MES-01", role="it_ot_bridge", zone="ot_dmz"),
        AssetSpec(id="twin-01", type="digital_twin", name="DIGITAL-TWIN", zone="ot_dmz"),
        AssetSpec(id="plc-01", type="ot_plc", name="PLC-DOSING", role="plc", zone="ot"),
        AssetSpec(id="cloud-01", type="cloud", name="CLOUD-TENANT", zone="cloud"),
        AssetSpec(id="siem-01", type="siem_platform", name="SIEM", zone="soc"),
        AssetSpec(id="edr-01", type="edr_platform", name="EDR-CONSOLE", zone="soc"),
        AssetSpec(id="fw-01", type="firewall", name="PERIMETER-FW", zone="perimeter"),
        AssetSpec(id="vm-01", type="vuln_mgmt", name="VULN-MGMT", zone="soc"),
    ]
    controls = [
        ControlSpec(id="c-edr", type="edr"),
        ControlSpec(id="c-siem", type="siem"),
        ControlSpec(id="c-fw", type="firewall_ids"),
    ]
    return EnvironmentSpec(assets=assets, controls=controls)


def _playbook() -> list[PlaybookStep]:
    role = lambda v: TargetSelector(by="role", value=v)  # noqa: E731
    typ = lambda v: TargetSelector(by="type", value=v)   # noqa: E731
    return [
        PlaybookStep(id="s01", technique="recon_osint", phase=PHASES[0], at_min=1),
        PlaybookStep(id="s02", technique="phishing", phase=PHASES[1], at_min=3,
                     target=role("primary_endpoint"), is_inject=True,
                     label="Deliver weaponised attachment via supplier look-alike domain"),
        PlaybookStep(id="s03", technique="c2_beacon", phase=PHASES[1], at_min=5,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s04", technique="credential_dump", phase=PHASES[2], at_min=7,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s05", technique="kerberoasting", phase=PHASES[2], at_min=9,
                     target=typ("domain_controller")),
        PlaybookStep(id="s06", technique="dcsync_domain_admin", phase=PHASES[2], at_min=11,
                     target=typ("domain_controller")),
        PlaybookStep(id="s07", technique="lateral_movement", phase=PHASES[3], at_min=14,
                     target=role("sensitive_share"), label="Lateral movement to file server"),
        PlaybookStep(id="s08", technique="lateral_movement", phase=PHASES[3], at_min=16,
                     target=typ("erp"), label="Lateral movement to ERP"),
        PlaybookStep(id="s09", technique="persistence_task", phase=PHASES[4], at_min=18,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s10", technique="cloud_persistence", phase=PHASES[4], at_min=20,
                     target=typ("cloud")),
        PlaybookStep(id="s11", technique="collection_staging", phase=PHASES[5], at_min=24,
                     target=role("sensitive_share"), is_inject=True,
                     label="Stage sensitive engineering drawings for exfiltration"),
        PlaybookStep(id="s12", technique="exfiltration", phase=PHASES[5], at_min=27,
                     target=role("sensitive_share")),
        PlaybookStep(id="s13", technique="disable_security_tools", phase=PHASES[6], at_min=32,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s14", technique="ransomware", phase=PHASES[6], at_min=36,
                     target=typ("erp"), is_inject=True,
                     label="Deploy ransomware across enterprise network"),
        PlaybookStep(id="s15", technique="ot_pivot", phase=PHASES[7], at_min=42,
                     target=role("it_ot_bridge")),
        PlaybookStep(id="s16", technique="ot_plc_modify", phase=PHASES[7], at_min=48,
                     target=role("plc"), is_inject=True,
                     label="Modify PLC setpoints — chemical dosing values drifting"),
    ]


def build() -> Scenario:
    return Scenario(
        schema_version=1,
        id="operation_black_phoenix_red",
        name="Operation Black Phoenix — Red Team",
        type="red",
        industry="manufacturing",
        badge="badge-red",
        label="Red Team",
        description=("Red team adversary emulation: execute a full APT kill chain from "
                     "reconnaissance through OT impact against a manufacturing target. "
                     "Emphasis on offensive tradecraft, evasion, and achieving all attacker objectives."),
        nominal_duration_min=90,
        difficulties=["Medium", "Hard", "Expert"],
        mitre_tactics=["Reconnaissance", "Initial Access", "Command and Control",
                       "Credential Access", "Privilege Escalation", "Lateral Movement",
                       "Persistence", "Collection", "Exfiltration", "Defense Evasion", "Impact"],
        phases=PHASES,
        recommended_topology=_topology(),
        playbook=_playbook(),
        objectives=Objectives(
            red=[
                "Complete external reconnaissance without triggering perimeter alerts",
                "Gain initial access via spear-phishing attachment",
                "Dump credentials and escalate to privileged access",
                "Achieve Domain Admin via DCSync",
                "Move laterally to file server and ERP",
                "Establish dual persistence (endpoint + cloud)",
                "Exfiltrate sensitive engineering data without DLP interception",
                "Deploy ransomware and pivot to OT/PLC for physical impact",
            ],
            blue=[
                "Detect any stage of the intrusion",
                "Contain at least one compromised asset",
            ],
        ),
    )


def _json_path() -> Path:
    return Path(__file__).with_suffix(".json")


def export() -> Path:
    path = _json_path()
    path.write_text(json.dumps(build().model_dump(mode="json"), indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(f"wrote {export()}")
