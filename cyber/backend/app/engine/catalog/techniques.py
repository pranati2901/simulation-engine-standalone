"""Concrete technique catalog (MITRE-aligned), covering Operation Black Phoenix's 8 phases.

Each entry is a declarative TechniqueSpec. Add a new technique by adding a spec here — the
engine interprets it generically. Detection base-latencies (seconds) are scaled at runtime by
difficulty + readiness.
"""
from __future__ import annotations

from ..enums import Severity
from .spec import (
    Effect,
    EmitTemplate,
    Precondition,
    ScoreSpec,
    TechniqueSpec,
    register,
)

# base detection latencies (seconds, pre-scaling)
EDR_FAST = 90.0
SIEM_BROAD = 480.0
FW_NET = 240.0
DLP_DATA = 150.0


def _pre(*items: tuple[str, str | None]) -> list[Precondition]:
    return [Precondition(kind=k, value=v) for k, v in items]


# --------------------------------------------------------------------------- #
#  Phase 1 — Reconnaissance
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="recon_osint", name="OSINT & External Reconnaissance", mitre="T1595/T1589",
    tactic="Reconnaissance", severity=Severity.LOW, requires_target=False,
    preconditions=_pre(("start", None)),
    detection={"firewall_ids": FW_NET, "siem": SIEM_BROAD},
    emits=[
        EmitTemplate(channel="net", severity=Severity.LOW,
                     text="External port/service scanning against perimeter ranges"),
        EmitTemplate(channel="dns", severity=Severity.LOW,
                     text="DNS enumeration / subdomain brute-force observed"),
    ],
    effects=[Effect(kind="flag", value="recon")],
    containable=False,
    score=ScoreSpec(red_success=10, blue_detect=15, blue_contain=0),
))

# --------------------------------------------------------------------------- #
#  Phase 2 — Initial Compromise
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="phishing", name="Spear-Phishing Attachment", mitre="T1566.001",
    tactic="Initial Access", severity=Severity.HIGH,
    preconditions=_pre(("start", None)),
    prevention={"email_sec": 2},          # blocked at Easy/Medium; bypassed Hard/Expert
    detection={"edr": EDR_FAST, "siem": SIEM_BROAD},
    react_kind="compromise",
    emits=[EmitTemplate(channel="email", severity=Severity.MEDIUM,
                        text="Weaponised attachment delivered to {target} (supplier lure)")],
    effects=[
        Effect(kind="compromise", value=None),
        Effect(kind="creds", value="user"),
        Effect(kind="flag", value="c2"),
    ],
    score=ScoreSpec(red_success=50, blue_detect=35, blue_contain=45),
))

register(TechniqueSpec(
    key="c2_beacon", name="Command & Control Beacon", mitre="T1071.001",
    tactic="Command and Control", severity=Severity.MEDIUM,
    preconditions=_pre(("flag", "c2"), ("foothold", None)),
    detection={"firewall_ids": FW_NET, "siem": SIEM_BROAD},
    emits=[EmitTemplate(channel="net", severity=Severity.MEDIUM,
                        text="Periodic HTTPS beacon to external C2 (jittered)")],
    effects=[Effect(kind="flag", value="c2_active")],
    containable=False,
    score=ScoreSpec(red_success=20, blue_detect=25, blue_contain=0),
))

# --------------------------------------------------------------------------- #
#  Phase 3 — Privilege Escalation
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="credential_dump", name="OS Credential Dumping (LSASS)", mitre="T1003.001",
    tactic="Credential Access", severity=Severity.HIGH,
    preconditions=_pre(("foothold", None)),
    detection={"edr": EDR_FAST, "siem": SIEM_BROAD},
    react_kind="credential_dump",
    effects=[Effect(kind="creds", value="privileged")],
    score=ScoreSpec(red_success=60, blue_detect=40, blue_contain=50),
))

register(TechniqueSpec(
    key="kerberoasting", name="Kerberoasting", mitre="T1558.003",
    tactic="Credential Access", severity=Severity.HIGH,
    preconditions=_pre(("foothold", None), ("asset", "domain_controller")),
    detection={"siem": SIEM_BROAD, "edr": EDR_FAST * 2},
    react_kind="kerberoast",
    effects=[Effect(kind="creds", value="privileged")],
    score=ScoreSpec(red_success=60, blue_detect=45, blue_contain=40),
))

register(TechniqueSpec(
    key="dcsync_domain_admin", name="DCSync / Domain Admin Compromise", mitre="T1003.006",
    tactic="Privilege Escalation", severity=Severity.CRITICAL,
    preconditions=_pre(("creds", "privileged"), ("asset", "domain_controller"), ("reachable", None)),
    detection={"siem": SIEM_BROAD, "edr": EDR_FAST},
    react_kind="compromise",
    effects=[Effect(kind="creds", value="domain_admin"), Effect(kind="compromise", value=None)],
    score=ScoreSpec(red_success=100, blue_detect=70, blue_contain=80),
))

