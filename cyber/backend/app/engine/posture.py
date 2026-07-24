"""Posture — aggregate each team's *enabled* workflow tasks into deterministic modifiers.

Toggling a task on/off changes the Posture, which changes detection latency, prevention,
triage/containment speed, segmentation, persistence survival and recovery — so customizing the
workflows mechanically changes who attacks/defends better. Pure: no RNG, no wall-clock.
"""
from __future__ import annotations

from .workflows import Workflow

# technique key -> family (matches workflows.FAMILIES)
TECHNIQUE_FAMILY: dict[str, str] = {
    "recon_osint": "recon",
    "phishing": "phishing",
    "c2_beacon": "c2",
    "credential_dump": "credaccess", "kerberoasting": "credaccess", "dcsync_domain_admin": "credaccess",
    "lateral_movement": "lateral", "ot_pivot": "lateral",
    "persistence_task": "persistence", "cloud_persistence": "persistence",
    "collection_staging": "exfil", "exfiltration": "exfil",
    "disable_security_tools": "impact", "ransomware": "impact",
    "ot_plc_modify": "ot",
}


def family_of(technique_key: str) -> str:
    return TECHNIQUE_FAMILY.get(technique_key, "all")


class Posture:
    def __init__(self) -> None:
        # defense
        self.detect: dict[str, float] = {}        # family/all -> boost
        self.triage_factor: float = 1.0           # <1 faster
        self.contain_factor: float = 1.0          # <1 faster
        self.containment_enabled: bool = False
        self.evidence_first: bool = False
        self.prevent_egress: bool = False
        self.hunt: bool = False
        self.cred_reset: float = 0.0
        self.segment: bool = False
        self.escalation_quality: bool = False
        self.recovery: bool = False
        self.eradication: float = 0.0
        self.decision_dc: bool = False
        # attacker
        self.evasion: dict[str, float] = {}       # family/all -> latency multiplier (>1 slower)
        self.low_and_slow: float = 1.0
        self.c2_resilience: float = 0.0
        self.persistence_strong: bool = False
        self.phish_potency: int = 0

    # ---- derived helpers ----------------------------------------------------
    def detection_factor(self, family: str) -> float:
        """Multiplier applied to a technique's base detection latency (lower = faster)."""
        slow = self.evasion.get(family, 1.0) * self.evasion.get("all", 1.0) * self.low_and_slow
        boost = self.detect.get(family, 0.0) + self.detect.get("all", 0.0)
        return slow / (1.0 + boost)

    @property
    def eradicates(self) -> bool:
        return (self.eradication + self.cred_reset) >= 1.0


def build_posture(workflows: dict[str, Workflow], enabled: dict[str, set[str]]) -> Posture:
    p = Posture()
    for actor, wf in workflows.items():
        on = enabled.get(actor)
        for step in wf.steps:
            if on is not None and step.id not in on:
                continue
            if on is None and not step.default_enabled:
                continue
            for eff in step.effects:
                _apply(p, eff.kind, eff.scope, eff.magnitude)
    return p


def _apply(p: Posture, kind: str, scope: str | None, mag: float) -> None:
    fam = scope or "all"
    if kind == "detect":
        p.detect[fam] = p.detect.get(fam, 0.0) + mag
    elif kind == "triage_speed":
        p.triage_factor *= mag
    elif kind == "contain_speed":
        p.contain_factor *= mag
    elif kind == "containment_enable":
        p.containment_enabled = True
    elif kind == "evidence_first":
        p.evidence_first = True
    elif kind == "prevent_egress":
        p.prevent_egress = True
    elif kind == "hunt":
        p.hunt = True
    elif kind == "cred_reset":
        p.cred_reset += mag
    elif kind == "segment":
        p.segment = True
    elif kind == "escalation_quality":
        p.escalation_quality = True
    elif kind == "recovery":
        p.recovery = True
    elif kind == "eradication":
        p.eradication += mag
    elif kind == "decision_gate":
        p.decision_dc = True
    elif kind == "evasion":
        p.evasion[fam] = p.evasion.get(fam, 1.0) * mag
    elif kind == "low_and_slow":
        p.low_and_slow *= mag
    elif kind == "c2_resilience":
        p.c2_resilience += mag
    elif kind == "persistence_strong":
        p.persistence_strong = True
    elif kind == "phish_potency":
        p.phish_potency += int(mag)
