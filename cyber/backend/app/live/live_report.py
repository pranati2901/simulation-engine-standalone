"""After-Action Report for a concluded LIVE mission — one report, every team.

Assembles the per-role scorecards, the attack/defence timelines, MITRE coverage (what Red did vs.
what was detected), key findings and prioritised recommendations from a finished LiveSession. Pure
read-only over the session state; built once on `_finish` and surfaced in the snapshot + via REST.
"""
from __future__ import annotations

from . import missions as mp


def _red_findings(op_final: dict) -> dict:
    s, w = [], []
    exp = op_final["exposure_pct"]
    if op_final["objective_met"]:
        s.append("Achieved the primary objective.")
    elif op_final["any_objective_met"]:
        s.append("Achieved a secondary objective (primary not proven).")
    else:
        w.append("Did not prove an objective before the match ended.")
    if exp <= 40:
        s.append(f"Operated stealthily — exposure {exp}%.")
    elif exp >= 85:
        w.append(f"Very high exposure ({exp}%) — a live SOC would almost certainly catch this.")
    if op_final["overspend_penalty"] > 0:
        w.append(f"Exceeded the detection-risk budget (−{op_final['overspend_penalty']}).")
    else:
        s.append("Stayed within the detection-risk budget.")
    return {"strengths": s, "weaknesses": w}


def _soc_findings(f: dict) -> dict:
    s, w = [], []
    cov = f["coverage_pct"]
    if cov >= 80:
        s.append(f"Strong detection coverage ({cov}%).")
    elif cov < 50:
        w.append(f"Detection gaps — only {cov}% of detectable behaviour was covered.")
    if f["escalated"] > 0:
        s.append(f"Escalated {f['escalated']} incident(s) to IR.")
    if f["mtta_s"] and f["mtta_s"] <= 10:
        s.append(f"Fast acknowledgement (MTTA {f['mtta_s']}s).")
    if f["open_alerts"] > 0:
        w.append(f"Left {f['open_alerts']} alert(s) untriaged — unactioned alerts are where breaches hide.")
    if f["detectable"] and f["detected"] < f["detectable"]:
        w.append(f"Missed {f['detectable'] - f['detected']} detectable behaviour(s).")
    return {"strengths": s, "weaknesses": w}


def _blue_findings(f: dict, impact_occurred: bool) -> dict:
    s, w = [], []
    if f["eviction_complete"]:
        s.append("Fully evicted the adversary (no footholds or persistence left).")
    elif f["footholds_total"] > 0:
        w.append("Did not fully evict — footholds and/or persistence remained.")
    if f["contained"] > 0:
        s.append(f"Contained {f['contained']} host(s) (MTTC {f['mttc_s']}s).")
    if f["prevented"]:
        s.append("Prevented impact: " + ", ".join(f["prevented"]) + ".")
    if impact_occurred and not f["prevented"]:
        w.append("Destructive/exfil impact occurred without being prevented or recovered in time.")
    return {"strengths": s, "weaknesses": w}


def _recommendations(session, of: dict, sf: dict, bf: dict) -> list[str]:
    recs: list[str] = []
    a = session.world.attacker
    if sf.get("coverage_pct", 0) < 80:
        recs.append("SOC: enable broader monitoring (EDR + identity + network) and correlation to lift "
                    f"detection coverage above 80% (was {sf.get('coverage_pct', 0)}%).")
    if a.flags.get("exfiltrated") and "exfil" not in bf.get("prevented", []):
        recs.append("Blue: block egress / DNS-sinkhole the moment staging is detected — exfiltration succeeded.")
    if (a.flags.get("ransomware") or a.flags.get("ot_impact")) and not bf.get("prevented"):
        recs.append("Blue: segment early to limit spread and restore from isolated, immutable backups — "
                    "destructive impact was not contained.")
    if session.red_ever_foothold and not bf.get("eviction_complete"):
        recs.append("Blue: scope → hunt → eradicate persistence → krbtgt ×2 BEFORE final containment, "
                    "so eviction sticks (Red can re-establish through surviving persistence).")
    if sf.get("open_alerts", 0) > 0:
        recs.append(f"SOC: work the full queue — {sf['open_alerts']} alert(s) were never triaged.")
    if of.get("exposure_pct", 0) >= 85:
        recs.append("Red: invest in evasion (AMSI/low-and-slow) and quieter tradecraft to lower exposure.")
    if session.match_result == "red":
        recs.append("Overall: the adversary reached the objective — prioritise the detection/containment gaps above.")
    elif session.match_result == "blue":
        recs.append("Overall: defenders won — sustain coverage and response speed; rehearse to keep MTTC low.")
    return recs[:7]


