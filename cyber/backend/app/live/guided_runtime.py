"""Guided runtime — drives a `GuidedScenario` (live/guided.py) over a LiveSession.

This is the generic engine the user asked for: it knows nothing W1/R5/C5-specific; it just walks
whatever phases/tasks the active scenario defines. Per-scenario behaviour lives entirely in the
scenario data, so each scenario's Red/Blue/SOC play is independent.

Model (v1, "guided tutorial" pacing):
  - A phase opens → the engine emits a briefing pop-up + the phase's SOC signal as telemetry.
  - Each role works its checklist. Completing a task emits a reactive event ("here's what just
    happened because you did this") — the toast/notification feed.
        · real_tool  → queues a REAL tool job (nmap/NetExec) against the lab; output streams back.
        · sim_red    → scripted attacker step; telemetry emitted; worm effect applied on resolve.
        · soc/blue   → defender move; its `mitigates` lever is banked for this phase.
        · observe    → a "look here" beat.
  - When every NON-optional task in the phase is done (auto-drivers complete empty seats), the phase
    RESOLVES: the worm-network effect is applied, *reduced by the mitigations the defenders managed*,
    and the next phase opens. Last phase → the run finishes with an outcome band + per-team score.

Events are emitted through the session's normal event bus (so they ride the existing WS snapshot).
Guided event kinds: g_phase · g_task · g_telemetry · g_decision · g_result.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import guided as G

if TYPE_CHECKING:                       # avoid a circular import at module load
    from .session import LiveSession


GUIDED_ROLES = ("soc", "blue", "red")   # defenders bank mitigations before Red resolves the phase


# ---------------------------------------------------------------------------
#  Run state
# ---------------------------------------------------------------------------
@dataclass
class GuidedRun:
    scenario_id: str
    net: "G.WormNetwork"
    phase_idx: int = 0
    completed: set[str] = field(default_factory=set)          # completed task ids (all phases)
    phase_mit: dict[int, set[str]] = field(default_factory=dict)  # mitigations banked per phase index
    team_score: dict[str, int] = field(default_factory=lambda: {"red": 0, "blue": 0, "soc": 0})
    started_at: float = field(default_factory=time.time)
    finished: bool = False
    outcome: str | None = None

    def scenario(self) -> "G.GuidedScenario":
        return G.GUIDED_SCENARIOS[self.scenario_id]

    def phase(self) -> "G.GuidedPhase | None":
        return self.scenario().phase(self.phase_idx)


# ---------------------------------------------------------------------------
#  Lifecycle
# ---------------------------------------------------------------------------
def attach(session: "LiveSession", scenario_id: str) -> bool:
    """Turn a started LiveSession into a guided run of `scenario_id`. Auto-arms real-tool live-fire."""
    scn = G.get_guided(scenario_id)
    if scn is None:
        return False
    run = GuidedRun(scenario_id=scenario_id, net=G.WormNetwork(total_hosts=scn.total_hosts))
    session.guided = run               # type: ignore[attr-defined]
    session.arm_live_fire(True)        # guided play = real tools on (when a lab is up)
    _enter_phase(session, run, 0, first=True)
    return True


def _enter_phase(session: "LiveSession", run: GuidedRun, idx: int, first: bool = False) -> None:
    phase = run.scenario().phase(idx)
    if phase is None:
        return
    run.phase_idx = idx
    run.phase_mit.setdefault(idx, set())
    tag = "Mission start" if first else f"Phase {idx + 1}/{len(run.scenario().phases)}"
    session._emit(
        "g_phase", f"{tag}: {phase.name}", phase.briefing, role="system", severity="high",
        data={"phase_idx": idx, "phase_id": phase.id, "mitre": phase.mitre,
              "stage_kind": phase.stage_kind, "attacker_goal": phase.attacker_goal,
              "victim_experience": phase.victim_experience})
    # The detection funnel signal for this phase lands in the SOC log.
    session._emit("g_telemetry", f"SOC signal — {phase.name}", phase.soc_signal,
                  role="soc", severity="medium", data={"phase_idx": idx})
    if phase.decision_point is not None:
        dp = phase.decision_point
        session._emit("g_decision", f"Decision point {dp.id}", dp.prompt, role="blue",
                      severity="high", data={"phase_idx": idx, **dp.public()})


# ---------------------------------------------------------------------------
#  Task completion
# ---------------------------------------------------------------------------
def complete_task(session: "LiveSession", player_id: str, task_id: str,
                  by_auto: bool = False) -> tuple[bool, str]:
    run: GuidedRun | None = getattr(session, "guided", None)
    if run is None:
        return False, "not a guided session"
    if run.finished:
        return False, "scenario already complete"
    phase = run.phase()
    if phase is None:
        return False, "no active phase"
    task = next((t for t in phase.tasks if t.id == task_id), None)
    if task is None:
        return False, "that task isn't in the current phase"
    if task.id in run.completed:
        return False, "task already done"

    if not by_auto:
        player = session.players.get(player_id)
        if player is None or player.role != task.role:
            return False, f"only the {task.role.upper()} seat can do this task"

    run.completed.add(task.id)
    _apply_task(session, run, phase, task)
    _score_task(run, task)

    # Reactive feedback — "what just happened because you did this".
    session._emit("g_task", f"✓ {task.label}", task.outcome, role=task.role, severity="info",
                  data={"phase_idx": run.phase_idx, "task_id": task.id, "kind": task.kind,
                        "does": task.does, "how": task.how, "mitigates": task.mitigates})

    _resolve_if_ready(session, run, phase)
    return True, ""


def _apply_task(session: "LiveSession", run: GuidedRun, phase: "G.GuidedPhase",
                task: "G.GuidedTask") -> None:
    if task.kind == "real_tool":
        # Emit an action event, then queue the REAL tool job against the lab (streams back async).
        ev = session._emit("action", task.label, f"{task.tool}: {task.how}", role="red",
                           severity="medium",
                           data={"action_id": task.action_id, "tool": task.tool, "guided": True,
                                 "live_fire": _queued_view(task.action_id)})
        session.pending_fire.append({"seq": ev["seq"], "action_id": task.action_id, "target_id": None})
    elif task.kind == "sim_red":
        session._emit("action", task.label, task.how, role="red", severity="medium",
                      data={"guided": True, "simulated": True, "mitre": phase.mitre})
    elif task.role in ("soc", "blue"):
        if task.mitigates:
            run.phase_mit.setdefault(run.phase_idx, set()).add(task.mitigates)
        kind = "soc" if task.role == "soc" else "response"
        session._emit(kind, task.label, task.how, role=task.role, severity="high",
                      data={"guided": True, "mitigates": task.mitigates})
    else:  # observe
        session._emit("intel", task.label, task.how, role=task.role, severity="info",
                      data={"guided": True})


def _score_task(run: GuidedRun, task: "G.GuidedTask") -> None:
    if task.kind in ("real_tool", "sim_red"):
        pts = 12
    elif task.role in ("soc", "blue"):
        pts = 18 if task.mitigates else 9
    else:
        pts = 3
    run.team_score[task.role] = run.team_score.get(task.role, 0) + pts


# ---------------------------------------------------------------------------
#  Phase resolution + worm progression
# ---------------------------------------------------------------------------
def _resolve_if_ready(session: "LiveSession", run: GuidedRun, phase: "G.GuidedPhase") -> None:
    if any(t.id not in run.completed for t in phase.gating_tasks()):
        return  # still waiting on a seat (human or auto) to finish a gating task
    _apply_network_effect(run, phase)
    session._emit("g_telemetry", f"Phase resolved: {phase.name}",
                  f"Network state — {run.net.infected}/{run.net.total_hosts} infected, "
                  f"band: {run.net.outcome_band()}", role="system", severity="medium",
                  data={"phase_idx": run.phase_idx, "network": run.net.snapshot()})
    nxt = run.phase_idx + 1
    if nxt >= len(run.scenario().phases):
        _finish(session, run)
    else:
        _enter_phase(session, run, nxt)


def _apply_network_effect(run: GuidedRun, phase: "G.GuidedPhase") -> None:
    """Apply the phase's worm delta, reduced by the mitigations the defenders banked this phase."""
    net = run.net
    eff = phase.network_effect
    mit = run.phase_mit.get(run.phase_idx, set())

    # Containment factor on this phase's new infections (best lever wins).
    if mit & {"isolate", "patch"}:
        factor = 0.12
    elif "segment" in mit:
        factor = 0.35
    elif "contain" in mit:
        factor = 0.5
    else:
        factor = 1.0
    if "early_detect" in mit:               # SOC speed shaves a bit more off
        factor *= 0.7

    add = round(eff.get("infect", 0) * factor)
    if add:
        net.infected = min(net.total_hosts, net.infected + add)

    # Kill-switch sinkhole: freeze infected hosts, halt new encryption.
    if "sinkhole" in mit:
        net.kill_switch_tripped = True
        net.dormant = net.infected
        net.r_value = 0.0
    # Vector removed → reproduction collapses.
    if mit & {"patch", "segment"}:
        net.r_value = round(max(0.0, net.r_value - 1.6), 2)
    if "isolate" in mit:
        net.r_value = 0.0
    if "segment" in mit:
        net.segmented = True
    if "patch" in mit:
        net.smbv1_patched = True

    # Recovery teardown: shadow copies gone; offline backups survive only if preserved.
    if eff.get("recovery_disabled"):
        net.recovery_disabled = True
        net.backups_safe = "backups" in mit

    # Mass encryption: live, non-dormant, non-contained infected hosts become impacted.
    if eff.get("encrypt_all") and not net.kill_switch_tripped:
        impacted_now = max(0, net.infected - net.dormant - net.contained - net.impacted)
        net.impacted = min(net.total_hosts, net.impacted + impacted_now)
        net.encrypting = 0

    # Restore from clean backups (impact phase) — only works if backups were protected.
    if "restore" in mit and net.backups_safe:
        net.recovered += net.impacted
        net.impacted = 0

    # Track contained count for the map.
    if mit & {"isolate", "contain", "segment"}:
        net.contained = min(net.total_hosts, net.contained + add + 1)


