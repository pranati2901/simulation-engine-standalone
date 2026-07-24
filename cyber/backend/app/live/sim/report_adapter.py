"""Turn a finished immersive ScenarioSim into the FULL detailed After-Action Report.

The deterministic engine produces a `run` dict that `app.reports.generator.generate_report` expands
into the rich, ~20-section executive AAR the frontend renders on the Reports page (exec summary,
per-team scorecards, attack path, per-asset risk, MITRE map, control effectiveness, dwell/zone/
credential analytics, regulatory + financial impact, maturity score, corrective actions, …).

The immersive sim (live/sim/engine.ScenarioSim) tracks all the underlying facts — a host topology,
an ordered action/alert event log, per-team scores — but in a different vocabulary. This module is
the translator: it reconstructs an equivalent `run` dict from the sim's end state, runs it through
the SAME generator the classic engine uses, then merges back the sim-shape keys the in-room result
overlay (components/AarReport) still needs. The result is a single report that renders as the full
detailed AAR on the Reports page AND as the in-room debrief — so the immersive sim's report is now
exactly as detailed as the older engine reports.

Pure, read-only over the finished sim. Any failure falls back to the sim's own basic report so a
report problem can never break scenario conclusion.
"""
from __future__ import annotations

import re
import sys
import traceback
from typing import TYPE_CHECKING

from app.engine.kpis import compute_kpis
from app.reports.generator import generate_report

from . import topology as T

if TYPE_CHECKING:
    from .engine import ScenarioSim

_MITRE_RE = re.compile(r"T\d{4}(?:\.\d{3})?")

# Per-scenario presentation (mirrors the guided scenario catalog so titles match the workspace).
_SCN = {
    "scn-wannacry-w1": ("Operation Tripwire", "WannaCry-Style SMB Worm"),
    "scn-r5-phishing": ("Phishing to Encrypt", "Human-Operated Ransomware Campaign"),
    "scn-c5-edr": ("EDR Outage Exploitation", "Attacking During Blindness"),
}

# host.role → (criticality 1-5, data_sensitivity 1-5) — feeds per-asset risk scoring.
_ROLE_CRIT = {
    "domain_controller": (5, 4), "backup": (5, 5), "database": (5, 5),
    "fileserver": (4, 5), "email": (4, 4), "appserver": (4, 3), "workstation": (2, 2),
}

# host.state → (security_state, health) in the generator's vocabulary.
_STATE_MAP = {
    "healthy": ("safe", "nominal"), "vulnerable": ("safe", "nominal"),
    "exploited": ("compromised", "nominal"),
    "infected": ("compromised", "degraded"), "propagating": ("compromised", "degraded"),
    "encrypting": ("compromised", "degraded"), "impacted": ("compromised", "down"),
    "dormant": ("suspicious", "degraded"), "contained": ("contained", "nominal"),
    "eradicated": ("contained", "nominal"), "recovered": ("safe", "nominal"),
}

# Blue tool effect → the control type it represents (generator _CONTROL_NAMES keys).
_BLUE_CTRL = {
    "segment": "segmentation", "sinkhole": "firewall_ids", "patch_all": "edr", "patch_hosts": "edr",
    "isolate": "edr", "restore": "backups", "protect_backup": "backups",
    "disable_cred": "mfa", "reset_creds": "mfa", "alt_detect": "siem",
}
# Blue effects that PREVENT spread (modelled as "block") vs. respond/contain (modelled as "response").
_BLUE_BLOCK = {"segment", "sinkhole", "patch_all", "patch_hosts"}

# Red persistence tools → persistence-report type labels understood by the generator.
_PERSIST_TYPE = {"persistence": "persistence_task", "schtask": "scheduled_task"}

_COMPROMISED_STATES = ("exploited", "infected", "propagating", "encrypting", "impacted", "dormant")


def _tech(tool) -> str:
    """First MITRE technique id embedded in a tool's `how` text, e.g. '(T1210)' → 'T1210'."""
    if tool is None:
        return ""
    m = _MITRE_RE.search(tool.how or "")
    return m.group(0) if m else ""


