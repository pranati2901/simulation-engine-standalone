"""Operation Black Phoenix — Blue Team scenario.

Incident response exercise: the attacker already has initial access and is
escalating. Blue team must contain, eradicate, recover, and handle regulatory
obligations. Full defensive controls enabled.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.engine.environment import AssetSpec, ControlSpec, EnvironmentSpec
from app.engine.scenario import Objectives, PlaybookStep, Scenario, TargetSelector

PHASES = [
    "Detection & Scoping", "Containment", "Eradication",
    "Recovery", "Post-Incident", "Regulatory Response",
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
        ControlSpec(id="c-seg", type="segmentation"),
        ControlSpec(id="c-dlp", type="dlp"),
        ControlSpec(id="c-mfa", type="mfa"),
        ControlSpec(id="c-backup", type="backups"),
        ControlSpec(id="c-email", type="email_sec"),
    ]
    return EnvironmentSpec(assets=assets, controls=controls)


def _playbook() -> list[PlaybookStep]:
    role = lambda v: TargetSelector(by="role", value=v)  # noqa: E731
    typ = lambda v: TargetSelector(by="type", value=v)   # noqa: E731
    return [
        PlaybookStep(id="s00a", technique="phishing", phase=PHASES[0], at_min=0,
                     target=role("primary_endpoint"), is_inject=True,
                     label="Prior compromise: phishing lure delivered (pre-seeded)"),
        PlaybookStep(id="s00b", technique="c2_beacon", phase=PHASES[0], at_min=1,
                     target=role("primary_endpoint"), is_inject=True,
                     label="Prior compromise: C2 beacon established (pre-seeded)"),
        PlaybookStep(id="s01", technique="credential_dump", phase=PHASES[0], at_min=3,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s02", technique="kerberoasting", phase=PHASES[0], at_min=6,
                     target=typ("domain_controller")),
        PlaybookStep(id="s03", technique="dcsync_domain_admin", phase=PHASES[0], at_min=10,
                     target=typ("domain_controller"), is_inject=True,
                     label="SOC alert: DCSync replication request from non-DC host"),
        PlaybookStep(id="s04", technique="lateral_movement", phase=PHASES[1], at_min=16,
                     target=role("sensitive_share"), label="Lateral movement to file server"),
        PlaybookStep(id="s05", technique="lateral_movement", phase=PHASES[1], at_min=19,
                     target=typ("erp"), label="Lateral movement to ERP"),
        PlaybookStep(id="s06", technique="persistence_task", phase=PHASES[1], at_min=23,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s07", technique="cloud_persistence", phase=PHASES[2], at_min=28,
                     target=typ("cloud")),
        PlaybookStep(id="s08", technique="collection_staging", phase=PHASES[2], at_min=33,
                     target=role("sensitive_share")),
        PlaybookStep(id="s09", technique="exfiltration", phase=PHASES[2], at_min=38,
                     target=role("sensitive_share"), is_inject=True,
                     label="DLP alert: 4.2GB upload to external cloud storage"),
        PlaybookStep(id="s10", technique="disable_security_tools", phase=PHASES[3], at_min=45,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s11", technique="ransomware", phase=PHASES[3], at_min=50,
                     target=typ("erp"), is_inject=True,
                     label="Ransomware detonation across enterprise systems"),
        PlaybookStep(id="s12", technique="ot_pivot", phase=PHASES[3], at_min=58,
                     target=role("it_ot_bridge")),
    ]


def build() -> Scenario:
    return Scenario(
        schema_version=1,
        id="operation_black_phoenix_blue",
        name="Operation Black Phoenix — Blue Team",
        type="blue",
        industry="manufacturing",
        badge="badge-blue",
        label="Blue Team",
        description=("Blue team incident response exercise: contain an active intrusion, "
                     "prevent further damage, recover impacted systems, and manage regulatory "
                     "obligations. The attacker has initial access and is escalating rapidly."),
        nominal_duration_min=150,
        mitre_tactics=["Credential Access", "Privilege Escalation", "Lateral Movement",
                       "Persistence", "Collection", "Exfiltration", "Defense Evasion", "Impact"],
        phases=PHASES,
        recommended_topology=_topology(),
        playbook=_playbook(),
        objectives=Objectives(
            red=[
                "Escalate privileges to Domain Admin",
                "Exfiltrate sensitive engineering data",
                "Deploy ransomware enterprise-wide",
                "Pivot into the OT environment",
            ],
            blue=[
                "Contain compromised endpoints within 15 minutes of detection",
                "Isolate the domain controller to prevent further privilege abuse",
                "Block lateral movement to sensitive shares and ERP",
                "Eradicate persistence mechanisms (endpoint and cloud)",
                "Detect and block data exfiltration before completion",
                "Recover from ransomware using verified backups",
                "Protect safety-critical OT systems from IT-side pivot",
                "Draft regulatory notification and preserve forensic evidence",
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
