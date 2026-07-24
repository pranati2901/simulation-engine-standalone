"""Precondition evaluation and control-coverage lookup (deterministic)."""
from __future__ import annotations

from ..catalog.spec import Precondition
from ..enums import CredScope
from ..world import AssetInstance, ControlInstance, World


def control_active_for(
    world: World, control_type: str, target: AssetInstance | None
) -> ControlInstance | None:
    """First active control of the type that applies at the relevant point.

    Global controls apply regardless of target; asset/zone-scoped controls must cover the
    target (and a target is therefore required for them to apply).
    """
    if control_type in world.attacker.disabled_control_types:
        return None
    for c in world.controls_of_type(control_type):
        if not c.active:
            continue
        if c.scope == "global":
            return c
        if target is not None and c.covers(target):
            return c
    return None


def _check(pre: Precondition, world: World, target: AssetInstance | None) -> bool:
    k = pre.kind
    if k == "start":
        return True
    if k == "foothold":
        return world.attacker.has_foothold()
    if k == "creds":
        need = CredScope(pre.value or "user")
        return world.attacker.cred_scope.rank >= need.rank
    if k == "asset":
        return world.has_type(pre.value or "")
    if k == "flag":
        return bool(world.attacker.flags.get(pre.value or "", False))
    if k == "not_flag":
        return not world.attacker.flags.get(pre.value or "", False)
    if k == "reachable":
        return target is not None and world.reachable(target)
    return False


def evaluate(
    preconditions: list[Precondition], world: World, target: AssetInstance | None
) -> tuple[bool, str | None]:
    """Return (ok, failed_reason). All preconditions must hold (logical AND)."""
    for pre in preconditions:
        if not _check(pre, world, target):
            label = pre.kind + (f":{pre.value}" if pre.value else "")
            return False, label
    return True, None
