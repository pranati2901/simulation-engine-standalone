"""Declarative technique specification.

A TechniqueSpec is data the engine interprets generically — no per-technique Python branch.
This keeps the attacker catalog uniform and serialisable (future: author techniques as JSON).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..enums import Severity

PreconditionKind = Literal["start", "foothold", "creds", "asset", "flag", "reachable", "not_flag"]
EffectKind = Literal[
    "compromise", "suspicious", "foothold", "creds", "flag",
    "degrade", "down", "disable_control", "exfiltrate",
]


class Precondition(BaseModel):
    kind: PreconditionKind
    value: str | None = None  # creds scope | asset type | flag name


class Effect(BaseModel):
    kind: EffectKind
    value: str | None = None  # creds scope | flag name | control type | asset type


class EmitTemplate(BaseModel):
    channel: str = "sys"
    severity: Severity = Severity.INFO
    text: str  # may contain "{target}" placeholder


class ScoreSpec(BaseModel):
    red_success: int = 0
    blue_detect: int = 0
    blue_contain: int = 0


class TechniqueSpec(BaseModel):
    key: str
    name: str
    mitre: str = ""
    tactic: str = ""
    description: str = ""
    severity: Severity = Severity.MEDIUM

    requires_target: bool = True
    preconditions: list[Precondition] = Field(default_factory=list)

    # control_type -> max difficulty rank it blocks at (block if difficulty.rank <= rank)
    prevention: dict[str, int] = Field(default_factory=dict)
    # control_type -> base detection latency (seconds), before difficulty/readiness scaling
    detection: dict[str, float] = Field(default_factory=dict)

    react_kind: str | None = None        # asset.react() telemetry kind for the primary target
    emits: list[EmitTemplate] = Field(default_factory=list)
    effects: list[Effect] = Field(default_factory=list)

    containable: bool = True             # detection can trigger containment of the target
    score: ScoreSpec = Field(default_factory=ScoreSpec)


_REGISTRY: dict[str, TechniqueSpec] = {}


def register(spec: TechniqueSpec) -> TechniqueSpec:
    _REGISTRY[spec.key] = spec
    return spec


def get_technique(key: str) -> TechniqueSpec:
    if key not in _REGISTRY:
        raise KeyError(f"Unknown technique: {key}")
    return _REGISTRY[key]


def all_techniques() -> list[TechniqueSpec]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def catalog() -> list[dict]:
    return [
        {
            "key": t.key, "name": t.name, "mitre": t.mitre, "tactic": t.tactic,
            "description": t.description, "severity": t.severity.value,
            "detects": sorted(t.detection.keys()), "prevents": sorted(t.prevention.keys()),
            "containable": t.containable,
            "preconditions": [{"kind": p.kind, "value": p.value} for p in t.preconditions],
            "effects": [{"kind": e.kind, "value": e.value} for e in t.effects],
        }
        for t in all_techniques()
    ]
