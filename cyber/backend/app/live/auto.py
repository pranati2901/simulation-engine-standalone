"""Deterministic auto-drivers — play any seat that has no human operator.

No AI: each driver walks its masterclass playbook sensibly, taking ONE action per tick toward its
goal. This is the same `Driver` seam the design docs reserved — a future `AIDriver` can replace any
of these with no other change. A role is auto-driven when its seat is unoccupied (or the host forces
it); see LiveSession.is_auto.
"""
from __future__ import annotations

from . import blue_playbook as bp
from . import red_playbook as rp
from . import soc_playbook as sp

# Per-objective Red plan (appended to the common prefix). Mirrors the kill-chain toward the flag.
_RED_PREFIX = ["plan.review", "recon.osint", "infra.c2", "infra.lure", "access.phish",
               "foothold.stabilize", "evade.amsi", "intrecon.identity_graph", "cred.lsass"]
_RED_BY_OBJECTIVE = {
    "domain_admin": ["cred.dcsync"],
    "exfil": ["collect.stage", "exfil.cloud", "exfil.dns"],
    "ransomware": ["impact.ransomware"],
    "ot_impact": ["cred.dcsync", "lateral.pivot_ot", "impact.ot_modify"],
    "cloud": ["persist.cloud"],
    # recon_surface / initial_foothold are satisfied by the common prefix (recon / phish).
}


def _select_target(valid):
    return valid[0].id if valid else None


def auto_red(session) -> tuple[str, str | None] | None:
    op, world = session.operator, session.world
    if op is None or world is None or op.concluded:
        return None
    primary = next((o["key"] for o in op.objectives if o["primary"]), None)
    # Re-take a contained host first if persistence survived (cat-and-mouse).
    plan = ["persist.reestablish"] + _RED_PREFIX + _RED_BY_OBJECTIVE.get(primary, []) + ["objective.capture_proof"]
    for aid in plan:
        act = rp.ACTIONS_BY_ID.get(aid)
        if act is None:
            continue
        if aid in ("exfil.cloud", "exfil.dns") and "egress_blocked" in session.defense_flags:
            continue
        ok, _ = rp.is_available(act, op, world)
        if not ok:
            continue
        target = None
        if act.target_mode == "select":
            target = _select_target(rp.valid_targets(act, op, world))
            if target is None:
                continue
        return aid, target
    return None


def auto_soc(session) -> tuple[str, str | None] | None:
    ss, world = session.soc, session.world
    if ss is None or world is None or ss.concluded:
        return None

    def avail(aid):
        act = sp.SOC_ACTIONS_BY_ID.get(aid)
        return act is not None and sp.is_available(act, ss, world)[0]

    # 1) stand up core detection so Red's behaviour is visible
    for aid in ("soc.edr_monitoring", "soc.identity_monitoring", "soc.correlation"):
        if avail(aid):
            return aid, None
    # 2) work the queue: triage new alerts, then escalate triaged ones
    new_alert = next((a for a in session.alerts if a["status"] == "new"), None)
    if new_alert:
        return "soc.triage", new_alert["id"]
    triaged = next((a for a in session.alerts if a["status"] == "triaged"), None)
    if triaged:
        return "soc.escalate", triaged["id"]
    # 3) round out coverage + proactive work
    for aid in ("soc.network_monitoring", "soc.intel", "soc.soar", "soc.collect",
                "soc.investigate", "soc.hunt", "soc.tune"):
        if avail(aid):
            return aid, None
    return None


def auto_blue(session) -> tuple[str, str | None] | None:
    bs, world = session.defender, session.world
    if bs is None or world is None or bs.concluded:
        return None
    a = world.attacker

    def avail(aid):
        act = bp.BLUE_ACTIONS_BY_ID.get(aid)
        return act is not None and bp.is_available(act, bs, world)[0]

    # 1) preparation + visibility
    for aid in ("see.edr", "see.identity", "see.siem", "prepare.backups", "prepare.playbooks"):
        if avail(aid):
            return aid, None
    # 2) cut active exfil / movement
    if a.flags.get("staged") and "egress_blocked" not in session.defense_flags and avail("contain.block_egress"):
        return "contain.block_egress", None
    if (a.flags.get("in_ot") or a.cred_scope.rank >= 2) and "segmentation_active" not in session.defense_flags \
            and avail("contain.segment"):
        return "contain.segment", None
    # 3) scope, then eradicate persistence BEFORE final containment (so eviction sticks)
    if avail("investigate.scope"):
        return "investigate.scope", None
    if any(a.flags.get(k) for k in ("persistence", "cloud_persistence")):
        if avail("hunt.persistence"):
            return "hunt.persistence", None
        if avail("eradicate.persistence"):
            return "eradicate.persistence", None
    if (a.flags.get("persistence_strong") or a.cred_scope.rank >= 3) and avail("eradicate.krbtgt"):
        return "eradicate.krbtgt", None
    # 4) DC gate before isolating a DC
    dc_compromised = any(x.type_key == "domain_controller" and x.security_state.value == "compromised"
                         for x in world.all_assets())
    if dc_compromised and "dc_gate" not in bs.capabilities and avail("contain.dc_gate"):
        return "contain.dc_gate", None
    # 5) contain compromised hosts (prefer SOC-escalated incidents)
    if avail("contain.isolate"):
        targets = bp.valid_targets(bp.BLUE_ACTIONS_BY_ID["contain.isolate"], bs, world)
        if targets:
            pick = next((t for t in targets if t.id in session.incident_declared), targets[0])
            return "contain.isolate", pick.id
    # 6) recover impacted systems, then validate
    if avail("recover.restore"):
        targets = bp.valid_targets(bp.BLUE_ACTIONS_BY_ID["recover.restore"], bs, world)
        if targets:
            return "recover.restore", targets[0].id
    if avail("recover.validate"):
        return "recover.validate", None
    return None


def tick(session) -> bool:
    """Advance every auto-driven, unoccupied seat by one action. Returns True if anything changed."""
    if session.status != "active":
        return False
    changed = False
    drivers = {"red": (auto_red, session.execute_red_action),
               "soc": (auto_soc, session.execute_soc_action),
               "blue": (auto_blue, session.execute_blue_action)}
    for role in ("red", "soc", "blue"):
        if session.status != "active" or not session.is_auto(role):
            continue
        pick, execute = drivers[role]
        choice = pick(session)
        if choice is not None:
            ok, _ = execute("", choice[0], choice[1], by_auto=True)
            changed = changed or ok
    return changed
