"""The Red operator's lifecycle as data — the guided, mission-oriented action space.

This is the catalog a human Red player drives through, modelled directly on
`red-team-masterclass.md`: the operational lifecycle (Section 3), the detection-risk *budget*
(Section 7.4), objective-first navigation (Section 7.3), graduated/quiet tradecraft, and adversary
profiles (Section 13). Each action declares lifecycle preconditions, a noise (detection-risk) cost,
world effects, fog-of-war reveals and an OPSEC note. The engine (live/session.py) interprets these
generically — adding an action = adding an entry here, exactly like the technique catalog.

Pure catalog + helpers: depends only on the engine's World/enums, never on the session, so it stays
reusable and a future AIDriver can consume the same action space + guardrails.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.enums import CredScope
from app.engine.models.assets import get_asset_type
from app.engine.world import AssetInstance, World


# --------------------------------------------------------------------------- #
#  Lifecycle stages (Masterclass §3 — the operational lifecycle, with loops)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RedStage:
    id: str
    name: str
    summary: str
    ref: str  # masterclass section


RED_STAGES: list[RedStage] = [
    RedStage("planning", "Planning", "Lock the objective, ROE and adversary profile before acting.", "§2"),
    RedStage("recon", "Reconnaissance", "Build the external picture to answer your PIRs — quiet first.", "§3.2 / §5"),
    RedStage("weaponize", "Weaponise & Infra", "Stand up resilient, deniable C2 and a delivery lure.", "§3.4 / §14"),
    RedStage("initial_access", "Initial Access", "Establish the first foothold — pick the vector by landing position, not ease.", "§3.5 / §6"),
    RedStage("foothold", "Foothold", "Stabilise C2 and characterise the defences before making noise.", "§3.6"),
    RedStage("internal_recon", "Internal Recon", "Map identity & trust from the inside; find the path to the objective.", "§3.7"),
    RedStage("privilege", "Privilege & Credentials", "Acquire *just enough* privilege; identity is the currency.", "§3.8–3.9 / §10"),
    RedStage("lateral", "Lateral Movement", "Traverse trust toward the objective — every hop must be justified.", "§3.10 / §11"),
    RedStage("persistence", "Persistence", "Retain access proportional to need; layered persistence tests eviction.", "§3.11 / §12"),
    RedStage("evasion", "Defense Evasion & C2", "Continuous: operate in the defender's blind spots; keep C2 resilient.", "§3.12–3.13 / §9"),
    RedStage("impact", "Objective & Impact", "Demonstrate the consequence — then STOP. Prove, don't cause harm.", "§3.14 / §18.3"),
]
STAGE_INDEX = {s.id: i for i, s in enumerate(RED_STAGES)}


# --------------------------------------------------------------------------- #
#  Adversary profiles (Masterclass §13) — set noise budget + character
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class AdversaryProfile:
    id: str
    name: str
    description: str
    budget: int                 # detection-risk budget (Masterclass §7.4)
    overspend_penalty: float    # score lost per noise point spent beyond budget
    assumed_breach: bool = False
    traits: tuple[str, ...] = ()


ADVERSARY_PROFILES: list[AdversaryProfile] = [
    AdversaryProfile(
        "nation_state", "Nation-state (espionage)",
        "Patient and very quiet. Large noise budget, but staying unseen is the point — "
        "overspending is heavily punished.", budget=220, overspend_penalty=3.0,
        traits=("patient", "stealth", "custom-tradecraft")),
    AdversaryProfile(
        "ransomware", "Ransomware (RaaS affiliate)",
        "Smash-and-grab. Small budget and noisier by nature; speed-to-impact matters more than "
        "stealth, so overspend is only lightly punished.", budget=95, overspend_penalty=0.6,
        traits=("fast", "noisy", "targets-backups")),
    AdversaryProfile(
        "cybercrime", "Cybercrime (commodity)",
        "Opportunistic, tooling-heavy, moderate budget. Abandons hard targets.",
        budget=130, overspend_penalty=1.2, traits=("opportunistic", "off-the-shelf")),
    AdversaryProfile(
        "insider", "Insider threat (assumed breach)",
        "Starts inside with valid access and an internal map. Blends with normal — extremely low "
        "noise floor; the test is behavioural detection.", budget=170, overspend_penalty=2.0,
        assumed_breach=True, traits=("trusted", "blends-in")),
]
PROFILE_BY_ID = {p.id: p for p in ADVERSARY_PROFILES}
DEFAULT_PROFILE = "nation_state"


# --------------------------------------------------------------------------- #
#  Actions — the Red operator's choices per stage
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RedAction:
    id: str
    stage: str
    label: str
    description: str
    tactic: str
    mitre: str = ""
    noise: int = 1                      # base detection-risk cost (Masterclass §7.4)
    requires: tuple[str, ...] = ()      # lifecycle/world preconditions (see _req_ok)
    target_mode: str = "none"           # none | auto | select
    target_type: str | None = None      # comma-separated asset type_keys / categories
    effects: tuple[str, ...] = ()       # effect specs (see session._apply_effects)
    intel: str = ""                     # operational intel revealed on success
    objective: str | None = None        # objective key this contributes to
    watched_by: tuple[str, ...] = ()    # control types that would raise exposure
    score: int = 10
    opsec: str = ""                     # the masterclass "what it costs if seen" note
    once: bool = True                   # repeatable when False (e.g. lateral hops)


def _a(*args, **kw) -> RedAction:
    return RedAction(*args, **kw)


RED_ACTIONS: list[RedAction] = [
    # -- Planning ----------------------------------------------------------- #
    _a("plan.review", "planning", "Define objective, ROE & PIRs",
       "Lock the mission's end-state and the intelligence questions recon must answer. "
       "Slow is smooth; smooth is fast.", "Planning", noise=0, requires=(),
       effects=("progress:planned", "reveal:external"),
       intel="Objective, success criteria and PIRs locked. External surface in view.",
       score=5, opsec="Costs nothing and frames every later decision."),

    # -- Reconnaissance ----------------------------------------------------- #
    _a("recon.osint", "recon", "Passive OSINT & identity harvest",
       "Org footprint, employees, tech fingerprints, leaked creds — all passive, all legal-adjacent.",
       "Reconnaissance", mitre="T1591/T1589", noise=2, requires=("planned",),
       effects=("progress:recon_done", "reveal:external"),
       intel="Employee personas, tech stack and an SSO/identity provider identified — strategy shifts toward identity.",
       watched_by=(), score=12, opsec="Quietest, highest-value recon. Do this first."),
    _a("recon.fingerprint", "recon", "Active service fingerprinting",
       "Light, controlled probing of exposed services to validate findings — louder than passive.",
       "Reconnaissance", mitre="T1595", noise=6, requires=("recon_done",),
       effects=("progress:surface", "reveal:type:email_server,cloud,server"),
       intel="Exposed services and an internet-facing application validated as a candidate vector.",
       watched_by=("firewall_ids",), score=10,
       opsec="Active scanning can tip off a perimeter SOC before you've even started."),
    _a("recon.supply_chain", "recon", "Map suppliers & trust relationships",
       "Identify third parties and acquisitions whose trust you can borrow (classic seams).",
       "Reconnaissance", mitre="T1591.002", noise=1, requires=("recon_done",),
       effects=("progress:supply",),
       intel="A recently-acquired subsidiary trusts the parent identity but is less monitored — a seam.",
       score=10, opsec="Pure OSINT; reveals weak trust boundaries to abuse later."),

    # -- Weaponise & infrastructure ---------------------------------------- #
    _a("infra.c2", "weaponize", "Stand up resilient C2 + redirectors",
       "Tiered, deniable C2 designed to blend with normal traffic and survive partial discovery.",
       "Resource Development", mitre="T1583", noise=0, requires=("recon_done",),
       effects=("progress:c2_ready", "flag:c2"),
       intel="C2 infrastructure live behind redirectors; channels chosen to match the adversary profile.",
       score=8, opsec="Offline prep — invisible to the target until you call back."),
    _a("infra.lure", "weaponize", "Build look-alike domain + delivery lure",
       "Delayed-macro / HTML-smuggling lure designed to bypass commodity email filtering.",
       "Resource Development", mitre="T1583.001", noise=0, requires=("recon_done",),
       effects=("progress:weaponized",),
       intel="Weaponised lure prepared against a trusted-supplier pretext.",
       score=8, opsec="Built off-target; only becomes evidence once delivered."),

    # -- Initial access (pick a vector by landing position, not ease) -------- #
    _a("access.valid_creds", "initial_access", "Log in with harvested valid credentials",
       "Use legitimate authentication material from prior intel — the quietest, most real-adversary path.",
       "Initial Access", mitre="T1078", noise=2, requires=("recon_done",),
       target_mode="auto", target_type="endpoint",
       effects=("compromise", "creds:user", "flag:c2", "progress:foothold", "reveal:foothold"),
       intel="Authenticated as a real user — blends with normal logons.",
       watched_by=("siem",), score=45, objective=None,
       opsec="Valid accounts are the lowest-noise entry; favoured by mature actors."),
    _a("access.phish", "initial_access", "Spear-phish a user → execute → beacon",
       "Deliver the lure, the user executes, a beacon calls back and migrates to a stable process.",
       "Initial Access", mitre="T1566.001", noise=6, requires=("weaponized", "c2_ready"),
       target_mode="auto", target_type="endpoint",
       effects=("compromise", "creds:user", "flag:c2", "progress:foothold", "reveal:foothold"),
       intel="Beacon stable on a user endpoint (low privilege) — a beachhead, not the objective.",
       watched_by=("email_sec", "edr"), score=50,
       opsec="Office→PowerShell is a classic detectable chain; potent but loud."),
    _a("access.exposed_service", "initial_access", "Exploit an exposed internet-facing service",
       "Leverage a weakness in a perimeter service — lands you on a server, but it's noisy.",
       "Initial Access", mitre="T1190", noise=8, requires=("surface",),
       target_mode="select", target_type="server,email_server,cloud",
       effects=("compromise", "creds:user", "flag:c2", "progress:foothold", "reveal:foothold"),
       intel="Foothold on an exposed server in the perimeter/DMZ.",
       watched_by=("firewall_ids", "edr"), score=45,
       opsec="Exploitation is the loudest entry — only when the landing position justifies it."),

    # -- Foothold establishment -------------------------------------------- #
    _a("foothold.stabilize", "foothold", "Migrate to stable process / resilient C2",
       "Make access survivable before doing anything risky.", "Defense Evasion", mitre="T1055",
       noise=2, requires=("foothold",), effects=("progress:stable", "flag:c2_active"),
       intel="Operating from a stable, survivable position with reliable C2.",
       watched_by=("edr",), score=12, opsec="Process injection can flag EDR; worth it for stability."),
    _a("foothold.characterize", "foothold", "Characterise the defensive tooling",
       "Quietly observe what's watching (EDR/logging presence) before making noise.",
       "Discovery", mitre="T1518.001", noise=1, requires=("foothold",),
       effects=("progress:char",),
       intel="Defensive tooling on the host enumerated — you now know what each later action costs.",
       watched_by=(), score=10, opsec="Empathy for the defender's visibility, turned to advantage."),

    # -- Internal reconnaissance ------------------------------------------- #
    _a("intrecon.host", "internal_recon", "Local host & session recon",
       "Read what's already visible from the foothold — users, sessions, software.",
       "Discovery", mitre="T1033/T1057", noise=2, requires=("foothold",),
       effects=("progress:host_recon",),
       intel="Local context mapped; cached sessions and software inventoried.",
       watched_by=("edr",), score=10, opsec="Low noise if you read rather than broadly enumerate."),
    _a("intrecon.identity_graph", "internal_recon", "Map the identity / trust graph",
       "Who can become whom? Build the 'shortest path to the objective' over trust, not topology.",
       "Discovery", mitre="T1482/T1069", noise=4, requires=("foothold",),
       effects=("progress:internal_recon_done", "reveal:internal"),
       intel="Identity graph built — the specific admin identity the objective trusts is identified.",
       watched_by=("siem",), score=18,
       opsec="Directory queries are detectable behaviour — targeted beats broad."),
    _a("intrecon.network", "internal_recon", "Network & segmentation discovery",
       "Map reachability and where segmentation is weak — noisier than identity work.",
       "Discovery", mitre="T1046/T1018", noise=6, requires=("foothold",),
       effects=("progress:internal_recon_done", "reveal:internal"),
       intel="Reachable hosts and weak segmentation boundaries identified.",
       watched_by=("siem", "firewall_ids"), score=12,
       opsec="Broad scanning lights up behavioural analytics — budget it carefully."),

    # -- Privilege escalation & credential access -------------------------- #
    _a("privesc.abuse_delegation", "privilege", "Abuse a legitimate admin path",
       "Misconfigured delegation / over-broad group — become privileged via a *legitimate* route.",
       "Privilege Escalation", mitre="T1078", noise=3, requires=("internal_recon_done", "creds:user"),
       effects=("creds:privileged",),
       intel="Privileged context obtained by abusing misplaced trust — quieter than exploitation.",
       watched_by=("siem",), score=55,
       opsec="Escalation is graph navigation over trust, not a pile of exploits."),
    _a("cred.lsass", "privilege", "Dump credentials from memory (LSASS)",
       "Harvest cached credentials from the foothold to escalate.", "Credential Access",
       mitre="T1003.001", noise=6, requires=("foothold",), effects=("creds:privileged",),
       intel="Privileged credentials harvested from host memory.",
       watched_by=("edr",), score=55, opsec="LSASS access by a non-system process is a strong EDR signal."),
    _a("cred.kerberoast", "privilege", "Kerberoast service accounts",
       "Request and crack service tickets to obtain service-account credentials.",
       "Credential Access", mitre="T1558.003", noise=4, requires=("foothold",),
       target_mode="select", target_type="domain_controller", effects=("creds:privileged",),
       intel="Service-account credentials recovered offline.",
       watched_by=("siem",), score=55, opsec="Cracking is offline; the TGS requests are the only tell."),
    _a("cred.dcsync", "privilege", "DCSync — replicate domain secrets",
       "Impersonate a DC to pull domain hashes incl. krbtgt → Domain Admin.", "Credential Access",
       mitre="T1003.006", noise=8, requires=("creds:privileged",),
       target_mode="select", target_type="domain_controller",
       effects=("creds:domain_admin", "compromise", "flag:domain_compromise"),
       intel="krbtgt obtained — effective control of the identity plane.", objective="domain_admin",
       watched_by=("siem", "edr"), score=100,
       opsec="DCSync from a non-DC is a high-fidelity, late-game spend."),

    # -- Lateral movement (repeatable; every hop justified) ---------------- #
    _a("lateral.move", "lateral", "Lateral movement to a chosen host",
       "Move as a trusted identity toward the objective — using the most legitimate method available.",
       "Lateral Movement", mitre="T1021", noise=4, requires=("creds:privileged", "reachable"),
       target_mode="select", target_type="server,domain_controller,file_share,erp,mes,endpoint",
       effects=("compromise", "reveal:asset"),
       intel="New foothold established one hop closer to the objective.",
       watched_by=("siem", "edr"), score=35, once=False,
       opsec="Movement for movement's sake is detection risk for no gain."),
    _a("lateral.pivot_ot", "lateral", "Pivot across the IT/OT boundary",
       "Cross from IT into the OT/MES network — the boundary is the headline control.",
       "Lateral Movement (ICS)", mitre="T0866", noise=6, requires=("foothold", "reachable"),
       target_mode="select", target_type="mes",
       effects=("compromise", "flag:in_ot", "reveal:zone:ot,ot_dmz"),
       intel="Reached the OT/MES segment — PLCs are now in reach.",
       watched_by=("siem",), score=80,
       opsec="If IT↔OT is segmented, this is exactly where you get stopped."),

    # -- Persistence ------------------------------------------------------- #
    _a("persist.task", "persistence", "Scheduled task / service persistence",
       "Survive reboots and routine churn during the operation.", "Persistence", mitre="T1053.005",
       noise=3, requires=("foothold",), effects=("flag:persistence",),
       intel="Operational persistence planted on the foothold.",
       watched_by=("edr",), score=40, opsec="Persistence is among the most-hunted artifacts."),
    _a("persist.golden_ticket", "persistence", "Forge a Golden Ticket",
       "Mint TGTs from krbtgt — durable identity persistence until krbtgt is reset twice.",
       "Persistence", mitre="T1558.001", noise=4, requires=("creds:domain_admin",),
       effects=("flag:persistence", "flag:persistence_strong"),
       intel="Golden Ticket forged — re-entry survives most eviction attempts.",
       watched_by=("siem",), score=55, opsec="Strategic persistence that tests eviction completeness."),
    _a("persist.cloud", "persistence", "Cloud account / app persistence",
       "Add a cloud identity or app credential for trusted, legitimate-looking re-entry.",
       "Persistence", mitre="T1136.003", noise=3, requires=("creds:privileged",),
       target_mode="select", target_type="cloud", effects=("flag:cloud_persistence",),
       intel="Cloud persistence established via a new trusted identity.",
       watched_by=("siem",), score=45, opsec="Cloud identity persistence often outlives on-prem eviction."),
    _a("persist.reestablish", "persistence", "Re-establish access via persistence",
       "Blue contained a host but didn't eradicate your persistence — call back in and retake it.",
       "Persistence", mitre="T1547", noise=4, requires=("contained_persistent",),
       target_mode="select", effects=("compromise",),
       intel="Foothold re-established after containment — eradication was incomplete.",
       watched_by=("edr",), score=30, once=False,
       opsec="Layered persistence specifically tests whether Blue evicts completely."),

    # -- Defense evasion & C2 (continuous) --------------------------------- #
    _a("evade.amsi", "evasion", "AMSI bypass + in-memory tradecraft",
       "Reduce the telemetry your subsequent actions generate.", "Defense Evasion",
       mitre="T1562.001", noise=1, requires=("foothold",), effects=("evasion:0.15",),
       intel="Subsequent actions now generate less endpoint telemetry.",
       score=10, opsec="Lowers your per-action noise floor — spend the small cost early."),
    _a("evade.low_slow", "evasion", "Operate low & slow",
       "Pace actions to dodge velocity-based correlation; trades tempo for stealth.",
       "Defense Evasion", mitre="T1029", noise=1, requires=("foothold",), effects=("evasion:0.2",),
       intel="Cadence slowed; velocity-based SIEM rules are less likely to correlate you.",
       score=10, opsec="Patience is tradecraft — time does the work the noise can't."),
    _a("c2.fallback", "evasion", "Add DNS-over-HTTPS fallback C2",
       "A redundant channel that survives a primary C2 block.", "Command and Control",
       mitre="T1071.004", noise=0, requires=("c2_ready",), effects=("resilience",),
       intel="Redundant C2 channel staged — a single block won't sever control.",
       score=8, opsec="Compartmentalised infra; discovery of one channel doesn't unravel all."),

    # -- Collection & exfiltration ----------------------------------------- #
    _a("collect.stage", "impact", "Collect & stage target data",
       "Locate and stage the objective data set for exfiltration.", "Collection", mitre="T1074",
       noise=3, requires=("foothold", "reachable"),
       target_mode="select", target_type="file_share,erp", effects=("flag:staged",),
       intel="Target data identified and staged for exfil.",
       watched_by=("dlp",), score=30, opsec="Mass reads of a file share can trip DLP thresholds."),
    _a("exfil.dns", "impact", "Exfiltrate over a covert DNS channel",
       "Slow, quiet exfiltration that blends into DNS noise.", "Exfiltration", mitre="T1048.001",
       noise=4, requires=("staged",), effects=("flag:exfiltrated", "exfiltrate"),
       intel="Target data exfiltrated over a low-and-slow channel.", objective="exfil",
       watched_by=("siem",), score=110, opsec="Quieter than bulk cloud upload; slower but safer."),
    _a("exfil.cloud", "impact", "Exfiltrate to cloud storage",
       "Fast bulk exfiltration to a cloud bucket — high volume, higher noise.", "Exfiltration",
       mitre="T1567.002", noise=7, requires=("staged",), effects=("flag:exfiltrated", "exfiltrate"),
       intel="Target data exfiltrated to attacker-controlled cloud storage.", objective="exfil",
       watched_by=("dlp", "firewall_ids"), score=120,
       opsec="Large outbound transfers are exactly what DLP/NDR look for."),

    # -- Impact / objective ------------------------------------------------ #
    _a("impact.disable_tools", "impact", "Impair defenses (disable EDR/logging)",
       "Blind the endpoint before the destructive step.", "Defense Evasion", mitre="T1562.001",
       noise=7, requires=("creds:privileged", "foothold"), effects=("disable_control:edr",),
       intel="Endpoint defensive tooling disabled on held hosts.",
       watched_by=("siem",), score=60, opsec="Tampering is loud-forever; central logging still sees it."),
    _a("impact.ransomware", "impact", "Deploy ransomware (benign marker)",
       "Prove destructive impact across reachable systems — ROE: mark, do not encrypt.", "Impact",
       mitre="T1486", noise=10, requires=("creds:privileged",),
       target_mode="auto", target_type="file_share,server",
       effects=("down", "flag:ransomware"),
       intel="Ransomware capability demonstrated against reachable systems (benign marker).",
       objective="ransomware", watched_by=("edr", "siem"), score=180,
       opsec="The loudest action there is — only at the objective, then stop."),
    _a("impact.ot_modify", "impact", "Modify PLC setpoints (benign marker)",
       "Demonstrate control over the physical process — ROE: prove, never endanger safety.",
       "Impair Process Control (ICS)", mitre="T0836", noise=8, requires=("flag:in_ot",),
       target_mode="select", target_type="ot_plc", effects=("down", "flag:ot_impact"),
       intel="Physical-process impact demonstrated on a PLC (benign marker).",
       objective="ot_impact", watched_by=("siem",), score=180,
       opsec="Safety-critical — the disciplined operator marks and immediately backs out."),
    _a("objective.capture_proof", "impact", "Capture proof & conclude the operation",
       "Capture clean, ROE-compliant evidence and STOP. Knowing when to stop is a senior skill.",
       "Objective Achievement", noise=0, requires=("objective_met",), effects=("conclude",),
       intel="Objective proven with defensible evidence. Operation concluded — minimum footprint.",
       score=0, opsec="Every action past the objective is risk for zero gain. Stop here."),
]
ACTIONS_BY_ID: dict[str, RedAction] = {a.id: a for a in RED_ACTIONS}


# --------------------------------------------------------------------------- #
#  Objectives — derived from the composed environment
# --------------------------------------------------------------------------- #
_OBJECTIVE_LABELS = {
    "ot_impact": "Reach & manipulate the OT/PLC — prove physical-process impact",
    "exfil": "Exfiltrate the sensitive data set — prove data theft",
    "ransomware": "Demonstrate ransomware impact across the estate",
    "domain_admin": "Compromise the identity plane (Domain Admin)",
    "cloud": "Establish durable cloud control-plane persistence",
    "recon_surface": "Map & validate the external attack surface",
    "initial_foothold": "Establish an initial foothold (human-layer entry)",
}
# Priority order for picking the *primary* objective (most consequential first).
_OBJECTIVE_PRIORITY = ("ot_impact", "exfil", "ransomware", "domain_admin")


def objective_label(key: str) -> str:
    return _OBJECTIVE_LABELS.get(key, key.replace("_", " ").title())


def derive_objectives(world: World) -> list[dict]:
    """Pick concrete, checkable objectives from the topology; flag the headline one as primary."""
    keys: list[str] = []
    if world.has_type("ot_plc"):
        keys.append("ot_impact")
    if world.has_type("file_share") or world.has_type("erp"):
        keys.append("exfil")
    keys.append("ransomware")
    if world.has_type("domain_controller"):
        keys.append("domain_admin")
    primary = next((k for k in _OBJECTIVE_PRIORITY if k in keys), keys[0])
    return [{"key": k, "label": _OBJECTIVE_LABELS[k], "met": False, "primary": k == primary}
            for k in dict.fromkeys(keys)]


def objective_is_met(key: str, world: World) -> bool:
    """World-derived objective completion. (op-state keys like recon_surface are checked by the session.)"""
    a = world.attacker
    if key == "domain_admin":
        return a.cred_scope.rank >= CredScope.DOMAIN_ADMIN.rank
    if key == "cloud":
        return bool(a.flags.get("cloud_persistence"))
    if key == "exfil":
        return bool(a.flags.get("exfiltrated"))
    return bool(a.flags.get(key))


# --------------------------------------------------------------------------- #
#  Availability, targets and noise (pure functions of op-state + world)
# --------------------------------------------------------------------------- #
def _matches_type(asset: AssetInstance, target_type: str) -> bool:
    wanted = {t.strip() for t in target_type.split(",")}
    if asset.type_key in wanted:
        return True
    try:
        return get_asset_type(asset.type_key).CATEGORY.value in wanted
    except Exception:
        return False


def _req_ok(req: str, op, world: World) -> bool:
    """Evaluate a single precondition string against operator state + world."""
    if req == "reachable":
        return True  # validated per-target in valid_targets / execution
    if req == "contained_persistent":
        has_persist = any(world.attacker.flags.get(k)
                          for k in ("persistence", "persistence_strong", "cloud_persistence"))
        from app.engine.enums import SecurityState as _SS
        any_contained = any(a.security_state == _SS.CONTAINED for a in world.all_assets())
        return has_persist and any_contained
    if req == "objective_met":
        return any(o["met"] for o in op.objectives if o["primary"]) or \
            any(o["met"] for o in op.objectives)
    if req == "foothold":
        return "foothold" in op.flags or world.attacker.has_foothold()
    if req.startswith("creds:"):
        return world.attacker.cred_scope.rank >= CredScope(req.split(":", 1)[1]).rank
    if req.startswith("flag:"):
        return bool(world.attacker.flags.get(req.split(":", 1)[1]))
    # bare name: an op progress flag (planned/recon_done/weaponized/...) OR a world flag (staged/in_ot/...)
    return req in op.flags or bool(world.attacker.flags.get(req))


def is_available(action: RedAction, op, world: World) -> tuple[bool, str]:
    if action.once and action.id in op.done_actions:
        return False, "already completed"
    for req in action.requires:
        if not _req_ok(req, op, world):
            return False, _req_reason(req)
    if action.target_mode == "select" and not valid_targets(action, op, world):
        return False, "no valid target discovered yet"
    if action.target_mode == "auto" and auto_target(action, world) is None:
        return False, "no suitable target in the environment"
    return True, ""


def _req_reason(req: str) -> str:
    pretty = {
        "planned": "review the mission plan first",
        "recon_done": "run reconnaissance first",
        "surface": "fingerprint exposed services first",
        "c2_ready": "stand up C2 first",
        "weaponized": "build the delivery lure first",
        "foothold": "establish a foothold first",
        "internal_recon_done": "map the internal terrain first",
        "objective_met": "reach the objective first",
        "reachable": "no reachable target",
    }
    if req in pretty:
        return pretty[req]
    if req.startswith("creds:"):
        return f"need {req.split(':', 1)[1].replace('_', ' ')} credentials"
    if req.startswith("flag:"):
        return f"requires: {req.split(':', 1)[1].replace('_', ' ')}"
    return f"requires {req}"


def valid_targets(action: RedAction, op, world: World) -> list[AssetInstance]:
    if action.target_mode != "select":
        return []
    if action.id == "persist.reestablish":
        from app.engine.enums import SecurityState as _SS
        return [world.get(aid) for aid in sorted(op.revealed)
                if world.get(aid) and world.get(aid).security_state == _SS.CONTAINED]  # type: ignore[misc]
    needs_reach = "reachable" in action.requires
    out: list[AssetInstance] = []
    for aid in sorted(op.revealed):
        asset = world.get(aid)
        if asset is None:
            continue
        if action.target_type and not _matches_type(asset, action.target_type):
            continue
        if action.id == "lateral.move" and asset.id in world.attacker.footholds:
            continue
        if needs_reach and not world.reachable(asset):
            continue
        out.append(asset)
    return out


def auto_target(action: RedAction, world: World) -> AssetInstance | None:
    if action.id in ("access.phish", "access.valid_creds"):
        eps = world.by_role("primary_endpoint") or world.by_type("endpoint")
        return eps[0] if eps else None
    if action.id == "access.exposed_service":
        ext = [a for a in world.all_assets() if a.zone in ("perimeter", "dmz", "cloud")]
        return (ext or world.by_type("server"))[0] if (ext or world.by_type("server")) else None
    if action.id == "impact.ransomware":
        fs = world.by_type("file_share") or [a for a in world.all_assets() if a.criticality >= 4]
        if fs:
            return fs[0]
        fhs = world.foothold_assets()
        return fhs[0] if fhs else None
    if action.id == "impact.disable_tools":
        fhs = world.foothold_assets()
        return fhs[0] if fhs else None
    return None


def effective_noise(action: RedAction, noise_multiplier: float, world: World,
                    target: AssetInstance | None) -> int:
    """Base noise scaled by the operator's evasion posture and where the defenders are watching."""
    mult = noise_multiplier
    watch_assets = [target] if target is not None else world.foothold_assets()
    exposed = any(
        world.active_control_for(a, ct) is not None
        for a in watch_assets if a is not None for ct in action.watched_by
    )
    if exposed:
        mult *= 1.4
    return max(0, round(action.noise * mult))