def _finish(session: "LiveSession", run: GuidedRun) -> None:
    run.finished = True
    run.outcome = run.net.outcome_band()
    total = sum(run.team_score.values())
    session._emit(
        "g_result", f"Scenario complete — {run.outcome}",
        f"Outcome: {run.outcome}.  {run.net.infected}/{run.net.total_hosts} hosts infected, "
        f"{run.net.impacted} impacted, {run.net.recovered} recovered.  "
        f"Estimated loss ${run.net.financial_loss():,}.",
        role="system", severity="critical",
        data={"outcome": run.outcome, "network": run.net.snapshot(),
              "team_score": dict(run.team_score), "total_score": total,
              "duration_s": int(time.time() - run.started_at)})
    session.status = "completed"
    session.match_result = "guided"
    # Build + persist the all-teams AAR (the "saved report" option, alongside the live in-room result).
    try:
        session.report = build_guided_report(session)
    except Exception:                       # a report failure must never break conclusion
        session.report = None
    if session.report is not None:
        _persist_guided_report(session)


# ---------------------------------------------------------------------------
#  After-Action Report (saved to DB → shows in Reports & AAR; also in the snapshot)
# ---------------------------------------------------------------------------
def build_guided_report(session: "LiveSession") -> dict:
    run: GuidedRun = session.guided                       # type: ignore[assignment]
    scn = run.scenario()
    net = run.net.snapshot()
    band = run.outcome or run.net.outcome_band()
    result = {"Contained": "blue", "Degraded": "draw", "Catastrophic": "red"}.get(band, "draw")
    verdict = {
        "Contained": "Contained — early detection and containment held the attack to minimal impact.",
        "Degraded": "Degraded — partial containment; meaningful impact and downtime.",
        "Catastrophic": "Catastrophic — the attack ran to enterprise-wide impact.",
    }.get(band, "Concluded.")
    duration_s = int(time.time() - run.started_at)

    timelines: dict[str, list[dict]] = {"red": [], "blue": [], "soc": []}
    real_count = detections = 0
    for e in session.events:
        d = e.get("data", {})
        if e["kind"] == "g_task" and e["role"] in timelines:
            timelines[e["role"]].append({"t": e["t"], "label": e["title"].replace("✓", "").strip(),
                                          "kind": d.get("kind", ""), "mitigates": d.get("mitigates", "")})
        if e["kind"] == "action" and d.get("guided"):
            if not d.get("simulated"):
                real_count += 1
            if (d.get("live_fire") or {}).get("detected"):
                detections += 1

    def findings(role: str) -> dict:
        s: list[str] = []
        w: list[str] = []
        if role == "red":
            s.append(f"Walked the full {len(scn.phases)}-phase attack chain.")
            if real_count:
                s.append(f"Executed {real_count} real tool action(s) against the Kali range.")
            if detections:
                w.append(f"{detections} action(s) were caught by the defenders.")
        elif role == "soc":
            (s if band == "Contained" else w).append(
                "Detected the intrusion early enough to drive containment." if band == "Contained"
                else "Detection lagged the attacker — impact was not prevented in time.")
        else:
            (s if net["backups_safe"] else w).append(
                "Preserved recovery — offline backups stayed safe." if net["backups_safe"]
                else "Lost recovery — backups were not protected in time.")
            if band == "Contained":
                s.append("Contained the spread before major impact.")
            elif band == "Catastrophic":
                w.append("Containment came too late — broad encryption occurred.")
        return {"strengths": s, "weaknesses": w}

    teams = {role: {"score": run.team_score.get(role, 0),
                    "kpis": {"tasks_completed": len(timelines[role])},
                    "timeline": timelines[role], "findings": findings(role)}
             for role in ("red", "soc", "blue")}
    teams["red"]["kpis"]["real_tool_actions"] = real_count
    teams["soc"]["kpis"]["detections"] = detections

    recs: list[str] = []
    if band != "Contained":
        recs.append("Act earlier in the kill chain — every phase you let pass multiplies cost and blast radius.")
    if not net["backups_safe"]:
        recs.append("Protect/isolate backups the instant recovery-inhibition is seen — rebuild vs. ruin.")
    if detections < real_count:
        recs.append("SOC: tighten detection coverage — some attacker actions ran unseen.")
    if band == "Contained":
        recs.append("Strong run — sustain the early-detection discipline and rehearse to keep it fast.")

    return {
        "session_id": session.id, "generated": "on_conclude", "guided": True,
        "scenario": {"id": scn.id, "name": scn.name, "subtitle": scn.subtitle},
        "result": result, "verdict": verdict, "outcome_band": band, "duration_s": duration_s,
        "network": net, "outcome": {"outcome_band": band, **net},
        "teams": teams,
        "mitre": [{"label": p.name, "mitre": p.mitre, "stage_kind": p.stage_kind} for p in scn.phases],
        "recommendations": recs[:6],
        "note": "Guided walkthrough AAR — saved to Reports & AAR.",
    }


