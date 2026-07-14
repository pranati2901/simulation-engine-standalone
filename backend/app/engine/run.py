"""Layer 1 — Core Simulation Engine: the deterministic run loop.

v1 scope (per the GoalCert User Flow doc, Part A.3 "Competency Check"): a single
response role reacts to fault-injected scenario steps built from an environment
snapshot. This is NOT a multi-role adversarial simulation — there is one operator
role per domain (maintenance crew, signal technician, facilities engineer, signals
operator, ...), and the engine scores whether that role responds correctly and in
time to each injected fault. That produces the exact artifact the user flow doc
calls for at Step 5: a signed clearance record backed by an evidence chain.

Pure and deterministic: no RNG, no wall-clock. Same (scenario, environment, config)
always produces the same timeline — every number in the UI changes only because you
changed a config knob (readiness, difficulty), which is what makes it legible as a
training tool instead of a black box.

Multi-role adversarial scheduling, cascading scenario graphs, and multiplayer are
explicitly out of scope for v1 — see docs/ARCHITECTURE.md.
"""
from __future__ import annotations

from .catalog.spec import get_action
from .conditions import eval_condition
from .config import RunConfig
from .enums import ActorState, EventType, Severity, Side
from .environment import EnvironmentSpec, build_world
from .events import SimEvent
from .kpis import compute_kpis
from .models.actors import get_actor_type
from .models.resources import get_resource_type
from .resolve import resolver as R
from .result import ClearanceRecord, ObjectiveStatus, RunResult
from .scenario import Scenario, TargetSelector
from .world import ActorInstance, World

DETECT_BASE_WITH_MONITOR_S = 120.0    # base detection latency if a monitoring resource is active
DETECT_BASE_NO_MONITOR_S = 600.0      # base detection latency with no monitoring — slower, realistic
RESPONSE_BASE_S = 300.0               # base time for the response role to act once detected

# Minimum operator readiness (0-100, see RunConfig.readiness) required to pass a
# decision gate at each risk level. Change these to retune difficulty economy.
GATE_READINESS_THRESHOLD = {"low": 20, "medium": 40, "high": 65, "extreme": 85}


def _select_target(selector: TargetSelector | None, world: World) -> ActorInstance | None:
    if selector is None:
        return None
    pool = world.actors_by_role(selector.value) if selector.by == "role" else world.actors_by_type(selector.value)
    return pool[0] if pool else None


def _has_monitor_resource(world: World) -> bool:
    """A resource counts as a monitor if its type key signals detection capability.
    Kept as a simple substring convention so any domain plugin can opt in without a
    new registry — e.g. "predictive_maintenance", "cctv_monitoring", "signal_monitoring".
    """
    return any(
        r.active and any(tag in r.type_key for tag in ("monitor", "predictive", "detection"))
        for r in world.resources.values()
    )