# --------------------------------------------------------------------------- #
#  Phase 4 — Lateral Movement
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="lateral_movement", name="Lateral Movement (RDP/SMB)", mitre="T1021",
    tactic="Lateral Movement", severity=Severity.HIGH,
    preconditions=_pre(("creds", "privileged"), ("reachable", None)),
    detection={"siem": SIEM_BROAD, "edr": EDR_FAST * 1.5},
    react_kind="lateral_in",
    effects=[Effect(kind="foothold", value=None)],
    score=ScoreSpec(red_success=40, blue_detect=35, blue_contain=45),
))

# --------------------------------------------------------------------------- #
#  Phase 5 — Persistence
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="persistence_task", name="Scheduled Task / Service Persistence", mitre="T1053",
    tactic="Persistence", severity=Severity.MEDIUM,
    preconditions=_pre(("foothold", None)),
    detection={"edr": EDR_FAST, "siem": SIEM_BROAD},
    react_kind="persistence",
    effects=[Effect(kind="flag", value="persistence")],
    score=ScoreSpec(red_success=50, blue_detect=40, blue_contain=35),
))

register(TechniqueSpec(
    key="cloud_persistence", name="Cloud Account Persistence", mitre="T1136.003",
    tactic="Persistence", severity=Severity.HIGH,
    preconditions=_pre(("creds", "privileged"), ("asset", "cloud")),
    detection={"siem": SIEM_BROAD},
    react_kind="persistence",
    effects=[Effect(kind="flag", value="cloud_persistence")],
    score=ScoreSpec(red_success=50, blue_detect=45, blue_contain=40),
))

# --------------------------------------------------------------------------- #
#  Phase 6 — Data Exfiltration
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="collection_staging", name="Data Collection & Staging", mitre="T1074",
    tactic="Collection", severity=Severity.MEDIUM,
    preconditions=_pre(("foothold", None), ("asset", "file_share"), ("reachable", None)),
    detection={"dlp": DLP_DATA, "siem": SIEM_BROAD},
    react_kind="collection",
    effects=[Effect(kind="flag", value="staged")],
    score=ScoreSpec(red_success=30, blue_detect=35, blue_contain=30),
))

register(TechniqueSpec(
    key="exfiltration", name="Exfiltration to Cloud Storage", mitre="T1567.002",
    tactic="Exfiltration", severity=Severity.HIGH,
    preconditions=_pre(("flag", "staged")),
    prevention={"dlp": 2},                # DLP blocks at Easy/Medium; bypassed Hard/Expert
    detection={"dlp": DLP_DATA, "firewall_ids": FW_NET, "siem": SIEM_BROAD},
    react_kind="exfiltration",
    effects=[Effect(kind="exfiltrate", value=None), Effect(kind="flag", value="exfiltrated")],
    score=ScoreSpec(red_success=120, blue_detect=70, blue_contain=60),
))

# --------------------------------------------------------------------------- #
#  Phase 7 — Ransomware
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="disable_security_tools", name="Impair Defenses (Disable EDR)", mitre="T1562.001",
    tactic="Defense Evasion", severity=Severity.HIGH,
    preconditions=_pre(("creds", "privileged"), ("foothold", None)),
    detection={"siem": SIEM_BROAD},       # central logging still sees it; endpoint EDR is the target
    effects=[Effect(kind="disable_control", value="edr")],
    containable=True,
    score=ScoreSpec(red_success=60, blue_detect=55, blue_contain=70),
))

register(TechniqueSpec(
    key="ransomware", name="Data Encrypted for Impact (Ransomware)", mitre="T1486",
    tactic="Impact", severity=Severity.CRITICAL,
    preconditions=_pre(("creds", "privileged"), ("foothold", None)),
    detection={"edr": EDR_FAST, "siem": SIEM_BROAD},
    react_kind="encrypt",
    effects=[Effect(kind="down", value=None), Effect(kind="flag", value="ransomware")],
    score=ScoreSpec(red_success=200, blue_detect=90, blue_contain=120),
))

# --------------------------------------------------------------------------- #
#  Phase 8 — OT Environment Attack
# --------------------------------------------------------------------------- #
register(TechniqueSpec(
    key="ot_pivot", name="IT/OT Boundary Pivot", mitre="T0866",
    tactic="Lateral Movement (ICS)", severity=Severity.HIGH,
    preconditions=_pre(("foothold", None), ("asset", "mes"), ("reachable", None)),
    detection={"siem": SIEM_BROAD},
    react_kind="lateral_in",
    effects=[Effect(kind="foothold", value=None), Effect(kind="flag", value="in_ot")],
    score=ScoreSpec(red_success=80, blue_detect=60, blue_contain=70),
))

register(TechniqueSpec(
    key="ot_plc_modify", name="Modify PLC Program / Setpoints", mitre="T0836",
    tactic="Impair Process Control (ICS)", severity=Severity.CRITICAL,
    preconditions=_pre(("flag", "in_ot"), ("asset", "ot_plc"), ("reachable", None)),
    detection={"siem": SIEM_BROAD},
    react_kind="ot_modify",
    effects=[Effect(kind="down", value=None), Effect(kind="flag", value="ot_impact")],
    score=ScoreSpec(red_success=200, blue_detect=95, blue_contain=130),
))
