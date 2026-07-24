"""Scenario = attacker playbook + recommended environment (intent, not outcome).

A scenario expresses *what the attacker attempts* and *what environment makes the run
meaningful*. Outcomes emerge from the engine resolving the playbook against the world.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .environment import EnvironmentSpec


class TargetSelector(BaseModel):
    by: Literal["role", "type"] = "role"
    value: str
    # which match to use when several exist
    pick: Literal["first", "all"] = "first"


class DetectionSignal(BaseModel):
    """Expected SOC detection signal for a playbook step (IRP ch.02 detection table)."""
    indicator_type: str = "Behavioural"  # Behavioural | Network | Active Directory | Registry | Data Access
    signal: str = ""                     # e.g. "Office app spawning PowerShell with -enc flag"
    detection_source: str = ""           # e.g. "EDR, SIEM Process Events"
    expected_priority: str = "P2"        # P0 | P1 | P2 | P3


class PlaybookStep(BaseModel):
    id: str
    technique: str                      # technique key from the catalog
    phase: str                          # phase name (must be in scenario.phases)
    at_min: float = 0.0                 # nominal minute offset within the scenario timeline
    target: TargetSelector | None = None
    is_inject: bool = False
    label: str | None = None            # optional human description override
    # v2: expected detections — what the SOC should see at this step (IRP ch.02)
    expected_detections: list[DetectionSignal] = Field(default_factory=list)
    # v2: fallback technique — if this step is blocked, try this technique instead (IRP ch.07 evasion)
    fallback_technique: str | None = None
    # v2: persistence sub-type for eradication matching (IRP ch.04)
    persistence_type: str | None = None  # registry_run_key | scheduled_task | process_injection | rogue_account | golden_ticket | log_deletion


class DecisionGate(BaseModel):
    """A containment decision gate from IRP ch.03 — an IF/THEN branch the engine enforces.

    When the gate's trigger condition is met during containment, the engine checks
    whether the correct action was taken (driven by posture/workflow config) and scores accordingly.
    """
    id: str                              # unique identifier
    name: str                            # human label
    trigger: str                         # condition key: "dc_compromised" | "multi_host" | "ransomware_spreading" | "active_exfil" | "single_endpoint"
    correct_action: str                  # what Blue SHOULD do: "approve_then_isolate" | "contain_confirmed_only" | "segment_vlan" | "block_egress_first" | "isolate_immediately"
    risk_level: str = "medium"           # low | medium | high | extreme
    description: str = ""                # IRP source text
    approval_required_from: str = ""     # e.g. "CISO" — who must approve if gate fires
    evidence_impact: str = ""            # good | partial | poor | excellent
    delay_s: int = 180                   # how long the gate delays containment (approval wait)
    score_correct: int = 20              # bonus for following the gate
    score_wrong: int = -10              # penalty for violating it


# The 5 IRP containment decision gates (IRP ch.03 section 3.1)
DEFAULT_DECISION_GATES: list[DecisionGate] = [
    DecisionGate(
        id="gate_single_endpoint", name="Single endpoint — isolate immediately",
        trigger="single_endpoint", correct_action="isolate_immediately",
        risk_level="low", description="Single endpoint with initial foothold only. Isolate via EDR immediately. Preserve memory first (5 min).",
        evidence_impact="good", delay_s=0, score_correct=10, score_wrong=0,
    ),
    DecisionGate(
        id="gate_dc_no_isolate", name="DC compromised — do NOT isolate without CISO",
        trigger="dc_compromised", correct_action="approve_then_isolate",
        risk_level="extreme", description="Do NOT isolate DC without CISO approval — will break all authentication. Block DC from sensitive VLANs instead.",
        approval_required_from="CISO", evidence_impact="excellent", delay_s=180, score_correct=25, score_wrong=-15,
    ),
    DecisionGate(
        id="gate_multi_host", name="Multi-host — contain confirmed only, monitor suspected",
        trigger="multi_host", correct_action="contain_confirmed_only",
        risk_level="medium", description="2+ hosts compromised. Isolate confirmed-compromised hosts. Monitor suspected passively. Do NOT isolate network-wide.",
        evidence_impact="partial", delay_s=0, score_correct=15, score_wrong=-5,
    ),
    DecisionGate(
        id="gate_ransomware_segment", name="Ransomware spreading — emergency VLAN segmentation",
        trigger="ransomware_spreading", correct_action="segment_vlan",
        risk_level="extreme", description="Emergency: segment network immediately. Isolate affected VLAN. Shut down file shares. Prioritise un-encrypted systems.",
        evidence_impact="poor", delay_s=0, score_correct=30, score_wrong=-20,
    ),
    DecisionGate(
        id="gate_exfil_egress_first", name="Active exfil — block egress before touching host",
        trigger="active_exfil", correct_action="block_egress_first",
        risk_level="low", description="Block egress IP/domain at firewall immediately. Do NOT isolate source host until egress is blocked. Notify Privacy Officer — NDB clock may be ticking.",
        evidence_impact="good", delay_s=0, score_correct=20, score_wrong=-10,
    ),
]


class RegulatoryFramework(BaseModel):
    """A regulatory notification obligation triggered by incident type (IRP ch.12)."""
    id: str
    name: str
    jurisdiction: str = ""               # e.g. "Australia", "Global"
    trigger: str                         # what incident type triggers it: "data_breach" | "ransomware" | "critical_infra" | "financial" | "any_material"
    deadline_hours: float                # notification deadline in hours
    recipient: str = ""                  # who must be notified
    format: str = ""                     # how to notify
    penalty: str = ""                    # consequence of non-compliance
    description: str = ""


# The 6 regulatory frameworks from IRP ch.12
REGULATORY_CATALOG: dict[str, RegulatoryFramework] = {
    "ndb": RegulatoryFramework(
        id="ndb", name="Notifiable Data Breaches (NDB) Scheme",
        jurisdiction="Australia", trigger="data_breach", deadline_hours=720,  # 30 days
        recipient="OAIC (Office of the Australian Information Commissioner)",
        format="NDB Statement via OAIC portal + direct notification to affected individuals",
        penalty="Up to AUD $50M per contravention",
        description="Mandatory notification for data breaches likely to result in serious harm. 30-day assessment window.",
    ),
    "apra_cps234": RegulatoryFramework(
        id="apra_cps234", name="APRA CPS 234 (Information Security)",
        jurisdiction="Australia — Financial", trigger="financial", deadline_hours=72,
        recipient="APRA (Australian Prudential Regulation Authority)",
        format="Formal incident notification via APRA Connect",
        penalty="Regulatory sanctions, enforceable undertakings, licence conditions",
        description="APRA-regulated entities must notify within 72 hours of a material information security incident.",
    ),
    "swift_csp": RegulatoryFramework(
        id="swift_csp", name="SWIFT Customer Security Programme",
        jurisdiction="Global — Financial", trigger="financial", deadline_hours=0,  # immediately
        recipient="SWIFT ISAC + local SWIFT representative",
        format="Immediate verbal notification + written follow-up within 24h",
        penalty="Non-compliance may result in removal from SWIFT network",
        description="Any suspected compromise of SWIFT infrastructure requires immediate notification.",
    ),
    "critical_infra": RegulatoryFramework(
        id="critical_infra", name="Critical Infrastructure Act 2018 (SOCI)",
        jurisdiction="Australia", trigger="critical_infra", deadline_hours=12,
        recipient="ACSC / ASD (Australian Signals Directorate)",
        format="Cyber incident report via ReportCyber portal; 12h for critical, 72h for significant",
        penalty="Civil penalties for non-reporting",
        description="Critical infrastructure entities must report significant cyber security incidents within 12-72 hours.",
    ),
    "austrac": RegulatoryFramework(
        id="austrac", name="AUSTRAC AML/CTF Act",
        jurisdiction="Australia — Financial", trigger="financial", deadline_hours=24,  # same day
        recipient="AUSTRAC (Australian Transaction Reports and Analysis Centre)",
        format="Suspicious Matter Report (SMR) via AUSTRAC Online",
        penalty="Up to AUD $22.2M per contravention",
        description="Financial institutions must report suspicious cyber-enabled financial crime same day.",
    ),
    "asx_listing": RegulatoryFramework(
        id="asx_listing", name="ASX Listing Rules 3.1 (Continuous Disclosure)",
        jurisdiction="Australia — Listed entities", trigger="any_material", deadline_hours=0,
        recipient="ASX Market Announcements Platform",
        format="Market-sensitive announcement via ASX Online",
        penalty="Fines, trading halt, class action exposure",
        description="Listed entities must immediately disclose any information that a reasonable person would expect to affect share price.",
    ),
}

# Industry -> suggested frameworks
INDUSTRY_FRAMEWORKS: dict[str, list[str]] = {
    "finance": ["ndb", "apra_cps234", "swift_csp", "austrac", "asx_listing"],
    "manufacturing": ["ndb", "critical_infra"],
    "energy": ["ndb", "critical_infra"],
    "healthcare": ["ndb", "critical_infra"],
    "generic": ["ndb"],
}


class Objectives(BaseModel):
    red: list[str] = Field(default_factory=list)
    blue: list[str] = Field(default_factory=list)


# Default per-actor workflow bindings (a scenario references workflows, never embeds them).
_DEFAULT_BINDINGS = {
    "red": "apt_ransomware_killchain", "soc": "tiered_triage_escalation",
    "blue": "nist_ir_response", "mgmt": "exec_escalation_regulatory", "ot": "ot_safety_ops",
}


class Scenario(BaseModel):
    schema_version: int = 1
    id: str
    name: str
    type: str = "purple"                # red|blue|purple|soc|ics|cloud...
    industry: str = "generic"
    badge: str = "badge-purple"
    label: str = "Purple Team"
    description: str = ""
    difficulties: list[str] = Field(default_factory=lambda: ["Easy", "Medium", "Hard", "Expert"])
    nominal_duration_min: int = 120
    mitre_tactics: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)
    recommended_topology: EnvironmentSpec
    playbook: list[PlaybookStep] = Field(default_factory=list)
    # v2: teams are referenced (Layer 6), not embedded.
    workflow_bindings: dict[str, str] = Field(default_factory=lambda: dict(_DEFAULT_BINDINGS))
    # v2: decision gates — configurable containment IF/THEN branches (IRP ch.03)
    decision_gates: list[DecisionGate] = Field(default_factory=lambda: list(DEFAULT_DECISION_GATES))
    # v2: regulatory frameworks — which notification obligations apply (IRP ch.12)
    regulatory_frameworks: list[str] = Field(default_factory=lambda: ["ndb"])
    objectives: Objectives = Field(default_factory=Objectives)
    report_sections: list[str] = Field(default_factory=lambda: [
        "exec_summary", "timeline", "mitre_map", "scorecard",
        "regulatory_impact", "financial_impact", "recommendations",
        "maturity_score", "corrective_actions",
    ])
