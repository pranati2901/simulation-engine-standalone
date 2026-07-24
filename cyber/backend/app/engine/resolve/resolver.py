"""Deterministic technique resolution: prevention, success, effects, telemetry,
detection scheduling and response scheduling. No RNG; pure functions of (world, config)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..catalog.spec import TechniqueSpec
from ..config import RunConfig
from ..enums import CredScope, Health, SecurityState
from ..events import Emit
from ..models.assets import get_asset_type
from ..posture import Posture, family_of
from ..world import AssetInstance, World
from .preconditions import control_active_for, evaluate

RESPONSE_BASE_SECONDS = 300.0
_OT_KEYS = ("ot_pivot", "ot_plc_modify")


@dataclass
class Resolution:
    status: str                       # "success" | "blocked" | "failed"
    prevented_by: str | None = None   # control type / posture lever that blocked
    reason: str | None = None         # failed precondition label
    affected_assets: list[str] = field(default_factory=list)


def resolve(
    spec: TechniqueSpec, world: World, target: AssetInstance | None, config: RunConfig,
    posture: Posture | None = None,
) -> Resolution:
    """Decide whether the technique is prevented, fails preconditions, or succeeds.

    Posture (from the teams' enabled workflow tasks) adds Blue/Red levers on top of controls.
    """
    if posture is not None:
        # Blue: egress blocked first -> exfiltration cannot leave
        if posture.prevent_egress and spec.key == "exfiltration":
            return Resolution(status="blocked", prevented_by="blue:block-egress")
        # Blue: emergency segmentation -> protect OT strongly; cross-zone lateral needs DA
        if posture.segment and target is not None and target.zone not in world.foothold_zones():
            if spec.key in _OT_KEYS and target.zone in ("ot", "ot_dmz"):
                return Resolution(status="blocked", prevented_by="blue:segmentation")
            if spec.key == "lateral_movement" \
                    and world.attacker.cred_scope.rank < CredScope.DOMAIN_ADMIN.rank:
                return Resolution(status="blocked", prevented_by="blue:segmentation")

    # 1) Prevention — an active, covering control blocks the technique at/under its difficulty.
    for ctype in sorted(spec.prevention):
        threshold = spec.prevention[ctype]
        if posture is not None and ctype == "email_sec":
            threshold -= posture.phish_potency          # Red lure reduces email-sec efficacy
        if config.difficulty.rank <= threshold and control_active_for(world, ctype, target):
            if posture is not None and ctype == "firewall_ids" and posture.c2_resilience >= 1:
                continue                                # Red C2 resilience evades egress block
            return Resolution(status="blocked", prevented_by=ctype)

    # 2) Preconditions — required attacker progress / environment.
    if spec.requires_target and target is None:
        return Resolution(status="failed", reason="no_target")
    ok, reason = evaluate(spec.preconditions, world, target)
    if not ok:
        return Resolution(status="failed", reason=reason)

    return Resolution(status="success")


def apply_effects(spec: TechniqueSpec, world: World, target: AssetInstance | None) -> list[str]:
    """Mutate world per the technique effects. Returns ids of assets whose state changed."""
    affected: list[str] = []
    for eff in spec.effects:
        if eff.kind in ("compromise", "foothold"):
            if target is not None:
                target.security_state = SecurityState.COMPROMISED
                world.attacker.add_foothold(target.id)
                affected.append(target.id)
        elif eff.kind == "suspicious":
            if target is not None and target.security_state == SecurityState.SAFE:
                target.security_state = SecurityState.SUSPICIOUS
                affected.append(target.id)
        elif eff.kind == "creds":
            world.attacker.raise_creds(CredScope(eff.value or "user"))
        elif eff.kind == "flag":
            world.attacker.flags[eff.value or "flag"] = True
        elif eff.kind == "degrade":
            if target is not None:
                target.health = Health.DEGRADED
                affected.append(target.id)
        elif eff.kind == "down":
            if target is not None:
                target.health = Health.DOWN
                target.security_state = SecurityState.COMPROMISED
                affected.append(target.id)
        elif eff.kind == "disable_control":
            ct = eff.value or ""
            if ct and ct not in world.attacker.disabled_control_types:
                world.attacker.disabled_control_types.append(ct)
        elif eff.kind == "exfiltrate":
            world.attacker.flags["exfiltrated"] = True
            if target is not None:
                target.props["exfiltrated"] = True
    return affected


def build_emits(spec: TechniqueSpec, world: World, target: AssetInstance | None) -> list[Emit]:
    """Telemetry produced by the technique and by the affected asset's reaction model."""
    out: list[Emit] = []
    tname = target.name if target is not None else "the environment"
    for tmpl in spec.emits:
        out.append(Emit(channel=tmpl.channel, severity=tmpl.severity,
                        text=tmpl.text.replace("{target}", tname)))
    if spec.react_kind and target is not None:
        out.extend(get_asset_type(target.type_key).react(target, spec.react_kind, world))
    return out


def compute_detection(
    spec: TechniqueSpec, world: World, target: AssetInstance | None,
    config: RunConfig, success_t: int, posture: Posture | None = None,
) -> tuple[int, str, str] | None:
    """Earliest detection across active covering controls -> (detect_t, control_type, control_id).

    Posture scales the base latency: SOC detection tasks speed it up; Red evasion/low-and-slow
    slow it down (per technique family).
    """
    factor = posture.detection_factor(family_of(spec.key)) if posture is not None else 1.0
    best: tuple[int, str, str] | None = None
    for ctype in sorted(spec.detection):
        ctrl = control_active_for(world, ctype, target)
        if ctrl is None:
            continue
        detect_t = success_t + config.latency(spec.detection[ctype] * factor)
        cand = (detect_t, ctype, ctrl.id)
        if best is None or (cand[0], cand[1]) < (best[0], best[1]):
            best = cand
    return best


def compute_response(
    spec: TechniqueSpec, target: AssetInstance | None, config: RunConfig, detect_t: int
) -> int | None:
    """When SOC/blue containment lands, if this technique is containable."""
    if not spec.containable or target is None:
        return None
    return detect_t + config.latency(RESPONSE_BASE_SECONDS)
