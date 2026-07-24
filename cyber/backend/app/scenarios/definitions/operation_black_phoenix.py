"""Operation Black Phoenix — the flagship scenario (encodes the PDF's 8-phase exercise).

Authored in Python against the engine catalog, then exported to JSON (the seed source of
truth). Run this module directly to (re)generate operation_black_phoenix.json.
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
        ControlSpec(id="c-edr", type="edr"),               # auto-attaches to endpoints/servers/DC
        ControlSpec(id="c-siem", type="siem"),
        ControlSpec(id="c-fw", type="firewall_ids"),
        ControlSpec(id="c-seg", type="segmentation"),
        ControlSpec(id="c-dlp", type="dlp"),               # auto-attaches to data/cloud
        ControlSpec(id="c-mfa", type="mfa"),
        ControlSpec(id="c-backup", type="backups"),
        ControlSpec(id="c-email", type="email_sec"),
    ]
    return EnvironmentSpec(assets=assets, controls=controls)


def _playbook() -> list[PlaybookStep]:
    role = lambda v: TargetSelector(by="role", value=v)  # noqa: E731
    typ = lambda v: TargetSelector(by="type", value=v)   # noqa: E731
    return [
        PlaybookStep(id="s01", technique="recon_osint", phase=PHASES[0], at_min=1),
        PlaybookStep(id="s02", technique="phishing", phase=PHASES[1], at_min=4,
                     target=role("primary_endpoint"), is_inject=True,
                     label="Phishing email from trusted-supplier look-alike delivered"),
        PlaybookStep(id="s03", technique="c2_beacon", phase=PHASES[1], at_min=6,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s04", technique="credential_dump", phase=PHASES[2], at_min=9,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s05", technique="kerberoasting", phase=PHASES[2], at_min=11,
                     target=typ("domain_controller")),
        PlaybookStep(id="s06", technique="dcsync_domain_admin", phase=PHASES[2], at_min=14,
                     target=typ("domain_controller")),
        PlaybookStep(id="s07", technique="lateral_movement", phase=PHASES[3], at_min=17,
                     target=role("sensitive_share"), label="Lateral movement to file server"),
        PlaybookStep(id="s08", technique="lateral_movement", phase=PHASES[3], at_min=19,
                     target=typ("erp"), label="Lateral movement to ERP"),
        PlaybookStep(id="s09", technique="persistence_task", phase=PHASES[4], at_min=22,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s10", technique="cloud_persistence", phase=PHASES[4], at_min=25,
                     target=typ("cloud")),
        PlaybookStep(id="s11", technique="collection_staging", phase=PHASES[5], at_min=30,
                     target=role("sensitive_share"), is_inject=True,
                     label="Sensitive engineering drawings staged for exfiltration"),
        PlaybookStep(id="s12", technique="exfiltration", phase=PHASES[5], at_min=34,
                     target=role("sensitive_share")),
        PlaybookStep(id="s13", technique="disable_security_tools", phase=PHASES[6], at_min=40,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s14", technique="ransomware", phase=PHASES[6], at_min=45,
                     target=typ("erp"), is_inject=True,
                     label="Ransomware deployment begins across the enterprise"),
        PlaybookStep(id="s15", technique="ot_pivot", phase=PHASES[7], at_min=52,
                     target=role("it_ot_bridge")),
        PlaybookStep(id="s16", technique="ot_plc_modify", phase=PHASES[7], at_min=58,
                     target=role("plc"), is_inject=True,
                     label="Unauthorized PLC setpoint change — chemical dosing values drifting"),
    ]


def build() -> Scenario:
    return Scenario(
        schema_version=1,
        id="operation_black_phoenix",
        name="Operation Black Phoenix",
        type="purple",
        industry="manufacturing",
        badge="badge-purple",
        label="Full-Scope (Red/Blue/SOC)",
        description=("Sophisticated, multi-stage intrusion against a critical-infrastructure "
                     "manufacturer: phishing to domain-admin, exfiltration of engineering IP, "
                     "enterprise ransomware, and an IT/OT pivot to manipulate plant PLCs."),
        nominal_duration_min=120,
        mitre_tactics=["Reconnaissance", "Initial Access", "Credential Access",
                       "Privilege Escalation", "Lateral Movement", "Persistence",
                       "Collection", "Exfiltration", "Defense Evasion", "Impact"],
        phases=PHASES,
        recommended_topology=_topology(),
        playbook=_playbook(),
        objectives=Objectives(
            red=[
                "Gain initial access via phishing",
                "Escalate privileges to Domain Admin",
                "Establish persistence (endpoint and cloud)",
                "Exfiltrate sensitive engineering data",
                "Deploy ransomware enterprise-wide",
                "Impact the OT/physical process",
            ],
            blue=[
                "Detect the initial compromise quickly",
                "Contain and isolate affected hosts",
                "Prevent privilege escalation to Domain Admin",
                "Detect and block data exfiltration",
                "Maintain business continuity / recover from ransomware",
                "Protect safety-critical OT systems",
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
