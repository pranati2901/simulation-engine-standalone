"""The Blue operator's lifecycle as data — the guided defensive action space.

Mirror of `red_playbook.py`, modelled on `blue-team-masterclass.md`: the defensive lifecycle
(Prepare → See → Decide → Act → Learn, §3), the appendix decision-checklist (triage →
scope-before-contain → evict completely → recover clean → stay vigilant), risk-based prioritisation
(§11) and identity-centric defense (§13). Each action declares preconditions, world effects that
*hinder Red on the shared World* (isolate footholds, block egress, reset creds, segment, eradicate
persistence, restore), a framework ref and a defender note.

Pure catalog + helpers — depends only on the engine's World/enums. The session interprets it.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.engine.enums import SecurityState
from app.engine.models.assets import get_asset_type
from app.engine.world import AssetInstance, World


# --------------------------------------------------------------------------- #
#  Lifecycle stages (Masterclass §3 — Prepare → See → Decide → Act → Learn)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BlueStage:
    id: str
    name: str
    summary: str
    ref: str


BLUE_STAGES: list[BlueStage] = [
    BlueStage("prepare", "Preparation", "Harden, pre-authorise response, isolate backups — the biggest determinant of IR success.", "§2 / §10.1"),
    BlueStage("see", "Visibility & Detection", "Turn on the telemetry/detections that make Red's behaviour visible. A blind spot is an invitation.", "§6 / §7"),
    BlueStage("decide", "Triage & Investigation", "Triage by asset criticality, then SCOPE fully before you act.", "§3.8–3.9 / §11"),
    BlueStage("hunt", "Threat Hunting", "Assume breach — find footholds & persistence that didn't alert.", "§9"),
    BlueStage("contain", "Containment", "Sever ALL footholds at once; block C2/egress; segment. Don't tip Red off mid-scope.", "§3.12 / §11.2"),
    BlueStage("eradicate", "Eradication", "Remove every foothold, persistence mechanism and stolen credential. Close the vector.", "§3.13"),
    BlueStage("recover", "Recovery & Validation", "Restore from clean, immutable backups; verify; raise vigilance for re-entry.", "§3.14–3.15 / §15"),
    BlueStage("learn", "Lessons Learned", "Convert the incident into a durable improvement; conclude the operation.", "§3.16"),
]
BLUE_STAGE_INDEX = {s.id: i for i, s in enumerate(BLUE_STAGES)}


# --------------------------------------------------------------------------- #
#  Detection coverage — which Red telemetry Blue can see (Masterclass §6)
# --------------------------------------------------------------------------- #
# Red action `watched_by` control types -> Blue monitoring domain.
WATCH_TO_DOMAIN = {"edr": "endpoint", "siem": "siem", "firewall_ids": "network",
                   "dlp": "data", "email_sec": "email"}
# Identity monitoring (ITDR) covers the identity-centric tactics regardless of control type.
IDENTITY_TACTICS = {"Credential Access", "Privilege Escalation",
                    "Lateral Movement", "Lateral Movement (ICS)"}


def detects(watched_by: tuple[str, ...], tactic: str, world: World,
            target: AssetInstance | None, monitoring: set[str]) -> bool:
    """Does Blue have coverage for a Red action? (environment controls OR enabled monitoring)."""
    for ct in watched_by:
        if target is not None and world.active_control_for(target, ct) is not None:
            return True
        if world.active_global_control(ct) is not None:
            return True
        if WATCH_TO_DOMAIN.get(ct) in monitoring:
            return True
    if tactic in IDENTITY_TACTICS and "identity" in monitoring:
        return True
    return False


# --------------------------------------------------------------------------- #
#  Actions
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BlueAction:
    id: str
    stage: str
    label: str
    description: str
    framework: str = ""                  # NIST/SANS/masterclass ref
    requires: tuple[str, ...] = ()
    target_mode: str = "none"            # none | select
    target_type: str | None = None       # asset type filter for select
    target_filter: str = ""              # compromised | down | contained
    effects: tuple[str, ...] = ()        # see session._apply_blue_effects
    score: int = 10
    note: str = ""                       # the masterclass defender wisdom
    once: bool = True


def _b(*args, **kw) -> BlueAction:
    return BlueAction(*args, **kw)


BLUE_ACTIONS: list[BlueAction] = [
    # -- Preparation -------------------------------------------------------- #
    _b("prepare.playbooks", "prepare", "Ready playbooks & pre-authorise containment",
       "Pre-agreed, pre-authorised response so you're not negotiating permissions mid-incident.",
       "§10.1", effects=("cap:pre_auth",), score=10,
       note="The single biggest determinant of IR success is preparation."),
    _b("prepare.backups", "prepare", "Isolate & test immutable backups",
       "Backups that are isolated, immutable and tested — the crux of ransomware survival.",
       "§15", effects=("cap:backups",), score=12,
       note="A backup you've never restored from is a hope, not a backup."),
    _b("prepare.harden", "prepare", "Harden: MFA, patch edge, least privilege",
       "Shrink the attack surface — phishing-resistant MFA and patched internet-facing systems.",
       "§3.4 / §13", effects=("cap:hardened",), score=12,
       note="The most repeated breach root cause is an unpatched edge or missing MFA."),
    _b("prepare.tiering", "prepare", "Tier admin access (PAM)",
       "Separate Tier-0 admin identities so privileged creds never land on general endpoints.",
       "§13.1", effects=("cap:tiering",), score=10,
       note="Tiered administration directly breaks the attacker's escalation path."),

    # -- Visibility & detection --------------------------------------------- #
    _b("see.edr", "see", "Deploy endpoint monitoring (EDR/Sysmon)",
       "Process lineage, LSASS access, persistence — where execution & credential theft show up.",
       "§6.2", effects=("monitor:endpoint",), score=10,
       note="Endpoint + identity telemetry lights up the most attack paths."),
    _b("see.identity", "see", "Enable identity monitoring (ITDR)",
       "Anomalous auth, ticket/token abuse, privilege change — identity is the modern perimeter.",
       "§13.1", effects=("monitor:identity",), score=12,
       note="Many modern intrusions are actually caught in identity behaviour."),
    _b("see.siem", "see", "Centralise logs + correlation (SIEM)",
       "The investigative backbone — correlate across the estate.", "§6.4",
       effects=("monitor:siem",), score=10, note="Correlation turns isolated signals into a story."),
    _b("see.network", "see", "Network detection (NDR / DNS / firewall)",
       "East-west movement, beaconing, exfiltration — catches what endpoints miss.", "§6.2",
       effects=("monitor:network",), score=10, note="NDR sees the unmanaged devices EDR can't."),
    _b("see.data", "see", "Data monitoring (DLP)",
       "Anomalous access volume and data movement on the crown jewels.", "§6.2",
       effects=("monitor:data",), score=10, note="Watch the data layer — that's the objective."),
    _b("see.health", "see", "Monitor the health of your monitoring",
       "Catch broken pipelines and dead sensors before an intrusion hides in the gap.", "§6.4",
       effects=("cap:monitor_health",), score=8,
       note="A silently-dead sensor is exactly where months of dwell time live."),

    # -- Triage & investigation --------------------------------------------- #
    _b("triage.prioritize", "decide", "Triage by asset criticality & intent",
       "Rank the queue by severity × asset value × adversary intent — DC alerts outrank a hundred endpoints.",
       "§11.2", effects=("cap:triage",), score=8,
       note="Priority = severity × asset criticality × adversary intent."),
    _b("investigate.scope", "decide", "Investigate & scope the full intrusion",
       "Pivot across telemetry to find EVERY foothold and the spread BEFORE containing.",
       "§3.9 / §11.2", requires=("compromised_exists",), effects=("cap:scoped",), score=18,
       note="Scope before you contain — or you tip Red off and miss footholds."),

    # -- Threat hunting ----------------------------------------------------- #
    _b("hunt.persistence", "hunt", "Hunt for persistence & rogue accounts",
       "Assume breach — find the persistence the alerts missed so eradication can be complete.",
       "§9", effects=("cap:hunted",), score=16,
       note="A hunt that finds nothing still finds a visibility gap."),

    # -- Containment -------------------------------------------------------- #
    _b("contain.isolate", "contain", "EDR-isolate a compromised host",
       "Network-contain a confirmed-compromised host (preserves forensic telemetry).",
       "§3.12", requires=("compromised_exists",), target_mode="select", target_filter="compromised",
       effects=("isolate",), score=20, once=False,
       note="Sever all known footholds at once — partial containment lets Red dig in."),
    _b("contain.dc_gate", "contain", "DC decision gate: block VLANs, don't break auth",
       "For a domain controller, block it from sensitive VLANs with CISO approval — do NOT isolate "
       "it outright (that breaks all authentication).", "§11.2", effects=("cap:dc_gate",), score=15,
       note="Isolating a DC without approval breaks the business — gate it first."),
    _b("contain.block_egress", "contain", "Block egress at firewall + DNS sinkhole",
       "Cut C2 and exfiltration channels — before dealing with the host if exfil is active.",
       "§3.12", effects=("flag:egress_blocked",), score=18,
       note="Block egress first when exfil is in progress; the NDB clock may be ticking."),
    _b("contain.disable_accounts", "contain", "Disable / reset compromised accounts",
       "Disable (not just reset) the accounts Red is moving with — drops stolen privilege.",
       "§3.13 / §13", effects=("creds_reset",), score=16,
       note="A compromised identity is the attacker's reach — revoke it."),
    _b("contain.segment", "contain", "Emergency VLAN segmentation",
       "Block cross-zone lateral movement and the IT→OT pivot.", "§2.2 / §3.12",
       effects=("flag:segmentation_active",), score=18,
       note="Segmentation is the single most consequential blast-radius control."),

    # -- Eradication -------------------------------------------------------- #
    _b("eradicate.persistence", "eradicate", "Remove all persistence (full IOC sweep)",
       "Enumerate and remove every persistence mechanism so Red can't re-establish.", "§3.13",
       requires=("persistence_exists",), effects=("eradicate_persistence",), score=20,
       note="You can only eradicate what you scoped/hunted — completeness is everything."),
    _b("eradicate.krbtgt", "eradicate", "krbtgt reset ×2 + domain-wide reset",
       "Invalidate Golden Tickets and stolen domain credentials after a domain compromise.",
       "§13", effects=("eradicate_domain",), score=20,
       note="Without krbtgt ×2, domain persistence survives every other eviction."),
    _b("eradicate.reimage", "eradicate", "Reimage contained hosts & close the vector",
       "Rebuild from a clean baseline and patch the initial-access vector.", "§3.13",
       requires=("contained_exists",), target_mode="select", target_filter="contained",
       effects=("reimage",), score=12, once=False, note="Rebuild beats clean when you can't be sure."),

    # -- Recovery & validation ---------------------------------------------- #
    _b("recover.restore", "recover", "Restore impacted systems from clean backups",
       "Bring down/encrypted systems back from isolated, verified-clean backups.", "§15",
       requires=("cap:backups", "down_exists"), target_mode="select", target_filter="down",
       effects=("restore",), score=15, once=False, note="Restore only from known-clean state — verify first."),
    _b("recover.validate", "recover", "Validate eviction & raise vigilance",
       "Heightened monitoring and targeted hunting for re-entry — adversaries pre-plan it.",
       "§3.15", effects=("cap:validated",), score=12,
       note="Post-incident is when vigilance must increase, not relax."),

    # -- Lessons learned ---------------------------------------------------- #
    _b("learn.aar", "learn", "Lessons learned & conclude the operation",
       "Blameless post-incident review; ship the new detection/control; conclude.", "§3.16",
       effects=("conclude",), score=0, note="Every miss becomes a new detection. Then stop."),
]
BLUE_ACTIONS_BY_ID: dict[str, BlueAction] = {a.id: a for a in BLUE_ACTIONS}


# --------------------------------------------------------------------------- #
#  Availability & targets (pure functions of blue-state + world)
# --------------------------------------------------------------------------- #
def _matches_type(asset: AssetInstance, target_type: str | None) -> bool:
    if not target_type:
        return True
    wanted = {t.strip() for t in target_type.split(",")}
    if asset.type_key in wanted:
        return True
    try:
        return get_asset_type(asset.type_key).CATEGORY.value in wanted
    except Exception:
        return False


def _passes_filter(asset: AssetInstance, target_filter: str, world: World) -> bool:
    if target_filter == "compromised":
        return asset.security_state == SecurityState.COMPROMISED
    if target_filter == "contained":
        return asset.security_state == SecurityState.CONTAINED
    if target_filter == "down":
        return asset.health.value == "down"
    return True


def _req_ok(req: str, bs, world: World) -> bool:
    a = world.attacker
    if req == "compromised_exists":
        return any(x.security_state == SecurityState.COMPROMISED for x in world.all_assets())
    if req == "foothold_exists":
        return a.has_foothold()
    if req == "down_exists":
        return any(x.health.value == "down" for x in world.all_assets())
    if req == "contained_exists":
        return any(x.security_state == SecurityState.CONTAINED for x in world.all_assets())
    if req == "persistence_exists":
        return any(a.flags.get(k) for k in ("persistence", "persistence_strong", "cloud_persistence"))
    if req.startswith("cap:"):
        return req.split(":", 1)[1] in bs.capabilities
    return True


def is_available(action: BlueAction, bs, world: World) -> tuple[bool, str]:
    if action.once and action.id in bs.done_actions:
        return False, "already done"
    for req in action.requires:
        if not _req_ok(req, bs, world):
            return False, _req_reason(req)
    if action.target_mode == "select" and not valid_targets(action, bs, world):
        return False, "no matching asset right now"
    return True, ""


def _req_reason(req: str) -> str:
    pretty = {
        "compromised_exists": "no compromised host detected yet",
        "down_exists": "nothing is down to restore",
        "contained_exists": "contain a host first",
        "persistence_exists": "no persistence found yet (hunt/scope first)",
        "cap:backups": "prepare isolated backups first",
    }
    return pretty.get(req, f"requires {req}")


def valid_targets(action: BlueAction, bs, world: World) -> list[AssetInstance]:
    if action.target_mode != "select":
        return []
    return [a for a in world.all_assets()
            if _matches_type(a, action.target_type) and _passes_filter(a, action.target_filter, world)]
