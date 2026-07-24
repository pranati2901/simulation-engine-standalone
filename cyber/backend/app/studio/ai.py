"""The Scenario Studio agent — Anthropic-backed reasoning with deterministic fallbacks.

Every capability works WITHOUT a key (deterministic stub) so the product runs before a key is added;
with a key it delegates to Claude. The HTTP call uses the stdlib (no SDK dependency) so it never
breaks the import graph. Capabilities: author a spec from NL, simulate a run (in-context, no physics),
analyse the outcome, build an interactive repair procedure, and coach a trainee.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from . import catalog
from .models import Procedure, RunMetrics, ScenarioSpec, SimEvent, SimulationResult, TrainStep
from .settings_store import AiConfig

logger = logging.getLogger("studio.ai")
_API_URL = "https://api.anthropic.com/v1/messages"


# ── raw Anthropic call (stdlib) ───────────────────────────────────────
def _call(cfg: AiConfig, system: str, user: str, max_tokens: int = 1200) -> str | None:
    if not cfg.enabled:
        return None
    body = json.dumps({
        "model": cfg.model, "max_tokens": max_tokens, "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(_API_URL, data=body, method="POST", headers={
        "x-api-key": cfg.api_key, "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        parts = data.get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:  # noqa: BLE001
        logger.warning("Anthropic call failed (%s); using stub", e)
        return None


def _call_json(cfg: AiConfig, system: str, user: str, max_tokens: int = 1600) -> dict | None:
    text = _call(cfg, system + "\n\nReturn ONLY valid minified JSON — no prose, no markdown fences.",
                 user, max_tokens)
    if not text:
        return None
    try:
        s, e = text.find("{"), text.rfind("}")
        return json.loads(text[s:e + 1]) if s >= 0 and e > s else None
    except (ValueError, TypeError):
        return None


def ai_mode(cfg: AiConfig) -> str:
    return "agent" if cfg.enabled else "stub"


# ── 1. Author a runnable spec from natural language ───────────────────
def _match_fault(description: str, domain: str) -> str:
    p = (description or "").lower()
    for f in catalog.faults(domain):
        fid = f["id"]
        if fid in p or fid.split("_")[0] in p or f.get("label", "").lower() in p:
            return fid
    return "none"


def _author_stub(description: str, domain: str, kind: str, horizon_min: float) -> ScenarioSpec:
    sysname = catalog.DOMAINS.get(domain, catalog.DOMAINS["generic"])["system"]
    fault = _match_fault(description, domain)
    name = (description or f"{kind.title()} on {sysname}").strip()
    name = (name[:70] + "…") if len(name) > 72 else name
    sev = 0.75 if kind == "fault" else 0.65
    return ScenarioSpec(
        name=name, domain=domain, kind=kind, system=sysname, fault=fault,
        severity=sev, intensity=0.85, horizon_min=horizon_min, description=description,
        rationale=(f"Mapped the request to the '{fault}' fault." if fault != "none"
                   else "Modelled as an external operating situation (no single component fault)."),
        expected_outcome="Conditions degrade over the horizon; early detection and mitigation cap the impact.",
        objectives=["Detect the developing situation early",
                    "Take mitigating action before material impact",
                    "Keep the system within safe operating limits"])


def author_scenario(cfg: AiConfig, description: str, domain: str, kind: str,
                    horizon_min: float = 60.0) -> ScenarioSpec:
    stub = _author_stub(description, domain, kind, horizon_min)
    faults = catalog.faults(domain)
    cat = "\n".join(f"  - {f['id']}: {f['label']}" for f in faults) or "  (none — use 'none')"
    system = (
        f"You are the Scenario Builder for a {catalog.DOMAINS.get(domain, {}).get('label', domain)} "
        "operations twin. Turn the operator's free-text request into a runnable what-if spec. "
        f"'kind' is '{kind}' ({'a component/system fault' if kind == 'fault' else 'an external operating situation'}). "
        f"Choose 'fault' as EXACTLY one id from this catalogue or 'none':\n{cat}\n"
        "Pick severity 0..1, intensity 0..1, and a realistic horizon_min. Give 2-4 objectives a good "
        "response should achieve. Fields: name, system, fault, severity, intensity, horizon_min, "
        "rationale, expected_outcome, objectives (string array).")
    data = _call_json(cfg, system, f"Domain: {domain}\nKind: {kind}\nRequest: {description}", 1400)
    if not data:
        return stub
    try:
        fault = data.get("fault", stub.fault)
        if fault != "none" and fault not in {f["id"] for f in faults}:
            fault = stub.fault
        return ScenarioSpec(
            name=str(data.get("name") or stub.name)[:80], domain=domain, kind=kind,
            system=str(data.get("system") or stub.system), fault=fault,
            severity=float(data.get("severity", stub.severity)),
            intensity=float(data.get("intensity", stub.intensity)),
            horizon_min=float(data.get("horizon_min", horizon_min)),
            description=description, rationale=str(data.get("rationale", ""))[:400],
            expected_outcome=str(data.get("expected_outcome", ""))[:300],
            objectives=[str(o)[:160] for o in (data.get("objectives") or stub.objectives)][:5])
    except (ValueError, TypeError):
        return stub


# ── 2. Simulate the run (in-context, no physics) ──────────────────────
def _band_for(sev: float) -> str:
    return ("Contained" if sev < 0.4 else "Degraded" if sev < 0.65
            else "Severe" if sev < 0.85 else "Critical")


def _simulate_stub(spec: ScenarioSpec) -> SimulationResult:
    h = spec.horizon_min
    sev = spec.severity
    band = _band_for(sev)
    flabel = catalog.fault_label(spec.domain, spec.fault) if spec.fault != "none" else "operating stress"
    detect = round(h * (0.28 - 0.12 * sev), 1)          # earlier detection when more severe/obvious
    impact = round(h * (0.62 + 0.2 * (1 - sev)), 1) if band in ("Severe", "Critical") else None
    sv = lambda x: SEV_ORDER[min(len(SEV_ORDER) - 1, max(0, x))]  # noqa: E731
    tl = [
        SimEvent(t_min=0.0, phase="Onset", actor="system",
                 title=f"{spec.system}: {flabel} begins under {int(spec.intensity*100)}% load",
                 detail=f"{spec.description or 'The scenario starts.'} Baseline drifts as conditions build.",
                 severity=sv(1)),
        SimEvent(t_min=detect, phase="Detection", actor="monitor",
                 title="Deviation crosses the monitoring threshold",
                 detail="Trend monitoring flags the developing situation; an alert is raised for triage.",
                 severity=sv(2)),
        SimEvent(t_min=round(h * 0.5, 1), phase="Escalation", actor="system",
                 title="Condition escalates",
                 detail=f"The {flabel} intensifies; secondary signals begin to move.",
                 severity=sv(3 if sev >= 0.6 else 2)),
    ]
    if impact is not None:
        tl.append(SimEvent(t_min=impact, phase="Impact", actor="system",
                           title="Material impact reached",
                           detail=f"Operating limits are exceeded — {band.lower()} impact to {spec.system}.",
                           severity=sv(4 if band == "Critical" else 3)))
    tl.append(SimEvent(t_min=round(h * 0.85, 1), phase="Response", actor="operator",
                       title="Mitigation applied",
                       detail="Operators intervene per procedure; the trajectory bends back toward limits.",
                       severity=sv(1)))
    tl.append(SimEvent(t_min=h, phase="Settle", actor="system",
                       title="Horizon reached — situation settled",
                       detail=f"Outcome: {band}. Residual risk remains until root-cause action is taken.",
                       severity=sv(0)))
    metrics = RunMetrics(
        time_to_detect_min=detect, time_to_impact_min=impact, peak_severity=sev,
        downtime_min=round(sev * h * 0.4, 1) if band in ("Severe", "Critical") else 0.0,
        affected_units=max(0, round(sev * 8)))
    dets = ["Trend/threshold monitoring on the primary signal",
            "Rate-of-change alert as the deviation accelerates"]
    mits = ["Reduce load / intensity to slow the trajectory",
            "Dispatch inspection and stage spares for the likely component",
            "Impose protective limits until root cause is confirmed"]
    risks = [f"Unmitigated {flabel} reaches operating limits within the horizon",
             "Secondary systems degrade if the primary is not addressed"]
    return SimulationResult(outcome_band=band,
                            headline=f"{spec.system}: {flabel} → {band.lower()} outcome over {int(h)} min",
                            timeline=sorted(tl, key=lambda e: e.t_min), metrics=metrics,
                            detections=dets, mitigations=mits, risks=risks)


SEV_ORDER = ["info", "low", "medium", "high", "critical"]


def simulate(cfg: AiConfig, spec: ScenarioSpec) -> SimulationResult:
    stub = _simulate_stub(spec)
    system = (
        f"You are a senior operations & reliability engineer simulating a what-if on a {spec.domain} "
        f"system ('{spec.system}'). There is NO physics engine — YOU simulate the outcome in-context, "
        "grounded and realistic for this domain. Produce a timeline of 5-8 ordered events over the "
        "horizon (each: t_min, phase, title, detail, severity in info|low|medium|high|critical, actor), "
        "an outcome_band (Contained|Degraded|Severe|Critical), a one-line headline, structured metrics "
        "(time_to_detect_min, time_to_impact_min or null, peak_severity 0..1, downtime_min, "
        "affected_units), and short lists: detections, mitigations, risks. Be specific to the scenario.")
    user = (f"Scenario spec:\n{spec.model_dump_json()}")
    data = _call_json(cfg, system, user, 2600)
    if not data:
        return stub
    try:
        tl = []
        for e in data.get("timeline", []) or []:
            sev = str(e.get("severity", "info")).lower()
            tl.append(SimEvent(
                t_min=float(e.get("t_min", 0)), phase=str(e.get("phase", ""))[:40],
                title=str(e.get("title", ""))[:160], detail=str(e.get("detail", ""))[:400],
                severity=sev if sev in SEV_ORDER else "info", actor=str(e.get("actor", "system"))[:20]))
        if not tl:
            return stub
        m = data.get("metrics", {}) or {}
        band = str(data.get("outcome_band", stub.outcome_band))
        band = band if band in ("Contained", "Degraded", "Severe", "Critical") else stub.outcome_band
        return SimulationResult(
            outcome_band=band, headline=str(data.get("headline", stub.headline))[:200],
            timeline=sorted(tl, key=lambda x: x.t_min),
            metrics=RunMetrics(
                time_to_detect_min=_fnum(m.get("time_to_detect_min")),
                time_to_impact_min=_fnum(m.get("time_to_impact_min")),
                peak_severity=float(m.get("peak_severity", spec.severity)),
                downtime_min=float(m.get("downtime_min", 0) or 0),
                affected_units=int(m.get("affected_units", 0) or 0)),
            detections=[str(x)[:160] for x in (data.get("detections") or stub.detections)][:6],
            mitigations=[str(x)[:160] for x in (data.get("mitigations") or stub.mitigations)][:6],
            risks=[str(x)[:160] for x in (data.get("risks") or stub.risks)][:6])
    except (ValueError, TypeError):
        return stub


def _fnum(v) -> float | None:
    try:
        return None if v is None else float(v)
    except (ValueError, TypeError):
        return None


# ── 3. Narrative analysis of the outcome ──────────────────────────────
def analyze(cfg: AiConfig, spec: ScenarioSpec, sim: SimulationResult) -> str:
    def _stub() -> str:
        m = sim.metrics
        bits = [f"Outcome: {sim.outcome_band}. {sim.headline}."]
        if m.time_to_detect_min is not None:
            bits.append(f"The situation becomes detectable at about {m.time_to_detect_min:.0f} min.")
        if m.time_to_impact_min is not None:
            lead = (m.time_to_impact_min - (m.time_to_detect_min or 0))
            bits.append(f"Material impact by ~{m.time_to_impact_min:.0f} min — roughly a "
                        f"{lead:.0f}-minute window to act.")
        else:
            bits.append("No hard operating limit is crossed within the horizon if mitigations are applied.")
        if sim.mitigations:
            bits.append("Key actions: " + "; ".join(sim.mitigations[:3]) + ".")
        return " ".join(bits)

    out = _call(cfg,
                f"You are a senior maintenance/reliability engineer for a {spec.domain} system. Given a "
                "what-if scenario and its simulated projection, explain in plain English: what happens, "
                "which subsystem leads the degradation, the time-to-limit and the window to act, and the "
                "precautions/maintenance to have ready. Be specific and grounded. 4-6 sentences, no preamble.",
                f"Machine: {spec.system}\nSpec: {spec.model_dump_json()}\nProjection: {sim.model_dump_json()}",
                700)
    return out or _stub()


# ── 4. Interactive repair procedure (training) ────────────────────────
def _procedure_stub(domain: str, system: str, fault: str, title: str) -> Procedure:
    flabel = catalog.fault_label(domain, fault) if fault and fault != "none" else "the fault"
    return Procedure(
        title=f"Repair: {title or flabel}", fault=fault or "none", domain=domain, system=system,
        summary=f"Isolate, diagnose, repair and verify {system} after {flabel}.",
        steps=[
            TrainStep(id="S1", title="Isolate & make safe",
                      action=f"Apply lockout/tagout to {system} and confirm a zero-energy state.",
                      rationale="Protects the technician before any intervention.",
                      criteria="Energy isolated and verified.", safety=True, requires=[],
                      skip_consequence="Live-energy hazard during the repair; risk of injury and secondary damage.",
                      wrong_order_consequence="N/A — this must be first."),
            TrainStep(id="S2", title="Diagnose the fault",
                      action="Confirm the faulted component from telemetry and inspection.",
                      rationale="Targets the real root cause instead of guessing.",
                      criteria="Root cause confirmed against the readings.", requires=["S1"],
                      skip_consequence="You may repair the wrong component and the fault returns.",
                      wrong_order_consequence="Diagnosing a live system is unsafe and inaccurate."),
            TrainStep(id="S3", title="Repair / replace",
                      action=f"Service or replace the component responsible for {flabel}.",
                      rationale="Restores the system to spec.", criteria="Component within spec.",
                      requires=["S1", "S2"], skip_consequence="The fault persists and impact continues.",
                      wrong_order_consequence="Repairing before diagnosis wastes the window on the wrong part."),
            TrainStep(id="S4", title="Recalibrate / re-tension",
                      action="Restore setpoints, calibration or tension to nominal.",
                      rationale="A correct part still fails if mis-set.", criteria="Setpoints at nominal.",
                      requires=["S3"], skip_consequence="The system runs off-nominal and re-degrades.",
                      wrong_order_consequence="Calibrating before the repair is meaningless."),
            TrainStep(id="S5", title="Verify & return to service",
                      action="Re-run and confirm all readings are within limits.",
                      rationale="Proves the fix before handing back.", criteria="All signals within limits.",
                      requires=["S1", "S2", "S3", "S4"], skip_consequence="An undetected residual fault ships to production.",
                      wrong_order_consequence="You cannot verify before repairing and calibrating."),
        ],
        success_criteria="All signals within limits, the fault cleared, and the system returned to service.",
        common_mistakes=["Skipping the safety isolation (working live).",
                         "Replacing a part before inspection confirms the failure mode.",
                         "Returning to service without a verification run."])


def build_procedure(cfg: AiConfig, domain: str, system: str, fault: str,
                    title: str = "", context: str = "") -> Procedure:
    stub = _procedure_stub(domain, system, fault, title)
    system_prompt = (
        f"You are a master maintenance trainer for a {domain} system ('{system}'). Produce a complete, "
        f"correctly-ordered repair procedure a trainee can follow for the fault '{fault}'"
        + (f" arising from: {title}. {context}" if title else "") + ". "
        "For EACH step give: id ('S1','S2',… in correct order), title, action, rationale, criteria, "
        "safety (bool), requires (array of prerequisite step ids), skip_consequence, "
        "wrong_order_consequence. Order safety-first, diagnose before repair, verify last. Also give a "
        "title, summary, success_criteria, and common_mistakes (string array). Be specific to this "
        "system — name real components and signals.")
    data = _call_json(cfg, system_prompt, f"Domain: {domain}\nSystem: {system}\nFault: {fault}\n"
                                          f"Scenario: {title}\nContext: {context}", 4000)
    if not data or not data.get("steps"):
        return stub
    try:
        steps = []
        for s in data["steps"]:
            steps.append(TrainStep(
                id=str(s.get("id", f"S{len(steps)+1}"))[:8], title=str(s.get("title", ""))[:80],
                action=str(s.get("action", ""))[:300], rationale=str(s.get("rationale", ""))[:300],
                criteria=str(s.get("criteria", ""))[:200], safety=bool(s.get("safety", False)),
                requires=[str(r)[:8] for r in (s.get("requires") or [])],
                skip_consequence=str(s.get("skip_consequence", ""))[:300],
                wrong_order_consequence=str(s.get("wrong_order_consequence", ""))[:300]))
        if not steps:
            return stub
        return Procedure(
            title=str(data.get("title", stub.title))[:120], fault=fault or "none", domain=domain,
            system=system, summary=str(data.get("summary", stub.summary))[:400], steps=steps,
            success_criteria=str(data.get("success_criteria", stub.success_criteria))[:300],
            common_mistakes=[str(m)[:200] for m in (data.get("common_mistakes") or stub.common_mistakes)][:8])
    except (ValueError, TypeError):
        return stub


# ── 5. Training coach chat ────────────────────────────────────────────
def coach_reply(cfg: AiConfig, messages: list[dict], context: dict) -> str:
    def _stub() -> str:
        q = ""
        for m in reversed(messages or []):
            if m.get("role") == "user":
                q = (m.get("content") or "").lower()
                break
        if any(k in q for k in ("skip", "isolation", "loto", "safety")):
            return ("Skipping the safety isolation is the riskiest mistake here — you'd be working on a "
                    "live system, risking injury and secondary damage. Always isolate before any physical work.")
        if any(k in q for k in ("order", "why", "sequence", "before", "after")):
            return ("The order matters: isolate, diagnose to target the right part, repair, recalibrate, "
                    "then verify. Each step depends on the one before it — that's why the flow is fixed.")
        if any(k in q for k in ("risk", "worst", "dangerous", "mistake")):
            return ("The two costly mistakes are (1) opening the system before lockout/tagout, and "
                    "(2) replacing a part before inspection confirms the failure mode — you fix the wrong "
                    "thing and the fault returns.")
        return ("Work the steps in order: isolate first, confirm the failure before replacing anything, "
                "recalibrate, and finish with a verification run. Ask me 'what if I skip X?' to explore "
                "consequences. (Local coach — add an Anthropic key in Settings for full coaching.)")

    if not cfg.enabled:
        return _stub()
    system = (
        "You are an interactive maintenance TRAINING coach. The trainee is working a repair procedure. "
        "Teach by doing: answer questions, and when they ask 'what if I skip / reorder / do X', explain "
        "the concrete consequence, why the correct flow matters, and the safe next move. Concise (3-6 "
        "sentences), specific to the steps, encouraging. Context:\n" + json.dumps(context, default=str)[:4000])
    out = _call(cfg, system, "\n".join(f"{m.get('role')}: {m.get('content','')}" for m in messages[-10:]), 600)
    return out or _stub()


# ── 6. AI Maintenance Director — cinematic autonomous-repair beats ────
def director_beats(cfg: AiConfig, procedure: Procedure) -> list[dict]:
    """A short ordered narration of an autonomous repair, one beat per step (+ intro/outro)."""
    beats = [{"kind": "intro", "title": "AI Maintenance Director engaged",
              "text": f"Autonomous repair for {procedure.title}. {procedure.summary}"}]
    for i, s in enumerate(procedure.steps, 1):
        beats.append({"kind": "safety" if s.safety else "step", "step": s.id,
                      "title": f"{i}. {s.title}", "text": s.action,
                      "criteria": s.criteria})
    beats.append({"kind": "outro", "title": "Repair complete — returned to service",
                  "text": procedure.success_criteria})
    return beats
