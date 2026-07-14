"""Aggregates each role's enabled workflow tasks into a deterministic Posture — the set
of levers that mechanically modulate detection, prevention, response latency,
segmentation/isolation and recovery for a run.

This is what makes "tune the workflow" *matter* mechanically instead of being a cosmetic
checklist. Domain plugins extend TECHNIQUE_FAMILY / the effect vocabulary for their own
action catalogs; the aggregation mechanism itself stays generic.

Skeleton only — port the aggregation logic from GoalCert's engine/posture.py, replacing
cyber-specific lever names (phish_potency, prevent_egress, segment, c2_resilience) with
domain-neutral equivalents (e.g. escalation_potency, contain_spread, isolate,
persistence_resilience) or plugin-declared custom levers.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Posture:
    """Deterministic modifiers derived from enabled workflow tasks for one run."""
    # Response-side levers (examples — extend per domain):
    isolate: bool = False              # was `segment`
    contain_spread: bool = False       # was `prevent_egress`
    detection_boost: float = 0.0
    response_speed_boost: float = 0.0
    # Primary-driver-side levers (for adversarial / adaptive scenarios):
    evasion_potency: float = 0.0       # was `phish_potency` / `c2_resilience`
    resilience: float = 0.0
    # Free-form, plugin-declared levers not covered above:
    custom: dict[str, float] = field(default_factory=dict)


def build_posture(enabled_tasks_by_role: dict[str, list], effect_vocabulary: dict) -> Posture:
    """TODO: port from GoalCert engine/posture.py.

    Walk each role's enabled WorkflowStep.effects, sum magnitudes into the matching
    Posture field (or `custom[kind]` if not a known field), and return the aggregate.
    """
    posture = Posture()
    for role, steps in enabled_tasks_by_role.items():
        for step in steps:
            for effect in getattr(step, "effects", []):
                if hasattr(posture, effect.kind):
                    current = getattr(posture, effect.kind)
                    if isinstance(current, bool):
                        setattr(posture, effect.kind, True)
                    elif isinstance(current, (int, float)):
                        setattr(posture, effect.kind, current + effect.magnitude)
                else:
                    posture.custom[effect.kind] = posture.custom.get(effect.kind, 0.0) + effect.magnitude
    return posture