def run(scenario: Scenario, environment: EnvironmentSpec, config: RunConfig) -> RunResult:
    world = build_world(environment, get_actor_type, get_resource_type)
    events: list[SimEvent] = []
    seq = 0

    def emit(t: int, type_: EventType, **kw) -> SimEvent:
        nonlocal seq
        ev = SimEvent(seq=seq, t=t, type=type_, scenario_id=scenario.id, **kw)
        events.append(ev)
        seq += 1
        return ev

    emit(0, EventType.SYSTEM, side=Side.SYSTEM, title="Run started",
         message=f"Scenario '{scenario.name}' initialised.")

    has_monitor = _has_monitor_resource(world)
    detect_base = DETECT_BASE_WITH_MONITOR_S if has_monitor else DETECT_BASE_NO_MONITOR_S

    attempts = successes = detected = contained = prevented = 0
    dwells: list[int] = []
    resolution_times: list[int] = []
    first_detection_t: int | None = None
    current_phase: str | None = None

    for step in sorted(scenario.steps, key=lambda s: s.at_min):
        if step.phase != current_phase:
            current_phase = step.phase
            emit(config.latency(step.at_min * 60), EventType.PHASE, side=Side.SYSTEM,
                 phase=current_phase, title=f"Phase: {current_phase}",
                 message=f"Entering phase '{current_phase}'.")

        spec = get_action(step.action)
        target = _select_target(step.target, world)
        fault_t = config.latency(step.at_min * 60)
        resolution = R.resolve(spec, world, target, config)

        if resolution.status == "blocked":
            prevented += 1
            emit(fault_t, EventType.BLOCK, side=Side.SYSTEM, actor_id=target.id if target else None,
                 actor_label=target.name if target else None, action=step.action, phase=step.phase,
                 title=f"{spec.name} prevented", severity=Severity.LOW,
                 message=f"Blocked by active resource ({resolution.prevented_by}).")
            continue

        if resolution.status == "failed":
            emit(fault_t, EventType.FAIL, side=Side.SYSTEM, action=step.action, phase=step.phase,
                 title=f"{spec.name} did not trigger",
                 message=resolution.reason or "precondition not met")
            continue

        # success: the fault/event actually occurs
        successes += 1
        emit(fault_t, EventType.ACTION, side=Side.SYSTEM, actor_id=target.id if target else None,
             actor_label=target.name if target else None, action=step.action, phase=step.phase,
             title=step.label or spec.name, severity=Severity.MEDIUM,
             message=f"{spec.name} triggered.")

        if target is None:
            continue  # untargeted step = a logged downstream consequence, not response-gated in v1

        target.state = ActorState.AT_RISK
        attempts += 1

        detect_t = fault_t + config.latency(detect_base)
        detected += 1
        dwells.append(detect_t - fault_t)
        first_detection_t = detect_t if first_detection_t is None else min(first_detection_t, detect_t)
        target.state = ActorState.DEGRADED
        emit(detect_t, EventType.DETECTION, side=Side.MONITOR, actor_id=target.id, actor_label=target.name,
             action=step.action, phase=step.phase, title=f"{spec.name} detected", severity=Severity.MEDIUM,
             message="Deviation flagged for response." if has_monitor else
                     "Deviation flagged for response (no automated monitor — manual detection).")

        gate = next((g for g in scenario.decision_gates if g.trigger == step.id), None)
        response_t = detect_t + config.latency(RESPONSE_BASE_S)
        correct = True
        if gate is not None:
            threshold = GATE_READINESS_THRESHOLD.get(gate.risk_level, 40)
            correct = config.readiness >= threshold
            if correct:
                contained += 1
            emit(response_t, EventType.DECISION, side=Side.RESPONSE, actor_id=target.id,
                 actor_label=target.name, action=step.action, phase=step.phase, title=gate.name,
                 severity=Severity.INFO if correct else Severity.CRITICAL,
                 message=(f"Correct response taken: {gate.correct_action}") if correct else
                         (f"Response missed/too slow — {gate.consequence_of_delay or 'risk unresolved.'} "
                          f"(needed readiness >= {threshold}, had {config.readiness})"))
        else:
            contained += 1

        resolution_times.append(response_t - fault_t)
        target.state = ActorState.RECOVERED if correct else ActorState.FAILED
        emit(response_t, EventType.RESPONSE, side=Side.RESPONSE, actor_id=target.id, actor_label=target.name,
             action=step.action, phase=step.phase, severity=Severity.INFO if correct else Severity.CRITICAL,
             title="Response applied" if correct else "Response ineffective",
             message=f"{target.name} -> {target.state.value}.")

    kpis = compute_kpis(attempts=attempts, successes=successes, detected=detected, contained=contained,
                         prevented=prevented, dwells=dwells, resolution_times=resolution_times,
                         first_detection_t=first_detection_t)

    context = {**kpis, "attempts": attempts, "successes": successes, "detected": detected,
               "contained": contained, "prevented": prevented}
    objectives_status: list[ObjectiveStatus] = []
    for obj in scenario.objectives:
        met = eval_condition(obj.condition, context) if obj.condition else (attempts > 0 and contained == attempts)
        objectives_status.append(ObjectiveStatus(text=obj.text, met=met))

    all_met = all(o.met for o in objectives_status) if objectives_status else (attempts > 0 and contained == attempts)
    evidence = [f"{e.title}: {e.message}" for e in events
                if e.type in (EventType.DETECTION, EventType.DECISION, EventType.RESPONSE)]
    clearance = ClearanceRecord(
        certified=all_met, procedure=scenario.name, domain=scenario.domain,
        readiness_used=config.readiness, difficulty=config.difficulty.value, evidence=evidence,
    )
    score = round(100 * (contained / attempts), 1) if attempts else 100.0

    total_t = max((e.t for e in events), default=0)
    emit(total_t, EventType.SYSTEM, side=Side.SYSTEM,
         title="Run complete", severity=Severity.INFO if all_met else Severity.HIGH,
         message=f"{'CERTIFIED' if all_met else 'NOT CERTIFIED'} — {contained}/{attempts} faults correctly resolved.")

    return RunResult(
        scenario_id=scenario.id,
        duration_s=config.duration_min * 60,
        focus_role=config.focus_role.value,
        events=sorted(events, key=lambda e: (e.t, e.seq)),
        scores={"operator": score},
        kpis=kpis,
        summary={"clearance": clearance.model_dump(), "attempts": attempts,
                 "contained": contained, "prevented": prevented},
        objectives={"operator": objectives_status},
        environment=[a.model_dump() for a in world.actors.values()],
        final_actors=[a.model_dump() for a in world.actors.values()],
        workflows=[],
        role_tasks={},
    )
