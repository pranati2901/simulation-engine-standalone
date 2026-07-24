"""Operation Black Phoenix — SOC scenario.

SOC detection and triage exercise: identify, correlate, and escalate attacker
activity across a multi-stage intrusion. Full defensive stack enabled to
maximise detection opportunities. Phases framed around SOC analyst workflow.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.engine.environment import AssetSpec, ControlSpec, EnvironmentSpec
from app.engine.scenario import Objectives, PlaybookStep, Scenario, TargetSelector

PHASES = [
    "Alert Triage", "Initial Detection", "Threat Hunting",
    "Scope Assessment", "Evidence Collection", "Escalation",
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
        PlaybookStep(id="s01", technique="phishing", phase=PHASES[0], at_min=4,
                     target=role("primary_endpoint"), is_inject=True,
                     label="Suspicious email with weaponised attachment detected by gateway"),
        PlaybookStep(id="s02", technique="c2_beacon", phase=PHASES[0], at_min=7,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s03", technique="credential_dump", phase=PHASES[1], at_min=12,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s04", technique="kerberoasting", phase=PHASES[1], at_min=16,
                     target=typ("domain_controller")),
        PlaybookStep(id="s05", technique="dcsync_domain_admin", phase=PHASES[2], at_min=22,
                     target=typ("domain_controller")),
        PlaybookStep(id="s06", technique="lateral_movement", phase=PHASES[2], at_min=28,
                     target=role("sensitive_share"), label="Lateral movement to file server"),
        PlaybookStep(id="s07", technique="persistence_task", phase=PHASES[3], at_min=34,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s08", technique="collection_staging", phase=PHASES[3], at_min=40,
                     target=role("sensitive_share"), is_inject=True,
                     label="Sensitive engineering drawings being staged for exfiltration"),
        PlaybookStep(id="s09", technique="exfiltration", phase=PHASES[4], at_min=48,
                     target=role("sensitive_share")),
        PlaybookStep(id="s10", technique="disable_security_tools", phase=PHASES[4], at_min=54,
                     target=role("primary_endpoint")),
        PlaybookStep(id="s11", technique="ransomware", phase=PHASES[5], at_min=62,
                     target=typ("erp"), is_inject=True,
                     label="Ransomware detonation — must escalate to incident response"),
    ]


def build() -> Scenario:
    return Scenario(
        schema_version=1,
        id="operation_black_phoenix_soc",
        name="Operation Black Phoenix — SOC",
        type="soc",
        industry="manufacturing",
        badge="badge-green",
        label="SOC",
        description=("SOC detection and triage exercise: identify, correlate, and escalate "
                     "attacker activity across a multi-stage intrusion. Emphasis on MTTD, "
                     "alert fidelity, and threat hunting across SIEM, EDR, and network telemetry."),
        nominal_duration_min=120,
        mitre_tactics=["Initial Access", "Command and Control", "Credential Access",
                       "Privilege Escalation", "Lateral Movement", "Persistence",
                       "Collection", "Exfiltration", "Defense Evasion", "Impact"],
        phases=PHASES,
        recommended_topology=_topology(),
        playbook=_playbook(),
        objectives=Objectives(
            red=[
                "Gain initial access via phishing",
                "Escalate privileges to Domain Admin",
                "Exfiltrate sensitive engineering data",
            ],
            blue=[
                "Detect the initial phishing compromise within 10 minutes",
                "Identify the C2 beacon via network telemetry",
                "Hunt for credential dumping activity in EDR logs",
                "Correlate Kerberoasting with DCSync in SIEM",
                "Scope the lateral movement to identify all affected hosts",
                "Detect data staging and exfiltration via DLP and network alerts",
                "Preserve forensic evidence and build an incident timeline",
                "Escalate to incident response with a drafted notification",
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
