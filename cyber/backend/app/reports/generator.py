"""Generate a deterministic After-Action Report from a completed run's data.

Sections mirror the PDF's "Final Executive Report" and extend it with per-asset
risk analysis, attack-path reconstruction, control effectiveness breakdown,
dwell-time analytics, zone breach analysis, credential escalation timeline,
and a structured key-findings section. Pure function of the run data.
"""
from __future__ import annotations

_TIMELINE_TYPES = {"attack", "block", "fail", "detection", "response", "inject", "phase"}

_CRED_TECHNIQUES: dict[str, tuple[str, str]] = {
    "T1566.001": ("user", "Spear-phishing delivered initial user credentials"),
    "T1003.001": ("privileged", "LSASS credential dump yielded privileged access"),
    "T1558.003": ("privileged", "Kerberoasting cracked service account hashes"),
    "T1003.006": ("domain_admin", "DCSync replicated Domain Admin credentials"),
}

_CONTROL_NAMES: dict[str, str] = {
    "edr": "EDR", "siem": "SIEM", "firewall_ids": "Firewall / IDS",
    "segmentation": "Segmentation", "dlp": "DLP", "mfa": "MFA",
    "backups": "Backups", "email_sec": "Email Security",
}

_CRED_RANK = {"none": 0, "user": 1, "privileged": 2, "domain_admin": 3}