def _mitre_timeline(session) -> list[dict]:
    """Red's attack steps with detection status (the kill-chain + coverage map)."""
    out = []
    for e in session.events:
        if e["kind"] == "action" and e["role"] == "red":
            d = e.get("data", {})
            out.append({
                "t": e["t"], "action_id": d.get("action_id"), "label": e["title"],
                "mitre": d.get("mitre", ""), "tactic": d.get("tactic", ""),
                "target": e.get("asset_label"), "noise": d.get("noise", 0),
                "detected": bool(d.get("detected")),
            })
    return out


def build_report(session) -> dict:
    """Build the all-teams After-Action Report for a concluded live mission."""
    op, ss, bd, world = session.operator, session.soc, session.defender, session.world
    mission = mp.MISSION_BY_ID.get(session.mission, mp.MISSION_BY_ID[mp.DEFAULT_MISSION])
    of = op.final or {}
    sf = ss.final or {}
    bf = bd.final or {}
    result = session.match_result or "draw"
    duration_s = session.events[-1]["t"] if session.events else 0
    assets = world.all_assets()

    red_f = _red_findings(of)
    red_f["_exposure"] = of.get("exposure_pct", 0)
    soc_f = _soc_findings(sf)
    blue_f = _blue_findings(bf, session.impact_occurred)
    mitre = _mitre_timeline(session)

    verdict = {
        "red": "Red achieved the objective — attacker wins.",
        "blue": "Blue fully evicted the adversary — defender wins.",
    }.get(result, "Operation concluded without a decisive outcome.")

    return {
        "session_id": session.id,
        "generated": "on_conclude",
        "mission": {"id": mission.id, "name": mission.name, "klass": mission.klass,
                    "briefing": mission.briefing, "success": dict(mission.success)},
        "profile": op.profile,
        "result": result,
        "verdict": verdict,
        "duration_s": duration_s,
        "outcome": {
            "objective_met": of.get("objective_met", False),
            "objectives": of.get("objectives", []),
            "assets_total": len(assets),
            "assets_compromised": sum(1 for a in assets if a.security_state.value == "compromised"),
            "assets_contained": sum(1 for a in assets if a.security_state.value == "contained"),
            "assets_down": sum(1 for a in assets if a.health.value == "down"),
            "footholds_total": bf.get("footholds_total", 0),
            "eviction_complete": bf.get("eviction_complete", False),
            "coverage_pct": session.coverage_pct,
        },
        "teams": {
            "red": {
                "score": of.get("total_score", op.score),
                "breakdown": {"actions": of.get("action_score", 0),
                              "stealth_bonus": of.get("stealth_bonus", 0),
                              "discipline_bonus": of.get("discipline_bonus", 0),
                              "overspend_penalty": of.get("overspend_penalty", 0)},
                "kpis": {"noise_spent": of.get("noise_spent", 0), "budget": of.get("budget", 0),
                         "exposure_pct": of.get("exposure_pct", 0),
                         "actions_taken": of.get("actions_taken", len(op.history))},
                "objectives": of.get("objectives", []),
                "timeline": op.history,
                "intel": op.intel,
                "findings": {"strengths": red_f["strengths"], "weaknesses": red_f["weaknesses"]},
            },
            "soc": {
                "score": sf.get("total_score", ss.score),
                "kpis": {"coverage_pct": sf.get("coverage_pct", session.coverage_pct),
                         "detected": sf.get("detected", session.detected_actions),
                         "detectable": sf.get("detectable", session.detectable_actions),
                         "mtta_s": sf.get("mtta_s", 0), "triaged": sf.get("triaged", 0),
                         "escalated": sf.get("escalated", 0), "open_alerts": sf.get("open_alerts", 0)},
                "timeline": ss.history,
                "alerts": list(session.alerts),
                "findings": soc_f,
            },
            "blue": {
                "score": bf.get("total_score", bd.score),
                "breakdown": {"actions": bf.get("action_score", 0),
                              "eviction_bonus": bf.get("eviction_bonus", 0),
                              "prevention_bonus": bf.get("prevention_bonus", 0)},
                "kpis": {"mttc_s": bf.get("mttc_s", 0), "contained": bf.get("contained", 0),
                         "footholds_total": bf.get("footholds_total", 0),
                         "eviction_complete": bf.get("eviction_complete", False),
                         "prevented": bf.get("prevented", [])},
                "timeline": bd.history,
                "findings": blue_f,
            },
        },
        "mitre": mitre,
        "recommendations": _recommendations(session, of, sf, bf),
        "note": "Management & OT roles are reserved seats and were not actively played in this build.",
    }