def _persist_guided_report(session: "LiveSession") -> None:
    """Save the guided AAR as a Run + Report row so it appears in Reports & AAR and survives restart."""
    try:
        from app.db.base import SessionLocal
        from app.db.models import Report as ReportRow, Run as RunRow
        db = SessionLocal()
        try:
            if db.get(RunRow, session.id) is None:
                report = session.report or {}
                teams = report.get("teams", {})
                scores = {r: t.get("score", 0) for r, t in teams.items()}
                host = session.players.get(session.host_id)
                db.add(RunRow(
                    id=session.id, scenario_id=report.get("scenario", {}).get("id", "guided"),
                    scenario_name=f"[GUIDED] {session.scenario_name}",
                    operator=host.name if host else "operator", status="completed",
                    focus_role="blue", config={}, environment_spec={},
                    duration_s=report.get("duration_s", 0), scores=scores, kpis={},
                    summary={"guided": True, "outcome": report.get("outcome_band"),
                             "result": report.get("result")},
                    objectives={}, events=session.events[-100:], final_assets=[]))
                db.add(ReportRow(run_id=session.id, content=report))
                db.commit()
        finally:
            db.close()
    except Exception as exc:                # persistence must never break conclusion
        import sys
        print(f"[guided] report persist failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
#  Auto-driver — fills unoccupied seats so the walkthrough always progresses
# ---------------------------------------------------------------------------
def auto_step(session: "LiveSession") -> bool:
    """Complete one pending gating task for each AUTO seat (defenders first). Returns True if changed."""
    run: GuidedRun | None = getattr(session, "guided", None)
    if run is None or run.finished:
        return False
    phase = run.phase()
    if phase is None:
        return False
    changed = False
    for role in GUIDED_ROLES:
        if not session.is_auto(role):
            continue
        pending = next((t for t in phase.gating_tasks()
                        if t.role == role and t.id not in run.completed), None)
        if pending is not None:
            ok, _ = complete_task(session, player_id="", task_id=pending.id, by_auto=True)
            changed = changed or ok
            phase = run.phase()        # phase may have advanced; re-read
            if phase is None or run.finished:
                break
    return changed


# ---------------------------------------------------------------------------
#  Snapshot (the guided portion the frontend renders)
# ---------------------------------------------------------------------------
def _queued_view(action_id: str) -> dict:
    from app.lab import live_fire as lf
    return lf.queued_view(action_id)


def snapshot(session: "LiveSession") -> dict | None:
    run: GuidedRun | None = getattr(session, "guided", None)
    if run is None:
        return None
    scn = run.scenario()
    phase = run.phase()

    def task_view(t: "G.GuidedTask") -> dict:
        return {**t.public(), "done": t.id in run.completed}

    gating = phase.gating_tasks() if phase else []
    phase_done = sum(1 for t in gating if t.id in run.completed)

    return {
        "scenario": scn.meta(),
        "phase_idx": run.phase_idx,
        "phase_count": len(scn.phases),
        "finished": run.finished,
        "outcome": run.outcome,
        "network": run.net.snapshot(),
        "team_score": dict(run.team_score),
        "phase": phase.public() if phase else None,
        "tasks": {
            "red": [task_view(t) for t in (phase.tasks_for("red") if phase else [])],
            "blue": [task_view(t) for t in (phase.tasks_for("blue") if phase else [])],
            "soc": [task_view(t) for t in (phase.tasks_for("soc") if phase else [])],
        },
        # compact phase list for the progress sidebar (name + done state)
        "phases": [
            {"index": p.index, "name": p.name, "mitre": p.mitre, "stage_kind": p.stage_kind,
             "state": ("done" if p.index < run.phase_idx else
                       "active" if p.index == run.phase_idx else "todo")}
            for p in scn.phases
        ],
        "progress": {"phase": run.phase_idx + 1, "total": len(scn.phases),
                     "phase_done": phase_done, "phase_total": len(gating)},
        "completed": sorted(run.completed),
    }