def _fmt(t: int) -> str:
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _mean(xs: list[int | float]) -> float:
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def _median(xs: list[int | float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    if n % 2 == 1:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def _exec_summary(run: dict) -> str:
    s, kp = run["summary"], run["kpis"]
    sc = run["scores"]
    duration_min = run["duration_s"] // 60
    name = run.get("scenario_name", "the scenario")

    outcome = []
    if s.get("ot_impact"):
        outcome.append("the attacker manipulated safety-critical OT processes")
    if s.get("ransomware"):
        outcome.append("ransomware was deployed against enterprise systems")
    if s.get("exfiltrated"):
        outcome.append("sensitive data was exfiltrated")
    if not outcome:
        outcome.append("the intrusion was contained before material impact")

    det = f"{kp.get('detection_rate', 0) * 100:.0f}% of successful actions were detected"
    mttd = kp.get("mttd_s", 0)
    winner = "Blue" if sc.get("blue", 0) >= sc.get("red", 0) else "Red"

    parts = [
        f"Over a {duration_min}-minute exercise ({name}), " + ", ".join(outcome),
        det + (f", with a mean time-to-detect of {mttd / 60:.1f} min" if mttd > 0 else ""),
    ]
    if s.get("contained", 0):
        parts.append(f"{s['contained']} host(s) were contained by the response team")
    if s.get("blocked", 0):
        parts.append(f"{s['blocked']} attacker action(s) were prevented outright by security controls")

    compromised = s.get("assets_compromised", 0)
    down = s.get("assets_down", 0)
    total = s.get("assets_total", 0)
    if compromised or down:
        parts.append(
            f"Of {total} assets in the environment, {compromised} were compromised"
            + (f" and {down} were taken offline" if down else "")
        )

    creds = s.get("attacker_max_creds", "none")
    if creds == "domain_admin":
        parts.append("The attacker achieved full Domain Admin privileges")
    elif creds == "privileged":
        parts.append("The attacker escalated to privileged credentials")

    parts.append(
        f"Overall advantage: {winner} team (Red {sc.get('red', 0)} / Blue {sc.get('blue', 0)})"
    )
    return ". ".join(parts) + "."


def _timeline(run: dict) -> list[dict]:
    out = []
    for e in run["events"]:
        if e.get("type") in _TIMELINE_TYPES:
            out.append({
                "t": e["t"], "clock": _fmt(e["t"]), "phase": e.get("phase"),
                "type": e["type"], "severity": e.get("severity"),
                "title": e.get("title"), "message": e.get("message"),
                "technique": e.get("technique"),
                "asset": e.get("asset_label"),
            })
    return out


def _attack_path(run: dict) -> list[dict]:
    path = []
    for e in run["events"]:
        etype = e.get("type")
        if etype == "attack":
            data = e.get("data", {})
            path.append({
                "t": e["t"], "clock": _fmt(e["t"]),
                "technique": e.get("technique", ""),
                "name": e.get("title", ""),
                "target_id": e.get("asset_id"),
                "target_name": e.get("asset_label", ""),
                "phase": e.get("phase", ""),
                "severity": e.get("severity", "medium"),
                "result": "fallback" if data.get("fallback_of") else "success",
                "fallback_of": data.get("fallback_of"),
            })
        elif etype == "block":
            path.append({
                "t": e["t"], "clock": _fmt(e["t"]),
                "technique": e.get("technique", ""),
                "name": (e.get("title", "")).replace("Prevented: ", ""),
                "target_id": e.get("asset_id"),
                "target_name": e.get("asset_label", ""),
                "phase": e.get("phase", ""),
                "severity": e.get("severity", "medium"),
                "result": "blocked",
                "blocked_by": _CONTROL_NAMES.get(e.get("actor", ""), e.get("actor", "")),
            })
    return path


def _mitre_map(run: dict) -> list[dict]:
    detected_set = {e.get("technique") for e in run["events"] if e.get("type") == "detection"}
    blocked_set = {e.get("technique") for e in run["events"] if e.get("type") == "block"}
    seen: dict[str, dict] = {}
    for e in run["events"]:
        if e.get("type") in ("attack", "block") and e.get("technique"):
            key = e["technique"]
            if key not in seen:
                seen[key] = {
                    "technique": key,
                    "name": e.get("title", "").replace("Prevented: ", ""),
                    "tactic": e.get("phase"),
                    "severity": e.get("severity", "medium"),
                    "detected": key in detected_set,
                    "blocked": key in blocked_set,
                }
    return [seen[k] for k in sorted(seen)]


def _scorecard(run: dict) -> dict:
    s, kp, sc = run["summary"], run["kpis"], run["scores"]
    obj = run.get("objectives", {})
    return {
        "red_score": sc.get("red", 0),
        "blue_score": sc.get("blue", 0),
        "winner": "Blue" if sc.get("blue", 0) >= sc.get("red", 0) else "Red",
        "mttd_min": round(kp.get("mttd_s", 0) / 60, 1),
        "mttr_min": round(kp.get("mttr_s", 0) / 60, 1),
        "detection_rate": kp.get("detection_rate", 0),
        "containment_rate": kp.get("containment_rate", 0),
        "prevention_rate": kp.get("prevention_rate", 0),
        "fp_rate": kp.get("fp_rate", 0),
        "time_to_first_detection_min": round(kp.get("time_to_first_detection_s", 0) / 60, 1),
        "attacker_actions": s.get("attempts", 0),
        "succeeded": s.get("succeeded", 0),
        "blocked": s.get("blocked", 0),
        "detected": s.get("detected", 0),
        "contained": s.get("contained", 0),
        "failed": s.get("failed", 0),
        "red_objectives_met": sum(1 for o in obj.get("red", []) if o.get("met")),
        "red_objectives_total": len(obj.get("red", [])),
        "blue_objectives_met": sum(1 for o in obj.get("blue", []) if o.get("met")),
        "blue_objectives_total": len(obj.get("blue", [])),
    }


_ROLE_TITLES = {
    "red": "Red Team", "soc": "SOC", "blue": "Blue Team (IR)",
    "mgmt": "Management / IC", "ot": "OT / Operations",
}


def _role_scorecards(run: dict) -> list[dict]:
    """Per-team scorecard: score, task completion, and the KPIs that matter to that role."""
    sc, kp, s = run["scores"], run["kpis"], run["summary"]
    role_tasks = run.get("role_tasks", {})
    cards = []
    for role in ("red", "soc", "blue", "mgmt", "ot"):
        if role not in sc:
            continue
        tasks = role_tasks.get(role, [])
        done = sum(1 for t in tasks if t.get("status") == "done")
        if role == "red":
            kpis = {"Actions succeeded": s.get("succeeded", 0), "Blocked": s.get("blocked", 0),
                    "Max privilege": s.get("attacker_max_creds", "none"),
                    "Assets compromised": s.get("assets_compromised", 0)}
            headline = ("Reached OT impact" if s.get("ot_impact") else "Deployed ransomware"
                        if s.get("ransomware") else "Exfiltrated data" if s.get("exfiltrated")
                        else "Intrusion contained early")
        elif role == "soc":
            kpis = {"Detection rate": f"{kp.get('detection_rate', 0) * 100:.0f}%",
                    "MTTD": f"{kp.get('mttd_s', 0) / 60:.1f}m", "MTTA": f"{kp.get('mtta_s', 0) / 60:.1f}m",
                    "Escalation accuracy": f"{kp.get('escalation_accuracy', 0) * 100:.0f}%",
                    "Hunt success": f"{kp.get('hunt_success', 0) * 100:.0f}%"}
            headline = f"Peaked at {s.get('max_p_level', 'P3')} · {s.get('detected', 0)} alerts triaged"
        elif role == "blue":
            kpis = {"Containment rate": f"{kp.get('containment_rate', 0) * 100:.0f}%",
                    "MTTC": f"{kp.get('mttc_s', 0) / 60:.1f}m", "Hosts contained": s.get("contained", 0),
                    "Recovery": "backups" if s.get("backups_enabled") else "impaired"}
            headline = f"{s.get('contained', 0)} host(s) contained · {s.get('blocked', 0)} prevented"
        elif role == "mgmt":
            kpis = {"Highest priority": s.get("max_p_level", "P3"),
                    "Notifications": done, "BCP": "activated" if s.get("ransomware") else "n/a"}
            headline = "Executive escalation & regulatory clocks managed"
        else:  # ot
            kpis = {"Safety preserved": "no" if s.get("ot_impact") else "yes",
                    "OT impact": "yes" if s.get("ot_impact") else "no"}
            headline = "Switched to manual ops" if done else "OT not engaged this run"
        cards.append({"role": role, "title": _ROLE_TITLES[role], "score": sc.get(role, 0),
                      "tasks_done": done, "tasks_total": len(tasks), "kpis": kpis,
                      "headline": headline, "tasks": tasks})
    return cards


def _per_asset_report(run: dict) -> list[dict]:
    env = run.get("environment", [])
    final = run.get("final_assets", [])
    events = run.get("events", [])

    initial_by_id = {a["id"]: a for a in env}
    final_by_id = {a["id"]: a for a in final}

    stats: dict[str, dict] = {}
    for e in events:
        aid = e.get("asset_id")
        if not aid:
            continue
        if aid not in stats:
            stats[aid] = {
                "attacks": 0, "blocks": 0, "detections": 0, "responses": 0,
                "dwells": [], "detected_by": set(), "first_attack_t": None,
            }
        etype = e.get("type")
        if etype == "attack":
            stats[aid]["attacks"] += 1
            if stats[aid]["first_attack_t"] is None:
                stats[aid]["first_attack_t"] = e["t"]
        elif etype == "block":
            stats[aid]["blocks"] += 1
        elif etype == "detection":
            stats[aid]["detections"] += 1
            stats[aid]["dwells"].append(e.get("data", {}).get("dwell_s", 0))
            ctrl = e.get("data", {}).get("control", "")
            if ctrl:
                stats[aid]["detected_by"].add(ctrl)
        elif etype == "response":
            stats[aid]["responses"] += 1

    all_ids = sorted(set(list(initial_by_id.keys()) + list(final_by_id.keys())))
    state_weight = {"safe": 0, "suspicious": 1, "compromised": 3, "contained": 1}
    health_weight = {"nominal": 0, "degraded": 1, "down": 3}
    report = []

    for aid in all_ids:
        init = initial_by_id.get(aid, {})
        fin = final_by_id.get(aid, {})
        st = stats.get(aid, {
            "attacks": 0, "blocks": 0, "detections": 0, "responses": 0,
            "dwells": [], "detected_by": set(), "first_attack_t": None,
        })

        criticality = fin.get("criticality", init.get("criticality", 3))
        data_sens = fin.get("data_sensitivity", init.get("data_sensitivity", 1))
        initial_state = init.get("security_state", "safe")
        final_state = fin.get("security_state", "safe")
        final_health = fin.get("health", "nominal")

        dwells = st["dwells"]
        avg_dwell = round(_mean(dwells)) if dwells else 0

        risk = min(100, max(0, round(
            criticality * 6 + data_sens * 3 + st["attacks"] * 4
            + min(avg_dwell / 60, 10) * 3
            + state_weight.get(final_state, 0) * 10
            + health_weight.get(final_health, 0) * 8
        )))

        report.append({
            "id": aid, "name": fin.get("name", init.get("name", aid)),
            "type": fin.get("type", init.get("type", "")),
            "zone": fin.get("zone", init.get("zone", "")),
            "criticality": criticality, "data_sensitivity": data_sens,
            "initial_state": initial_state, "final_state": final_state,
            "final_health": final_health, "times_targeted": st["attacks"],
            "times_blocked": st["blocks"], "times_detected": st["detections"],
            "contained": st["responses"] > 0 or final_state == "contained",
            "avg_dwell_s": avg_dwell, "detected_by": sorted(st["detected_by"]),
            "risk_score": risk,
        })

    report.sort(key=lambda a: -a["risk_score"])
    return report


def _control_effectiveness(run: dict) -> list[dict]:
    controls: dict[str, dict] = {}
    for e in run["events"]:
        etype = e.get("type")
        if etype == "block":
            ctype = e.get("actor", "")
            if not ctype:
                continue
            controls.setdefault(ctype, {"type": ctype, "detections": 0, "blocks": 0,
                                        "techniques_detected": [], "techniques_blocked": [],
                                        "dwell_times": []})
            controls[ctype]["blocks"] += 1
            tech = e.get("technique", "")
            if tech and tech not in controls[ctype]["techniques_blocked"]:
                controls[ctype]["techniques_blocked"].append(tech)
        elif etype == "detection":
            ctype = e.get("data", {}).get("control", "")
            if not ctype:
                continue
            controls.setdefault(ctype, {"type": ctype, "detections": 0, "blocks": 0,
                                        "techniques_detected": [], "techniques_blocked": [],
                                        "dwell_times": []})
            controls[ctype]["detections"] += 1
            tech = e.get("technique", "")
            if tech and tech not in controls[ctype]["techniques_detected"]:
                controls[ctype]["techniques_detected"].append(tech)
            controls[ctype]["dwell_times"].append(e.get("data", {}).get("dwell_s", 0))

    result = []
    for ctype in sorted(controls):
        c = controls[ctype]
        dwells = c.pop("dwell_times")
        c["name"] = _CONTROL_NAMES.get(ctype, ctype)
        c["avg_dwell_s"] = round(_mean(dwells)) if dwells else 0
        c["total_actions"] = c["detections"] + c["blocks"]
        result.append(c)
    result.sort(key=lambda c: -c["total_actions"])
    return result


def _dwell_analysis(run: dict) -> dict:
    by_asset: dict[str, list[int]] = {}
    by_phase: dict[str, list[int]] = {}
    all_dwells: list[int] = []
    for e in run["events"]:
        if e.get("type") != "detection":
            continue
        dwell = e.get("data", {}).get("dwell_s", 0)
        all_dwells.append(dwell)
        label = e.get("asset_label") or e.get("asset_id") or "unknown"
        by_asset.setdefault(label, []).append(dwell)
        phase = e.get("phase") or "unknown"
        by_phase.setdefault(phase, []).append(dwell)

    def _stats(xs: list[int]) -> dict:
        if not xs:
            return {"mean_s": 0, "median_s": 0, "min_s": 0, "max_s": 0, "count": 0}
        xs_sorted = sorted(xs)
        return {"mean_s": round(_mean(xs_sorted)), "median_s": round(_median(xs_sorted)),
                "min_s": xs_sorted[0], "max_s": xs_sorted[-1], "count": len(xs_sorted)}

    worst = max(by_asset.items(), key=lambda kv: max(kv[1])) if by_asset else None
    return {
        "overall": _stats(all_dwells),
        "by_asset": [{"asset": k, **_stats(v)} for k, v in sorted(by_asset.items())],
        "by_phase": [{"phase": k, **_stats(v)} for k, v in by_phase.items()],
        "worst": {"asset": worst[0] if worst else None,
                  "max_dwell_s": max(worst[1]) if worst else 0},
    }


def _zone_analysis(run: dict) -> list[dict]:
    env = run.get("environment", [])
    final_by_id = {a["id"]: a for a in run.get("final_assets", [])}
    zones: dict[str, dict] = {}
    for a in env:
        zone = a.get("zone", "unknown")
        zones.setdefault(zone, {"zone": zone, "assets_total": 0, "assets_compromised": 0,
                                "assets_contained": 0, "assets_down": 0, "assets_safe": 0,
                                "asset_names": []})
        zones[zone]["assets_total"] += 1
        zones[zone]["asset_names"].append(a.get("name", a["id"]))
        fin = final_by_id.get(a["id"], {})
        fs = fin.get("security_state", "safe")
        if fs == "compromised":
            zones[zone]["assets_compromised"] += 1
        elif fs == "contained":
            zones[zone]["assets_contained"] += 1
        else:
            zones[zone]["assets_safe"] += 1
        if fin.get("health") == "down":
            zones[zone]["assets_down"] += 1
    for z in zones.values():
        total = z["assets_total"] or 1
        z["breach_pct"] = round(z["assets_compromised"] / total * 100)
        z["status"] = ("breached" if z["assets_compromised"] > 0
                       else "contained" if z["assets_contained"] > 0 else "secure")
    return sorted(zones.values(), key=lambda z: -z["assets_compromised"])


def _credential_timeline(run: dict) -> list[dict]:
    timeline: list[dict] = []
    seen: set[str] = set()
    for e in run["events"]:
        if e.get("type") != "attack":
            continue
        tech = e.get("technique", "")
        if tech in _CRED_TECHNIQUES:
            scope, desc = _CRED_TECHNIQUES[tech]
            if scope not in seen:
                seen.add(scope)
                timeline.append({"t": e["t"], "clock": _fmt(e["t"]), "scope": scope,
                                 "rank": _CRED_RANK.get(scope, 0), "technique": tech,
                                 "description": desc, "target": e.get("asset_label", "")})
    return timeline


def _key_findings(run: dict) -> dict:
    s, kp = run["summary"], run["kpis"]
    events = run["events"]
    strengths: list[str] = []
    weaknesses: list[str] = []

    blocked = s.get("blocked", 0)
    if blocked > 0:
        names = sorted({e.get("title", "").replace("Prevented: ", "")
                        for e in events if e.get("type") == "block"})
        strengths.append(f"{blocked} attacker action(s) prevented: {', '.join(names)}")

    det_rate = kp.get("detection_rate", 0)
    if det_rate >= 0.8:
        strengths.append(f"Strong detection coverage at {det_rate * 100:.0f}%")
    elif det_rate >= 0.5:
        strengths.append(f"Moderate detection coverage at {det_rate * 100:.0f}%")

    mttd = kp.get("mttd_s", 0)
    if 0 < mttd < 300:
        strengths.append(f"Fast mean time-to-detect ({mttd / 60:.1f} minutes)")

    contained_n = s.get("contained", 0)
    if contained_n > 0:
        strengths.append(f"{contained_n} compromised asset(s) successfully contained")
    if s.get("backups_enabled"):
        strengths.append("Tested offline backups available, reducing ransomware impact")
    if not s.get("ransomware") and s.get("succeeded", 0) > 3:
        strengths.append("Ransomware deployment was prevented despite deep intrusion")
    if not s.get("ot_impact") and s.get("succeeded", 0) > 5:
        strengths.append("OT/ICS systems protected despite enterprise compromise")

    if det_rate < 0.3 and s.get("succeeded", 0) > 0:
        weaknesses.append(f"Critical detection gap: only {det_rate * 100:.0f}% of attacks detected")
    elif det_rate < 0.5 and s.get("succeeded", 0) > 0:
        weaknesses.append(f"Poor detection coverage at {det_rate * 100:.0f}%")
    if mttd > 600:
        weaknesses.append(f"Slow detection: mean dwell time {mttd / 60:.1f} minutes")
    if s.get("exfiltrated"):
        weaknesses.append("Sensitive data exfiltrated before detection or containment")
    if s.get("ransomware"):
        weaknesses.append("Ransomware successfully deployed causing operational disruption")
    if s.get("ot_impact"):
        weaknesses.append("Attacker reached OT/ICS and manipulated safety-critical processes")
    if s.get("detected", 0) == 0 and s.get("succeeded", 0) > 0:
        weaknesses.append("No attacks detected at all, indicating complete defensive blindness")
    if s.get("contained", 0) == 0 and s.get("detected", 0) > 0:
        weaknesses.append("Detections raised but no containment actions followed")
    if s.get("attacker_max_creds", "none") == "domain_admin":
        weaknesses.append("Attacker achieved Domain Admin, indicating full domain compromise")

    critical = None
    for e in events:
        if e.get("type") == "block":
            critical = (f"At {_fmt(e['t'])}, {_CONTROL_NAMES.get(e.get('actor', ''), e.get('actor', ''))} "
                        f"prevented {e.get('title', '').replace('Prevented: ', '')}, disrupting the kill chain")
            break
    if not critical:
        for e in events:
            if e.get("type") == "attack" and e.get("severity") == "critical":
                critical = (f"At {_fmt(e['t'])}, {e.get('title', 'a critical attack')} succeeded "
                            f"against {e.get('asset_label', 'a target')}, marking a pivotal escalation")
                break
    if not critical:
        for e in events:
            if e.get("type") == "detection":
                critical = f"First detection at {_fmt(e['t'])}: {e.get('message', '')}"
                break

    return {
        "strengths": strengths or ["No notable defensive strengths observed in this run"],
        "weaknesses": weaknesses or ["No significant defensive gaps identified"],
        "critical_moment": critical or "No single critical moment identified in this run",
    }


def _regulatory_impact(run: dict) -> list[dict]:
    """Produce structured regulatory impact entries, enriched by framework data from NOTIFY events."""
    s = run["summary"]
    events = run.get("events", [])

    # Collect triggered frameworks from NOTIFY events
    frameworks: list[dict] = []
    for e in events:
        if e.get("type") == "notify":
            data = e.get("data", {})
            if data.get("framework_id"):
                frameworks.append({
                    "framework_id": data["framework_id"],
                    "framework_name": data.get("framework_name", ""),
                    "deadline_hours": data.get("deadline_hours", 0),
                    "penalty": data.get("penalty", ""),
                    "on_time": data.get("on_time", False),
                    "message": e.get("message", ""),
                })

    if frameworks:
        return frameworks

    # Fallback: generic impact text if no framework events
    items: list[dict] = []
    if s.get("exfiltrated"):
        items.append({"framework_name": "Data Breach Notification", "message":
            "Personal/IP data breach: breach-notification obligations likely triggered.",
            "deadline_hours": 720, "penalty": "", "on_time": False})
    if s.get("ransomware"):
        items.append({"framework_name": "Operational Disruption Disclosure", "message":
            "Material operational disruption: may require disclosure to regulators.",
            "deadline_hours": 0, "penalty": "", "on_time": False})
    if s.get("ot_impact"):
        items.append({"framework_name": "Critical Infrastructure Reporting", "message":
            "Safety-critical impact: mandatory reporting to national CERT / sector authority.",
            "deadline_hours": 12, "penalty": "", "on_time": False})
    if not items:
        items.append({"framework_name": "No Impact", "message":
            "No reportable regulatory impact identified. Incident contained pre-impact.",
            "deadline_hours": 0, "penalty": "", "on_time": True})
    return items


def _financial_impact(run: dict) -> dict:
    s = run["summary"]
    final_assets = run.get("final_assets", [])
    backups = s.get("backups_enabled")
    low = high = 0
    drivers: list[str] = []
    if s.get("ransomware"):
        base = (300_000, 900_000) if backups else (1_500_000, 4_000_000)
        low += base[0]
        high += base[1]
        drivers.append("Ransomware recovery & downtime" + (" (mitigated by backups)" if backups else ""))
    if s.get("exfiltrated"):
        low += 500_000
        high += 2_000_000
        drivers.append("Data breach response, notification & legal")
    if s.get("ot_impact"):
        low += 1_000_000
        high += 5_000_000
        drivers.append("OT/physical process disruption & safety remediation")
    down_assets = [a for a in final_assets if a.get("health") == "down"]
    for a in down_assets:
        crit = a.get("criticality", 3)
        low += 50_000 * crit
        high += 150_000 * crit
    if down_assets:
        names = ", ".join(a.get("name", a["id"]) for a in down_assets[:4])
        drivers.append(f"{len(down_assets)} system(s) offline ({names}), cost scaled by criticality")
    if low == 0 and high == 0:
        drivers.append("Negligible — no material impact realised")
    return {"estimate_low_usd": low, "estimate_high_usd": high, "drivers": drivers}


def _recommendations(run: dict) -> list[str]:
    s, kp = run["summary"], run["kpis"]
    recs: list[str] = []
    if kp.get("detection_rate", 0) < 0.8:
        recs.append("Improve detection coverage: expand SIEM log sources, add behavioural analytics, and tune correlation rules.")
    if kp.get("mttd_s", 0) > 600:
        recs.append("Reduce mean-time-to-detect: prioritise high-severity alert triage and add automated enrichment.")
    if s.get("exfiltrated"):
        recs.append("Deploy or strengthen DLP and egress filtering on sensitive data stores and cloud.")
    if s.get("ransomware"):
        recs.append("Harden against ransomware: enforce least privilege, application allow-listing, and maintain tested offline backups.")
    if not s.get("backups_enabled"):
        recs.append("Implement and regularly test offline, immutable backups.")
    if s.get("ot_impact"):
        recs.append("Enforce strict IT/OT segmentation and deploy OT-aware monitoring at the boundary.")
    if s.get("contained", 0) == 0 and s.get("succeeded", 0) > 0:
        recs.append("Establish and automate containment playbooks (host isolation, credential reset).")
    if s.get("attacker_max_creds", "none") == "domain_admin":
        recs.append("Implement PAM for privileged accounts and enable DCSync detection in SIEM.")
    if s.get("detected", 0) == 0 and s.get("succeeded", 0) > 0:
        recs.append("Critical: deploy baseline detection capability. No attacker actions were detected.")
    if not recs:
        recs.append("Maintain current posture; continue periodic purple-team validation.")
    return recs


def _maturity_score(run: dict) -> dict:
    kp, s = run["kpis"], run["summary"]
    detection = kp.get("detection_rate", 0) * 30
    containment = kp.get("containment_rate", 0) * 25
    prevention = kp.get("prevention_rate", 0) * 20
    recovery = 10 if s.get("backups_enabled") else 0
    impact_penalty = 0
    impact_penalty += 15 if s.get("ransomware") else 0
    impact_penalty += 15 if s.get("ot_impact") else 0
    impact_penalty += 10 if s.get("exfiltrated") else 0
    raw = 15 + detection + containment + prevention + recovery - impact_penalty
    score = max(0, min(100, round(raw)))
    band = ("Initial" if score < 25 else "Developing" if score < 50
            else "Defined" if score < 70 else "Managed" if score < 88 else "Optimised")
    return {"score": score, "band": band, "breakdown": {
        "Base": 15, "Detection": round(detection, 1), "Containment": round(containment, 1),
        "Prevention": round(prevention, 1), "Recovery": round(recovery, 1),
        "Impact Penalty": round(-impact_penalty, 1),
    }}


def _corrective_actions(run: dict) -> list[dict]:
    recs = _recommendations(run)
    s = run["summary"]
    high_impact = s.get("ot_impact") or s.get("ransomware") or s.get("exfiltrated")
    actions = []
    for i, r in enumerate(recs):
        is_critical = any(k in r.lower() for k in ("ot", "ransomware", "dlp", "backup", "critical"))
        prio = "P1" if is_critical and high_impact else "P2" if i < 3 else "P3"
        actions.append({"priority": prio, "action": r})
    actions.sort(key=lambda a: a["priority"])
    return actions


def _persistence_report(run: dict) -> dict:
    """Red persistence planted vs Blue eradication — granular matching from IRP ch.04."""
    s = run["summary"]
    planted = s.get("persistence_planted", [])
    eradicated = s.get("persistence_eradicated", False)

    # Labels for persistence types (IRP ch.04 R.E list)
    type_labels = {
        "registry_run_key": "Registry Run Key (HKCU\\...\\Run)",
        "scheduled_task": "Scheduled Task (T1053)",
        "process_injection": "Process Injection into LSASS",
        "rogue_account": "Rogue AD Account / Service Account",
        "golden_ticket": "Golden Ticket (krbtgt hash)",
        "log_deletion": "Log Deletion / Anti-forensics",
        "persistence_task": "Scheduled Task / Service Persistence",
        "cloud_persistence": "Cloud Account Persistence",
    }

    items = []
    for p in planted:
        ptype = p.get("type", "unknown")
        items.append({
            "type": ptype,
            "label": type_labels.get(ptype, ptype),
            "technique": p.get("technique", ""),
            "asset": p.get("asset_name", ""),
            "asset_id": p.get("asset_id", ""),
            "t": p.get("t", 0),
            "clock": _fmt(p.get("t", 0)),
            "eradicated": eradicated,
        })

    return {
        "total_planted": len(planted),
        "total_eradicated": len(planted) if eradicated else 0,
        "eradication_complete": eradicated,
        "eradication_rate": 1.0 if eradicated else 0.0,
        "items": items,
    }


def _vm_execution_report(run: dict) -> dict:
    """VM bridge execution summary — which techniques were executed on real VMs vs modeled."""
    s = run.get("summary", {})
    vm_results = s.get("vm_results", [])
    vm_enabled = s.get("vm_enabled", False)
    if not vm_enabled and not vm_results:
        return {"enabled": False, "total_real": 0, "total_modeled": 0, "items": []}

    # Count how many attack events happened total
    attack_count = sum(1 for e in run.get("events", []) if e.get("type") == "attack")
    real_count = len(vm_results)
    modeled_count = attack_count - real_count

    return {
        "enabled": vm_enabled,
        "total_real": real_count,
        "total_modeled": modeled_count,
        "coverage_pct": round(real_count / attack_count * 100) if attack_count else 0,
        "items": vm_results,
    }


def _decision_gate_report(run: dict) -> list[dict]:
    """Extract decision gate events from the timeline for the report."""
    gates = []
    for e in run["events"]:
        if e.get("type") == "decision":
            data = e.get("data", {})
            gates.append({
                "t": e["t"], "clock": _fmt(e["t"]),
                "gate": data.get("gate", ""),
                "title": e.get("title", ""),
                "message": e.get("message", ""),
                "followed": data.get("followed"),
                "correct_action": data.get("correct_action", ""),
                "approval_from": data.get("approval_from", ""),
            })
    return gates


def generate_report(run: dict) -> dict:
    return {
        "scenario_name": run.get("scenario_name"),
        "duration_min": run["duration_s"] // 60,
        "focus_role": run.get("focus_role", "blue"),
        "exec_summary": _exec_summary(run),
        "role_scorecards": _role_scorecards(run),
        "key_findings": _key_findings(run),
        "attack_path": _attack_path(run),
        "per_asset": _per_asset_report(run),
        "timeline": _timeline(run),
        "mitre_map": _mitre_map(run),
        "scorecard": _scorecard(run),
        "control_effectiveness": _control_effectiveness(run),
        "dwell_analysis": _dwell_analysis(run),
        "zone_analysis": _zone_analysis(run),
        "credential_timeline": _credential_timeline(run),
        "persistence_report": _persistence_report(run),
        "vm_execution": _vm_execution_report(run),
        "live_fire_validation": run.get("summary", {}).get("live_fire_validation"),
        "decision_gates": _decision_gate_report(run),
        "regulatory_impact": _regulatory_impact(run),
        "financial_impact": _financial_impact(run),
        "recommendations": _recommendations(run),
        "maturity_score": _maturity_score(run),
        "corrective_actions": _corrective_actions(run),
    }
