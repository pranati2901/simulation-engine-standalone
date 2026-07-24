"""Mission types — the flow & goals every team operates inside (from cybersecurity-mission-encyclopedia.md §2).

A *mission* drives the whole live match: it sets the Red objective (and therefore the win condition),
how heavily stealth is weighted, the adversary character, the starting state, and the success criteria
each team is graded against. Red attacks toward the mission goal; SOC detects/triages; Blue responds —
all within the mission's flow. Picking a different mission is picking a different game on the same world.

Pure data catalog (the offensive/VALIDATE family). Adding a mission = one entry here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.environment import AssetSpec, ControlSpec, EnvironmentSpec
from app.engine.scenario import Objectives, Scenario


@dataclass(frozen=True)
class MissionType:
    id: str
    name: str
    klass: str                       # encyclopedia class (Validate / Respond ...)
    cadence: str                     # flavour (PROJECT / PERIODIC / EVENT-DRIVEN ...)
    tagline: str
    briefing: str                    # the mission's flow & goal narrative
    primary_objective: str | None    # objective key that becomes the win condition (None = topology headline)
    extra_objectives: tuple[str, ...] = ()
    stealth_weight: float = 1.0      # multiplies Red's stealth bonus + overspend penalty (0 = stealth irrelevant)
    forced_profile: str | None = None
    recommended_profile: str = "nation_state"
    headline_metric: str = ""        # which metric the mission spotlights
    needs: tuple[str, ...] = ()       # asset type_keys the mission ideally wants present
    success: dict = field(default_factory=dict)  # {red, soc, blue} — what winning looks like


def _m(*a, **k) -> MissionType:
    return MissionType(*a, **k)


MISSIONS: list[MissionType] = [
    _m("red_team", "Red Team Operation", "Validate", "PROJECT",
       "Reach a business-impacting objective without being stopped — and measure the defense.",
       "A full-scope, objective-bound, stealthy engagement. Red runs the entire kill-chain toward the "
       "crown-jewel objective while staying under the detection threshold; SOC must catch the quiet "
       "activity; Blue must scope and evict before impact. Stealth is paramount.",
       primary_objective=None, stealth_weight=1.5, recommended_profile="nation_state",
       headline_metric="objective reached + dwell time",
       success={"red": "Reach the objective with minimum footprint",
                "soc": "Detect the quiet intrusion fast (low MTTD)",
                "blue": "Scope fully, then evict completely before impact"}),
    _m("adversary_emulation", "Adversary Emulation", "Validate", "PROJECT",
       "Withstand a specific named threat actor's playbook — fidelity over creativity.",
       "Red stays in character for the chosen adversary profile (the actor IS the mission), even when a "
       "flashier path exists. The question is: can we withstand *this* actor? Coverage is measured "
       "technique-by-technique.",
       primary_objective=None, stealth_weight=1.3, recommended_profile="cybercrime",
       headline_metric="coverage vs. the actor's TTPs",
       success={"red": "Stay in-character; achieve the actor's goal",
                "soc": "Detect the actor's known TTPs",
                "blue": "Respond per the actor's expected behaviour"}),
    _m("pen_test", "Penetration Test", "Validate", "PROJECT",
       "Find and demonstrate as many exploitable weaknesses as possible — breadth over stealth.",
       "Noise is fine; the goal is to prove exploitable issues across the estate. Stealth is NOT scored, "
       "so Red optimises for breadth and depth of findings rather than staying hidden.",
       primary_objective=None, stealth_weight=0.0, recommended_profile="cybercrime",
       headline_metric="breadth of exploitable findings",
       success={"red": "Demonstrate the maximum exploitable impact",
                "soc": "(secondary) note what was detected",
                "blue": "(secondary) note what was contained"}),
    _m("purple_team", "Purple Team Exercise", "Validate", "PERIODIC",
       "Collaboratively build and validate detections for chosen TTPs — coverage is the win.",
       "Red executes openly and SOC/Blue watch the telemetry to build or fix a detection for each "
       "behaviour. The win condition is detection coverage gained, not flags captured — stealth is not "
       "scored.",
       primary_objective=None, stealth_weight=0.0, recommended_profile="cybercrime",
       headline_metric="detection coverage built",
       success={"red": "Exercise each technique transparently",
                "soc": "Achieve high detection coverage of Red's behaviour",
                "blue": "Validate response to each technique"}),
    _m("bas", "Security Validation (BAS)", "Validate", "CONTINUOUS",
       "Continuously verify that controls fire against known techniques.",
       "Red runs through the technique set (best driven on auto-pilot) so the defense can measure control "
       "and detection efficacy end-to-end. Stealth is irrelevant; coverage is everything.",
       primary_objective=None, stealth_weight=0.0, recommended_profile="cybercrime",
       headline_metric="control / detection coverage %",
       success={"red": "Exercise the full technique set",
                "soc": "Measure detection coverage",
                "blue": "Confirm controls and response fire"}),
    _m("ransomware_sim", "Ransomware Simulation", "Validate", "PROJECT",
       "Measure time-to-broad-reach and backup exposure — fast, noisy, no real encryption.",
       "Emulate a RaaS affiliate racing toward broad reach and the backups. The headline is the SOC's "
       "MTTD against a fast actor and whether Blue protects/recovers in time. Impact is a benign marker, "
       "never real encryption.",
       primary_objective="ransomware", stealth_weight=0.5, forced_profile="ransomware",
       recommended_profile="ransomware", headline_metric="MTTD vs. a fast actor + backup survival",
       needs=("file_share",),
       success={"red": "Reach broad impact fast",
                "soc": "Detect the fast actor in time (low MTTD)",
                "blue": "Protect/restore from clean backups; evict"}),
    _m("insider_sim", "Insider Threat Simulation", "Validate", "PROJECT",
       "Test detection of malicious use of *authorised* access — starts inside.",
       "Assumed-breach: Red begins with a valid identity and the internal map, blending with normal work. "
       "There's no perimeter to beat — the whole test is behavioural detection of authorised-but-malicious "
       "activity.",
       primary_objective="exfil", stealth_weight=0.8, forced_profile="insider",
       recommended_profile="insider", headline_metric="behavioural detection of authorised abuse",
       needs=("file_share",),
       success={"red": "Abuse legitimate access to reach the data",
                "soc": "Catch the behavioural anomaly (UEBA/identity)",
                "blue": "Revoke access; confirm no data left"}),
    _m("attack_surface", "Attack Surface Assessment", "Validate", "PERIODIC",
       "Map the external/exposed footprint an adversary could target.",
       "A short, recon-led mission: enumerate the external surface and validate exposed services. The goal "
       "is a complete, prioritised exposure picture — not deep compromise.",
       primary_objective="recon_surface", stealth_weight=0.3, recommended_profile="cybercrime",
       headline_metric="exposure inventory completeness",
       success={"red": "Map and validate the external attack surface",
                "soc": "Notice external recon/scanning",
                "blue": "Reduce the exposed surface"}),
    _m("cloud_assessment", "Cloud Security Assessment", "Validate", "PROJECT",
       "Test the cloud control plane, identity and configuration resilience.",
       "Everything routes through identity and the management plane. Red seeks cloud persistence / "
       "control-plane reach; the defense watches control-plane and identity telemetry.",
       primary_objective="cloud", stealth_weight=1.0, recommended_profile="cybercrime",
       headline_metric="cloud identity / control-plane paths", needs=("cloud",),
       success={"red": "Establish durable cloud control-plane access",
                "soc": "Detect anomalous cloud API / identity use",
                "blue": "Revoke keys/roles; remediate config"}),
    _m("identity_assessment", "Identity Security Assessment", "Validate", "PROJECT",
       "Test the identity attack graph — the path to Tier 0 (Domain Admin).",
       "Identity is the modern perimeter. Red navigates the trust/permission graph toward domain control; "
       "the defense must see and break the path.",
       primary_objective="domain_admin", stealth_weight=1.0, recommended_profile="nation_state",
       headline_metric="shortest path to Tier 0", needs=("domain_controller",),
       success={"red": "Reach Domain Admin / krbtgt",
                "soc": "Detect Kerberoast / DCSync / PtH",
                "blue": "krbtgt ×2; break the trust path"}),
    _m("supply_chain", "Supply Chain Assessment", "Validate", "PROJECT",
       "Test exposure via a trusted third party / supplier as the entry vector.",
       "Entry comes through a trusted supplier relationship rather than a frontal assault. Red leverages "
       "that trust to get in, then pursues the data objective; the defense must catch trust-abuse.",
       primary_objective="exfil", stealth_weight=1.0, recommended_profile="nation_state",
       headline_metric="trust-path blast radius",
       success={"red": "Enter via supplier trust; reach the data",
                "soc": "Detect anomalous third-party trust use",
                "blue": "Revoke the trust path; scope blast radius"}),
    _m("social_eng", "Social Engineering Assessment", "Validate", "PERIODIC",
       "Test the human layer — phishing-led initial access (within ROE).",
       "A short, human-focused mission: the win is whether a pretext lands a foothold. Constructive learning, "
       "not punishment — the defense's job is fast detection of the resulting access.",
       primary_objective="initial_foothold", stealth_weight=0.5, recommended_profile="cybercrime",
       headline_metric="human-layer resilience",
       success={"red": "Land a foothold via the human layer",
                "soc": "Detect the post-phish execution / beacon",
                "blue": "Contain the phished host; reset the user"}),
]
MISSION_BY_ID: dict[str, MissionType] = {m.id: m for m in MISSIONS}
DEFAULT_MISSION = "red_team"


def public(m: MissionType) -> dict:
    return {"id": m.id, "name": m.name, "klass": m.klass, "cadence": m.cadence,
            "tagline": m.tagline, "briefing": m.briefing, "primary_objective": m.primary_objective,
            "stealth_weight": m.stealth_weight, "forced_profile": m.forced_profile,
            "recommended_profile": m.recommended_profile, "headline_metric": m.headline_metric,
            "needs": list(m.needs), "success": dict(m.success)}


# --------------------------------------------------------------------------- #
#  Per-mission environments — each mission is SELF-CONTAINED (no Black Phoenix).
#  Built from the asset/control catalog as composable blocks. (Future: these
#  asset instances get backed by real plugged-in VMs for an accurate sim.)
# --------------------------------------------------------------------------- #
def _a(aid, atype, role=None, zone=None, crit=None) -> AssetSpec:
    return AssetSpec(id=aid, type=atype, role=role, zone=zone, criticality=crit)


# corp foothold terrain + the SOC's own appliances (present in every mission)
_BASE_ASSETS = [
    _a("ws-1", "endpoint", role="primary_endpoint", zone="corp", crit=2),
    _a("ws-2", "endpoint", zone="corp"),
    _a("dc-1", "domain_controller", zone="corp"),
    _a("mail-1", "email_server", zone="corp"),
    _a("siem-1", "siem_platform", zone="soc"),
    _a("edr-1", "edr_platform", zone="soc"),
    _a("fw-1", "firewall", zone="perimeter"),
    _a("vm-1", "vuln_mgmt", zone="soc"),
]
_DATA_ASSETS = [_a("file-1", "file_share", role="sensitive_share", zone="corp", crit=5),
                _a("erp-1", "erp", zone="corp")]
_CLOUD_ASSETS = [_a("cloud-1", "cloud", zone="cloud")]
_OT_ASSETS = [_a("mes-1", "mes", role="it_ot_bridge", zone="ot_dmz"),
              _a("twin-1", "digital_twin", zone="ot_dmz"),
              _a("plc-1", "ot_plc", role="plc", zone="ot")]
_STD_CONTROLS = [ControlSpec(id=f"c-{t}", type=t, enabled=True) for t in
                 ("edr", "siem", "firewall_ids", "segmentation", "dlp", "mfa", "backups", "email_sec")]

# which high-value blocks each mission needs: (data, cloud, ot)
_ENV_BLOCKS: dict[str, tuple[bool, bool, bool]] = {
    "red_team": (True, True, True), "adversary_emulation": (True, True, True),
    "pen_test": (True, True, True), "purple_team": (True, True, True), "bas": (True, True, True),
    "ransomware_sim": (True, False, False), "insider_sim": (True, False, False),
    "supply_chain": (True, False, False),
    "attack_surface": (False, True, False), "cloud_assessment": (False, True, False),
    "identity_assessment": (False, False, False), "social_eng": (False, False, False),
}


def environment_for(mission_id: str) -> EnvironmentSpec:
    data, cloud, ot = _ENV_BLOCKS.get(mission_id, (True, True, True))
    assets = list(_BASE_ASSETS)
    if data:
        assets += _DATA_ASSETS
    if cloud:
        assets += _CLOUD_ASSETS
    if ot:
        assets += _OT_ASSETS
    return EnvironmentSpec(assets=[a.model_copy() for a in assets],
                           controls=[c.model_copy() for c in _STD_CONTROLS])


def scenario_for(mission_id: str) -> Scenario:
    """A lightweight standalone Scenario wrapping a dedicated mission (its own env + goals)."""
    m = MISSION_BY_ID[mission_id]
    return Scenario(
        id=f"mission::{mission_id}", name=m.name, type="red", label="Mission",
        description=m.briefing, recommended_topology=environment_for(mission_id), phases=[],
        objectives=Objectives(red=[v for v in (m.success.get("red"),) if v],
                              blue=[v for v in (m.success.get("blue"),) if v]),
    )
