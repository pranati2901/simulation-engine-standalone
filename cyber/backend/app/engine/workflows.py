"""Layer 6 — Roles & Workflows (IRP-grounded, customizable).

Each team's procedure is *data*: a list of tasks sourced from the GoalCert Incident Response
Plan (IRP-CYBER-001). Tasks are grouped by phase/stage and each carries a **modeled effect** —
so enabling/disabling a task mechanically changes the simulation outcome (which posture attacks
or defends better), not just a checklist tick.

- `default_enabled` defines the **default workflow** that runs out-of-the-box.
- `removable=False` marks a core task the operator cannot turn off.
- `effects` are aggregated into a deterministic Posture (see engine/posture.py) that modulates
  detection, prevention, triage/containment latency, segmentation, persistence and recovery.

The `kind` handle + `effects` are the action-space + guardrails a future AIDriver would consume.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import Side

# Technique families an effect can scope to (also see engine/posture.py TECHNIQUE_FAMILY).
FAMILIES = ("recon", "phishing", "c2", "credaccess", "lateral", "persistence", "exfil", "impact", "ot")


class TaskEffect(BaseModel):
    """A modeled effect a task contributes when enabled.

    kind — what it does (see engine/posture.py for the full vocabulary).
    scope — optional technique family it applies to ("all" or a FAMILIES value).
    magnitude — strength (interpretation depends on kind; default 1).
    """
    kind: str
    scope: str | None = None
    magnitude: float = 1.0


class RoleInfo(BaseModel):
    role: str
    name: str
    mission: str
    description: str


class WorkflowStep(BaseModel):
    id: str
    team: str
    kind: str                      # engine handle / grouping
    label: str
    description: str = ""
    phase_hint: str = ""           # stage grouping for the UI
    irp_ref: str = ""              # IRP source id (e.g. B.C.02)
    default_enabled: bool = True   # part of the default workflow
    removable: bool = True         # operator may toggle it off
    effects: list[TaskEffect] = Field(default_factory=list)


class Workflow(BaseModel):
    actor: str
    id: str
    name: str
    description: str
    steps: list[WorkflowStep] = Field(default_factory=list)


ROLES: dict[str, RoleInfo] = {
    Side.RED.value: RoleInfo(
        role="red", name="Red Team (Adversary)",
        mission="Compromise, escalate, exfiltrate and impact — adapting TTPs when blocked.",
        description="Executes the APT→ransomware→OT kill-chain (IRP ch.07). Evasion tasks let it "
                    "survive detection and containment; toggle them to tune attacker sophistication."),
    Side.SOC.value: RoleInfo(
        role="soc", name="Security Operations Centre",
        mission="Detect fast, triage accurately, classify severity, escalate correctly.",
        description="Runs the Identification phase + severity tree + escalation matrix (IRP ch.02/09). "
                    "Detection/triage tasks decide how fast and accurately the SOC sees the attack."),
    Side.BLUE.value: RoleInfo(
        role="blue", name="Blue Team (Incident Response)",
        mission="Contain, eradicate and recover — preserving evidence, following decision gates.",
        description="Runs the NIST 800-61 lifecycle (IRP ch.03–05). Containment, eradication and "
                    "recovery tasks decide how well the intrusion is stopped and undone."),
    Side.MGMT.value: RoleInfo(
        role="mgmt", name="Management / Incident Command",
        mission="Executive decisions, notifications and regulatory deadlines.",
        description="Triggered by P-level (IRP ch.09/12): notify CISO/exec, declare P0, BCP, regulatory."),
    Side.OT.value: RoleInfo(
        role="ot", name="OT / Operations",
        mission="Protect safety-critical processes; switch to manual.",
        description="Validates OT alerts, switches to manual operations, isolates the OT segment."),
}


def _s(team, sid, kind, label, desc="", phase="", irp="", default=True, removable=True,
       effects=None) -> WorkflowStep:
    return WorkflowStep(id=sid, team=team, kind=kind, label=label, description=desc, phase_hint=phase,
                        irp_ref=irp, default_enabled=default, removable=removable,
                        effects=effects or [])


def _e(kind, scope=None, magnitude=1.0) -> TaskEffect:
    return TaskEffect(kind=kind, scope=scope, magnitude=magnitude)


_WORKFLOWS: dict[str, Workflow] = {}


def _register(wf: Workflow) -> Workflow:
    _WORKFLOWS[wf.id] = wf
    return wf


# --------------------------------------------------------------------------- #
#  RED — apt_ransomware_killchain (IRP ch.07: kill-chain + evasion table 7.2)
# --------------------------------------------------------------------------- #
_register(Workflow(
    actor="red", id="apt_ransomware_killchain", name="APT → Ransomware → OT kill-chain",
    description="Seven-stage adversary kill-chain plus evasion tradecraft. Evasion tasks make the "
                "attacker stealthier and more resilient to Blue's response.",
    steps=[
        _s("red", "red.recon", "recon", "Reconnaissance", "OSINT, identity & service mapping",
           "Reconnaissance", "7.1-1", removable=False),
        _s("red", "red.lure", "weaponise", "Weaponise: look-alike domain + macro lure",
           "Delayed-macro / HTML-smuggling lure that bypasses commodity email filtering",
           "Initial Compromise", "7.1-2", effects=[_e("phish_potency", "phishing", 1)]),
        _s("red", "red.access", "initial_access", "Initial access + C2 beacon",
           "Phish → execute → migrate to stable process → establish C2", "Initial Compromise",
           "7.1-3", removable=False),
        _s("red", "red.amsi", "evasion", "AMSI bypass + process injection",
           "Reflective DLL / injection into benign process to dodge EDR behavioural detection",
           "Initial Compromise", "7.2-EDR", effects=[_e("evasion", "all", 1.4)]),
        _s("red", "red.c2_https", "evasion", "C2 over HTTPS / domain fronting",
           "Blend C2 with legitimate CDN traffic; resists perimeter blocking", "Initial Compromise",
           "7.2-NET", effects=[_e("c2_resilience"), _e("evasion", "c2", 1.3)]),
        _s("red", "red.dns_c2", "evasion", "DNS-over-HTTPS fallback C2",
           "Backup channel that survives a primary C2 block (IRP R.C.01)", "Initial Compromise",
           "R.C.01", default=False, effects=[_e("c2_resilience", magnitude=2.0)]),
        _s("red", "red.low_slow", "evasion", "Low & slow operation",
           "One TTP every 15+ min during business hours to dodge velocity-based SIEM rules",
           "Initial Compromise", "R.ID.04", default=False, effects=[_e("low_and_slow", "all", 1.5)]),
        _s("red", "red.lolbins", "evasion", "LOLBins after EDR flag",
           "Switch to certutil/mshta/regsvr32 if PowerShell is flagged (IRP R.C.04)",
           "Privilege Escalation", "R.C.04", default=False, effects=[_e("evasion", "all", 1.3)]),
        _s("red", "red.privesc", "priv_esc", "Privilege escalation to Domain Admin",
           "LSASS dump → Kerberoast → Pass-the-Hash → DCSync", "Privilege Escalation", "7.1-4",
           removable=False),
        _s("red", "red.persist", "persistence", "Persistence (tasks/registry/SMB beacon/Golden Ticket)",
           "Survives reboot & host isolation; Golden Ticket survives until krbtgt ×2 reset",
           "Persistence", "R.E", effects=[_e("persistence_strong", magnitude=1.0)]),
        _s("red", "red.lateral", "lateral", "Lateral movement to sensitive VLAN",
           "RDP/SMB + SOCKS pivot through the DC toward sensitive/OT zones", "Lateral Movement",
           "7.1-5", removable=False),
        _s("red", "red.exfil", "exfil", "Collection & exfiltration",
           "Stage, archive+encrypt, exfil over DNS tunnel / cloud", "Data Exfiltration", "7.1-6",
           removable=False),
        _s("red", "red.impact", "impact", "Impact: ransomware + log clearing + OT",
           "Disable tools, encrypt shares, clear logs, pivot to PLCs", "Ransomware", "7.1-7",
           removable=False),
    ],
))

# --------------------------------------------------------------------------- #
#  SOC — tiered_triage_escalation (IRP ch.02 + checklists)
# --------------------------------------------------------------------------- #
_register(Workflow(
    actor="soc", id="tiered_triage_escalation", name="Tiered triage & escalation",
    description="Identification phase: detect → triage → classify severity → escalate → hunt. "
                "Detection tasks decide what the SOC can see; triage tasks decide how fast.",
    steps=[
        _s("soc", "soc.siem_sources", "detect", "Verify SIEM data sources feeding",
           "No log gaps — broad baseline detection", "Preparation", "B.02a",
           effects=[_e("detect", "all", 0.10)]),
        _s("soc", "soc.correlation", "detect", "Enable high-fidelity correlation rules",
           "Kerberoasting / LSASS / Pass-the-Hash / lateral-movement detection content",
           "Preparation", "B.02", effects=[_e("detect", "credaccess", 0.6), _e("detect", "lateral", 0.45)]),
        _s("soc", "soc.edr_coverage", "detect", "Confirm EDR coverage at 100%",
           "All endpoints sensored; strong endpoint detection", "Preparation", "B.03",
           effects=[_e("detect", "impact", 0.4), _e("detect", "persistence", 0.4)]),
        _s("soc", "soc.threat_intel", "detect", "Threat-intel enrichment (MISP/VT)",
           "Faster, higher-confidence triage; C2 reputation", "Identification", "1.2",
           effects=[_e("detect", "c2", 0.4), _e("triage_speed", magnitude=0.85)]),
        _s("soc", "soc.l1_triage", "triage", "L1 triage — filter false positives",
           "First-line analyst confirms malicious before escalation", "Identification", "2.2",
           removable=False, effects=[_e("triage_speed", magnitude=0.85)]),
        _s("soc", "soc.severity_tree", "classify", "Severity decision tree (accurate P-level)",
           "Correctly classifies privileged-host / DCSync / ransomware as P1/P0", "Identification",
           "2.2", effects=[_e("escalation_quality", magnitude=1.0)]),
        _s("soc", "soc.escalate", "escalate", "Escalate per matrix to IR",
           "Hands off to Blue and notifies the chain", "Identification", "ch.09", removable=False),
        _s("soc", "soc.l2_investigation", "investigate", "L2 investigation: process tree & scope",
           "Widens scope across hosts", "Identification", "8.1", effects=[_e("detect", "all", 0.08)]),
        _s("soc", "soc.threat_hunt", "hunt", "Threat hunt — persistence & rogue accounts",
           "Proactively finds persistence the alerts missed (IRP 4.2)", "Persistence", "4.2",
           effects=[_e("hunt", magnitude=1.0), _e("detect", "persistence", 0.3)]),
        _s("soc", "soc.sitrep", "coordination", "30-min sitrep cadence + out-of-band war room",
           "Keeps response coordinated under pressure", "Identification", "B.C.07", default=False,
           effects=[_e("triage_speed", magnitude=0.92)]),
    ],
))

# --------------------------------------------------------------------------- #
#  BLUE — nist_ir_response (IRP ch.03–05)
# --------------------------------------------------------------------------- #
_register(Workflow(
    actor="blue", id="nist_ir_response", name="NIST 800-61 incident response",
    description="Identify → Contain → Eradicate → Recover, with decision gates. Containment tasks "
                "decide how fast/whether the attack is stopped; eradication decides if it stays gone.",
    steps=[
        _s("blue", "blue.identify", "identify", "Identify & scope incident",
           "Confirm, scope and prioritise with SOC", "Identification", "ch.02", removable=False),
        _s("blue", "blue.memory_first", "evidence", "Acquire memory BEFORE isolation",
           "Preserves volatile evidence (small containment delay; evidence integrity)",
           "Containment", "B.C.01", effects=[_e("evidence_first", magnitude=1.0)]),
        _s("blue", "blue.block_egress", "prevent_egress", "Block egress at firewall + DNS sinkhole FIRST",
           "Stops exfiltration channels before dealing with the host (IRP B.C.02)", "Containment",
           "B.C.02", effects=[_e("prevent_egress", magnitude=1.0)]),
        _s("blue", "blue.edr_contain", "contain", "EDR network containment",
           "Isolate confirmed-compromised hosts while keeping forensic telemetry", "Containment",
           "B.C.03", removable=False, effects=[_e("containment_enable"), _e("contain_speed", magnitude=1.0)]),
        _s("blue", "blue.disable_accounts", "cred", "Disable compromised accounts",
           "Disable (not just reset) accounts used for lateral movement", "Containment", "B.C.04",
           effects=[_e("cred_reset", magnitude=0.5)]),
        _s("blue", "blue.segmentation", "segment", "Emergency VLAN segmentation / ACL review",
           "Blocks cross-zone lateral movement and the IT→OT pivot (IRP B.C.05)", "Containment",
           "B.C.05", effects=[_e("segment", magnitude=1.0)]),
        _s("blue", "blue.widen_hunt", "hunt", "Widen the hunt (72h, same C2/process chain)",
           "Finds additional compromised hosts and persistence", "Containment", "B.C.06",
           effects=[_e("hunt", magnitude=1.0)]),
        _s("blue", "blue.dc_gate", "decision", "Decision gate: don't isolate the DC without approval",
           "Blocks DC from sensitive VLANs instead of breaking auth (IRP 3.1)", "Containment", "3.1",
           effects=[_e("decision_gate", "dc", 1.0)]),
        _s("blue", "blue.eradicate", "eradicate", "Eradicate persistence (full IOC sweep)",
           "Removes every persistence mechanism on the R.E list", "Persistence", "B.E.02",
           effects=[_e("eradication", magnitude=1.0)]),
        _s("blue", "blue.krbtgt", "cred", "krbtgt reset ×2 + domain-wide reset",
           "Invalidates Golden Tickets and stolen domain creds after DCSync", "Persistence", "B.E.04",
           effects=[_e("cred_reset", magnitude=1.0), _e("eradication", magnitude=0.5)]),
        _s("blue", "blue.reimage", "eradicate", "Reimage from clean baseline + patch vector",
           "Rebuilds compromised hosts and closes the initial-access vector", "Ransomware", "B.E.06",
           default=False, effects=[_e("eradication", magnitude=0.5)]),
        _s("blue", "blue.backups", "recovery", "Tested offline backups + staged recovery",
           "Reduces ransomware/OT impact and recovery time (IRP ch.05)", "Ransomware", "B.R.04",
           effects=[_e("recovery", magnitude=1.0)]),
        _s("blue", "blue.lessons", "lessons", "Lessons learned / AAR",
           "Produces the after-action report", "OT Attack", "ch.06", removable=False),
    ],
))

# --------------------------------------------------------------------------- #
#  MGMT + OT (kept; mostly representational, no mechanical effects)
# --------------------------------------------------------------------------- #
_register(Workflow(
    actor="mgmt", id="exec_escalation_regulatory", name="Executive escalation & regulatory",
    description="Decisions and notifications gated on P-level, with modeled deadlines (IRP ch.09/12).",
    steps=[
        _s("mgmt", "mgmt.notify_ciso", "notify_ciso", "Notify CISO / open war-room",
           "On P1, within 30 minutes", "Privilege Escalation", "ch.09"),
        _s("mgmt", "mgmt.declare_p0", "declare_p0", "Declare P0 / activate BCP",
           "On domain breach / ransomware", "Ransomware", "8.1"),
        _s("mgmt", "mgmt.regulatory", "regulatory", "Regulatory notification",
           "NDB / ACSC / APRA clocks (IRP ch.12)", "Data Exfiltration", "ch.12"),
        _s("mgmt", "mgmt.comms", "comms", "Public & customer comms (no ransom w/o Legal)",
           "Coordinated communications", "Ransomware", "8.1"),
    ],
))

_register(Workflow(
    actor="ot", id="ot_safety_ops", name="OT safety operations",
    description="Protect safety-critical processes when the attack reaches OT (IRP Phase 8).",
    steps=[
        _s("ot", "ot.validate", "validate", "Validate OT alerts", "Confirm setpoint deviations",
           "OT Attack", "8"),
        _s("ot", "ot.coordinate", "coordinate", "Coordinate with plant operators", "", "OT Attack", "8"),
        _s("ot", "ot.manual", "manual_ops", "Switch to manual operations",
           "Take control off the compromised path", "OT Attack", "8"),
        _s("ot", "ot.isolate", "isolate_ot", "Isolate OT segment", "Protect safety interlocks",
           "OT Attack", "8"),
    ],
))


def get_workflow(workflow_id: str) -> Workflow:
    if workflow_id not in _WORKFLOWS:
        raise KeyError(f"Unknown workflow: {workflow_id}")
    return _WORKFLOWS[workflow_id]


def all_workflows() -> list[Workflow]:
    return [_WORKFLOWS[k] for k in sorted(_WORKFLOWS)]


def workflows_by_actor(actor: str) -> list[Workflow]:
    return [w for w in all_workflows() if w.actor == actor]


def role_catalog() -> list[dict]:
    return [ROLES[r].model_dump() for r in ("red", "soc", "blue", "mgmt", "ot")]


def workflow_catalog() -> list[dict]:
    return [w.model_dump() for w in all_workflows()]


def default_enabled_ids(workflow_id: str) -> list[str]:
    return [s.id for s in get_workflow(workflow_id).steps if s.default_enabled]


DEFAULT_BINDINGS: dict[str, str] = {
    "red": "apt_ransomware_killchain", "soc": "tiered_triage_escalation",
    "blue": "nist_ir_response", "mgmt": "exec_escalation_regulatory", "ot": "ot_safety_ops",
}