def _control_for_alert(label: str) -> str:
    """Attribute a SOC alert to the control that would have raised it (from its label)."""
    low = label.lower()
    if any(k in low for k in ("exploit", "smb", "scan", "lateral", "outbound", "spread", "domain")):
        return "firewall_ids"
    if any(k in low for k in ("payload", "service", "autorun", "shadow", "rename", "hunt", "locked", "inject")):
        return "edr"
    return "siem"


# --------------------------------------------------------------------------- #
#  run-dict reconstruction
# --------------------------------------------------------------------------- #
def _to_run_dict(sim: "ScenarioSim") -> dict:
    topo = sim.topo
    tools = sim.tools
    pz = next((h for h in topo.hosts.values() if h.patient_zero), None)

    events: list[dict] = []
    red_actions: list[tuple] = []          # (t, tool, asset_id, asset_label, severity, technique)
    first_attack_t: dict[str, int] = {}     # per-host first attack time (for dwell)
    global_first_t: int | None = None
    tech_phase: dict[str, str] = {}          # technique → red stage (to phase-label detections)
    seen_phase: str | None = None

    for e in sim.events:
        kind, role, t = e.get("kind"), e.get("role"), int(e.get("t", 0))
        data = e.get("data", {})
        tool = tools.get(data.get("tool_id", ""))

        if kind == "action" and role == "red":
            tech = _tech(tool)
            phase = (tool.stage if tool else e.get("title", "")) or ""
            aid, alabel = data.get("asset_id"), data.get("asset_label")
            sev = e.get("severity", "medium")
            if tech:
                tech_phase.setdefault(tech, phase)
            if phase and phase != seen_phase:               # phase marker on each new red stage
                seen_phase = phase
                events.append({"type": "phase", "t": t, "phase": phase, "severity": "info",
                               "title": f"Phase: {phase}", "message": f"Red entered {phase}"})
            events.append({"type": "attack", "t": t, "phase": phase, "severity": sev,
                           "technique": tech, "title": tool.name if tool else e.get("title", ""),
                           "message": e.get("message", ""), "actor": "red-team",
                           "asset_id": aid, "asset_label": alabel, "data": {}})
            red_actions.append((t, tool, aid, alabel, sev, tech))
            if global_first_t is None:
                global_first_t = t
            if aid and aid not in first_attack_t:
                first_attack_t[aid] = t

        elif kind == "response" and tool is not None:
            eff = tool.effect
            if eff == "view":                                # pure investigation lens — skip
                continue
            actor = _BLUE_CTRL.get(eff, "edr")
            if eff in _BLUE_BLOCK:
                events.append({"type": "block", "t": t, "phase": tool.stage, "severity": "medium",
                               "technique": "", "title": tool.name, "message": e.get("message", ""),
                               "actor": actor, "data": {}})
            else:
                events.append({"type": "response", "t": t, "phase": tool.stage,
                               "severity": e.get("severity", "high"), "technique": "",
                               "title": tool.name, "message": e.get("message", ""), "actor": actor,
                               "asset_id": data.get("asset_id"), "asset_label": data.get("asset_label"),
                               "data": {}})

    # Detections — one per SOC alert, attributed to a control with a reconstructed dwell time.
    for a in sim.alerts:
        host_id = a.get("host_id")
        ctrl = _control_for_alert(a.get("label", ""))
        base_t = first_attack_t.get(host_id, global_first_t or 0)
        dwell = max(0, int(a.get("t", 0)) - base_t)
        events.append({"type": "detection", "t": int(a.get("t", 0)),
                       "phase": tech_phase.get(a.get("mitre", ""), "Detection"),
                       "severity": a.get("severity", "medium"), "technique": a.get("mitre", ""),
                       "title": f"Alert: {a.get('label', '')}",
                       "message": (f"{ctrl.upper()} detected {a.get('label', '')}"
                                   + (f" on {a.get('host_name')}" if a.get("host_name") else "")
                                   + f" (dwell {dwell}s)"),
                       "asset_id": host_id, "asset_label": a.get("host_name"),
                       "data": {"control": ctrl, "dwell_s": dwell}})

    events.sort(key=lambda ev: ev["t"])

    # ---- derived facts -------------------------------------------------------
    done = sim.teams["red"].done
    done_effects = {tools[tid].effect for tid in done if tid in tools}
    done_tools = [tools[tid] for tid in done if tid in tools]

    infected = sim.infected_total()
    impacted = sim.impacted_total()
    named_comp = sum(1 for h in topo.hosts.values() if h.state in _COMPROMISED_STATES)
    extra_comp = sim.extra_infected + sim.extra_impacted + sim.extra_dormant
    compromised = named_comp + extra_comp
    contained_named = sum(1 for h in topo.hosts.values() if h.state in ("contained", "eradicated", "recovered"))
    dormant_named = sum(1 for h in topo.hosts.values() if h.state == "dormant")
    contained = contained_named + dormant_named + sim.extra_dormant   # hosts neutralised by Blue

    ransomware = "encrypt" in done_effects or impacted > 0
    exfiltrated = "exfiltrate" in done_effects
    creds = "none"
    if "cred_dump" in done_effects:
        creds = "domain_admin" if any("domain admin" in (t.outcome or "").lower() for t in done_tools) else "privileged"
    elif done_effects & {"exploit", "infect", "c2_establish", "deliver_phish", "spray"}:
        creds = "user"

    persistence_planted = [
        {"type": _PERSIST_TYPE.get(tool.id, "persistence_task"), "technique": tech,
         "asset_id": aid or (pz.id if pz else None), "asset_name": alabel or (pz.name if pz else None), "t": t}
        for (t, tool, aid, alabel, sev, tech) in red_actions if tool and tool.effect == "persist"
    ]
    eradicated = (sim._live_threats() == 0 and sim.extra_infected == 0
                  and (sim.smbv1_patched or sim.kill_switch == "tripped"))

    real_actions = [r for r in red_actions if r[1] and r[1].kind == "real"]
    vm_results = [{"technique": tech, "name": tool.name, "target": alabel or "",
                   "tool": tool.fire_action or tool.name, "real_executed": True, "real_success": True}
                  for (t, tool, aid, alabel, sev, tech) in real_actions]

    # ---- counts / KPIs -------------------------------------------------------
    attempts = len(red_actions)
    detected = len(sim.alerts)
    blocked = sum(1 for ev in events if ev["type"] == "block")
    triaged = sum(1 for a in sim.alerts if a["status"] in ("triaged", "escalated"))
    escalated = sum(1 for a in sim.alerts if a["status"] == "escalated")

    dwells = [ev["data"]["dwell_s"] for ev in events if ev["type"] == "detection"]
    first_det_t = min((int(a["t"]) for a in sim.alerts), default=None)
    mttc: list[int] = []
    if first_det_t is not None:
        for ev in events:
            if ev["type"] == "response" and ev.get("actor") == "edr" and "isolat" in ev["title"].lower():
                mttc.append(max(0, ev["t"] - first_det_t))

    kpis = compute_kpis(attempts=attempts, successes=attempts, detected=detected, contained=contained,
                        blocked=blocked, dwells=dwells, mttrs=mttc, first_detection_t=first_det_t)
    kpis["mtta_s"] = 0.0
    kpis["mttc_s"] = kpis["mttr_s"]
    kpis["escalation_accuracy"] = round(escalated / triaged, 3) if triaged else 1.0
    kpis["hunt_success"] = 0.0

    if impacted > 0 or ransomware:
        max_p = "P1"
    elif sim.incident_declared:
        max_p = "P2"
    elif sim.alerts:
        max_p = "P3"
    else:
        max_p = "None"

    summary = {
        "attempts": attempts, "succeeded": attempts, "blocked": blocked, "failed": 0,
        "detected": detected, "contained": contained, "escalations": escalated, "max_p_level": max_p,
        "assets_total": topo.total_hosts(), "assets_compromised": compromised,
        "assets_contained": contained_named + sim.extra_dormant, "assets_down": impacted,
        "attacker_max_creds": creds, "exfiltrated": exfiltrated, "ransomware": ransomware,
        "ot_impact": False, "backups_enabled": sim.backups_safe,
        "persistence_planted": persistence_planted, "persistence_eradicated": eradicated,
        "vm_results": vm_results, "vm_enabled": bool(real_actions),
    }

    # ---- objectives ----------------------------------------------------------
    objectives = {
        "red": [
            {"text": "Establish an initial foothold", "met": done_effects & {"exploit", "infect"} != set()},
            {"text": "Move laterally / propagate the worm",
             "met": "start_propagation" in done_effects or infected > 1},
            {"text": "Disable recovery before impact", "met": "disable_recovery" in done_effects},
            {"text": "Achieve impact (ransomware / exfiltration)", "met": ransomware or exfiltrated},
        ],
        "blue": [
            {"text": "Detect the intrusion", "met": detected > 0},
            {"text": "Contain compromised hosts", "met": contained > 0},
            {"text": "Remove the attack vector",
             "met": sim.smbv1_patched or sim.kill_switch == "tripped" or sim.segmented},
            {"text": "Recover impacted systems",
             "met": any(h.state == "recovered" for h in topo.hosts.values())},
        ],
    }

    # ---- per-role task checklists (tools used vs. available) -----------------
    role_tasks: dict[str, list[dict]] = {}
    for team in ("red", "soc", "blue"):
        role_tasks[team] = [
            {"id": tid, "label": tool.name, "description": tool.summary,
             "status": "done" if tid in sim.teams[team].done else "pending"}
            for tid, tool in tools.items() if tool.team == team
        ]

    # ---- asset snapshots -----------------------------------------------------
    def snap(h: T.Host, initial: bool) -> dict:
        crit, sens = _ROLE_CRIT.get(h.role, (2, 2))
        if initial:
            sstate, health = ("compromised", "nominal") if h.patient_zero else ("safe", "nominal")
        else:
            sstate, health = _STATE_MAP.get(h.state, ("safe", "nominal"))
        return {"id": h.id, "type": h.role, "name": h.name, "role": h.role, "zone": h.vlan,
                "criticality": crit, "data_sensitivity": sens,
                "security_state": sstate, "health": health}

    name, _sub = _SCN.get(sim.scenario_id, ("Operation Tripwire", ""))
    return {
        "scenario_id": sim.scenario_id, "scenario_name": name, "focus_role": "blue",
        "duration_s": max(1, sim._t()), "events": events,
        "scores": {"red": sim.team_score("red"), "blue": sim.team_score("blue"),
                   "soc": sim.team_score("soc")},
        "kpis": kpis, "summary": summary, "objectives": objectives,
        "environment": [snap(h, True) for h in topo.hosts.values()],
        "final_assets": [snap(h, False) for h in topo.hosts.values()],
        "role_tasks": role_tasks,
    }


