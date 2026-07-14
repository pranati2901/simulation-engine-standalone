"""Precondition evaluation: does an active resource cover this actor, and are a step's
required prior-state conditions satisfied? Pure functions of (world, config).

Skeleton — port from GoalCert's engine/resolve/preconditions.py, generalizing control
type checks (firewall_ids, edr, ...) to resource type_key checks.
"""
from __future__ import annotations

from ..world import ActorInstance, World


def resource_active_for(world: World, resource_type: str, target: ActorInstance | None) -> bool:
    """Is there an active resource of this type currently covering the target actor?"""
    for resource in world.resources.values():
        if resource.type_key != resource_type or not resource.active:
            continue
        if target is None or resource.covers(target):
            return True
    return False


def evaluate(condition_key: str, world: World, target: ActorInstance | None) -> tuple[bool, str | None]:
    """Evaluate a named precondition (e.g. "requires_foothold", "requires_authority:elevated").

    Returns (met, reason_if_not_met). TODO: port the full precondition vocabulary from
    GoalCert's preconditions.py and extend per plugin as needed.
    """
    if condition_key == "requires_foothold":
        return (world.driver.has_foothold(), "no_foothold")
    if condition_key.startswith("requires_authority:"):
        _, level = condition_key.split(":", 1)
        from ..enums import AuthorityScope
        required = AuthorityScope(level)
        return (world.driver.authority.rank >= required.rank, "insufficient_authority")
    return (True, None)
