"""Deterministic step resolution: prevention, success, effects, telemetry, detection
scheduling and response scheduling. No RNG; pure functions of (world, config).

This is the heart of the engine and the piece most worth porting carefully from
GoalCert's engine/resolve/resolver.py — the *pattern* (check resources -> check
preconditions -> apply effects -> emit telemetry -> schedule detection/response) is
fully generic. Only the specific lever names are cyber-flavoured there.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..catalog.spec import ActionSpec
from ..config import RunConfig
from ..events import Emit
from ..posture import Posture
from ..world import ActorInstance, World
from .preconditions import evaluate, resource_active_for

RESPONSE_BASE_SECONDS = 300.0


@dataclass
class Resolution:
    status: str                       # "success" | "blocked" | "failed"
    prevented_by: str | None = None   # resource type / posture lever that blocked it
    reason: str | None = None         # failed precondition label
    affected_actors: list[str] = field(default_factory=list)
    telemetry: list[Emit] = field(default_factory=list)


def resolve(
    spec: ActionSpec, world: World, target: ActorInstance | None, config: RunConfig,
    posture: Posture | None = None,
) -> Resolution:
    """Decide whether the action is prevented, fails preconditions, or succeeds.

    TODO: port the full resolution logic from GoalCert's resolver.py:
      1. Posture-level overrides (e.g. an enabled "isolate" task blocks spread actions
         outright before resource checks even run).
      2. Resource-based prevention — an active, covering resource blocks the action at
         or under its difficulty threshold (spec.prevention: dict[resource_type, threshold]).
      3. Preconditions — required driver progress / environment state
         (spec.requires_target, spec.preconditions).
      4. On success: apply spec.effects to `target` / world, collect telemetry.
    """
    if posture is not None:
        if posture.isolate and target is not None and target.zone not in world.foothold_zones():
            return Resolution(status="blocked", prevented_by="response:isolate")
        if posture.contain_spread and spec.category == "spread":
            return Resolution(status="blocked", prevented_by="response:contain_spread")

    for rtype, threshold in sorted(spec.prevention.items()):
        if config.difficulty.rank <= threshold and resource_active_for(world, rtype, target):
            return Resolution(status="blocked", prevented_by=rtype)

    if spec.requires_target and target is None:
        return Resolution(status="failed", reason="no_target")

    for cond in spec.preconditions:
        met, reason = evaluate(cond, world, target)
        if not met:
            return Resolution(status="failed", reason=reason)

    affected = [target.id] if target is not None else []
    return Resolution(status="success", affected_actors=affected, telemetry=list(spec.telemetry))