# --------------------------------------------------------------------------- #
#  in-room AAR enrichment (the sim-shape `teams`/`mitre` AarReport renders)
# --------------------------------------------------------------------------- #
def _mitre_chain(sim: "ScenarioSim") -> list[dict]:
    alert_hosts = {a.get("host_id") for a in sim.alerts if a.get("host_id")}
    out = []
    for e in sim.events:
        if e.get("kind") == "action" and e.get("role") == "red":
            data = e.get("data", {})
            out.append({"t": int(e.get("t", 0)), "label": e.get("title", ""),
                        "mitre": _tech(sim.tools.get(data.get("tool_id", ""))),
                        "target": data.get("asset_label"),
                        "detected": bool(data.get("asset_id") and data.get("asset_id") in alert_hosts)})
    return out


def _add_findings(sim: "ScenarioSim", base: dict) -> None:
    band = base.get("outcome_band", "")
    teams = base.get("teams", {})
    impacted = sim.impacted_total()

    # Teaching mode: a non-functional (narrated) team gets an educational assessment of what it WOULD
    # have done against this run — never a 0, framed as the missed defensive opportunities.
    n_alerts = len(sim.alerts)
    severe = sum(1 for a in sim.alerts if a["severity"] in ("high", "critical"))
    if sim._is_narrated("soc") and "soc" in teams:
        teams["soc"]["findings"] = {
            "strengths": [f"A competent SOC had {n_alerts} alert(s) to work — triaging them and escalating "
                          f"the {severe} severe one(s) would have handed IR a scoped incident early.",
                          "The exploit/credential/encryption signals here are high-fidelity true positives."],
            "weaknesses": ["Low-fidelity early signals (scans, enumeration) are easy to miss — that's the "
                           "window Red exploited.", "Faster mean-time-to-detect shrinks Red's head start."]}
    if sim._is_narrated("blue") and "blue" in teams:
        opp = min(6, sim._live_threats() + impacted)
        teams["blue"]["findings"] = {
            "strengths": [f"There were ~{opp} clear containment opportunities — isolating footholds and "
                          "closing the vector (segment / patch / reset creds) would have capped the blast radius.",
                          "Air-gapping backups before impact keeps recovery viable."],
            "weaknesses": ["Containment only works if it's *timely* — every phase Red completes raises the cost.",
                           "Without escalation from SOC, Blue is working blind."]}

    red_s, red_w = [], []
    encrypt_tools = {"ransomware", "ransomware_r5", "gpo_ransomware"}
    if encrypt_tools & sim.teams["red"].done or impacted > 0:
        red_s.append("Drove the intrusion all the way to ransomware impact.")
    if sim.infected_total() + impacted > 0:
        red_s.append(f"Spread to {sim.infected_total() + impacted} host(s) before the run ended.")
    if band == "Contained":
        red_w.append("Defenders contained the worm before it reached scale.")
    if "red" in teams:
        teams["red"]["findings"] = {"strengths": red_s, "weaknesses": red_w}

    soc_s, soc_w = [], []
    if sim.alerts:
        soc_s.append(f"Raised {len(sim.alerts)} alert(s); "
                     f"{sum(1 for a in sim.alerts if a['status'] == 'escalated')} escalated to IR.")
    else:
        soc_w.append("No alerts were raised — the intrusion ran unseen.")
    if any(a["status"] == "new" for a in sim.alerts):
        soc_w.append("Left alerts un-triaged — unactioned alerts are where breaches hide.")
    if "soc" in teams and not sim._is_narrated("soc"):
        teams["soc"]["findings"] = {"strengths": soc_s, "weaknesses": soc_w}

    blue_s, blue_w = [], []
    if sim.segmented or sim.smbv1_patched or sim.kill_switch == "tripped":
        blue_s.append("Removed the worm's vector (segment / patch / sinkhole).")
    if band == "Contained":
        blue_s.append("Contained the spread before major impact.")
    elif band == "Catastrophic":
        blue_w.append("Containment came too late — broad encryption occurred.")
    if not sim.backups_safe:
        blue_w.append("Recovery was impaired — backups were not protected in time.")
    if "blue" in teams and not sim._is_narrated("blue"):
        teams["blue"]["findings"] = {"strengths": blue_s, "weaknesses": blue_w}


# --------------------------------------------------------------------------- #
#  public entry point
# --------------------------------------------------------------------------- #
def build(sim: "ScenarioSim") -> dict:
    """Full detailed AAR for a finished sim: generator sections + sim-shape keys, merged.

    Falls back to the sim's own basic report if reconstruction or generation fails — a report
    problem must never break scenario conclusion.
    """
    base = sim._build_report()
    try:
        run = _to_run_dict(sim)
        detailed = generate_report(run)
    except Exception:                       # noqa: BLE001 — never break conclusion on a report bug
        traceback.print_exc(file=sys.stderr)
        return base
    base["mitre"] = _mitre_chain(sim)
    _add_findings(sim, base)
    # detailed adds every rich section (incl. `scorecard`, which flips the Reports page to the full
    # renderer) and a richer `recommendations`; base contributes the sim-shape keys the in-room
    # overlay reads (scenario, result, outcome_band, verdict, outcome, teams, mitre, note, …).
    return {**base, **detailed}
