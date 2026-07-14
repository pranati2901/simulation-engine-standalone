"""Run configuration — the operator-tunable knobs that deterministically shape outcomes."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import Difficulty, Side


class WorkflowConfig(BaseModel):
    """Operator customization of each role's workflow.

    `enabled[role]` = explicit list of enabled task ids. If a role is absent, that
    role's default-enabled tasks are used.
    """
    enabled: dict[str, list[str]] = Field(default_factory=dict)

    def enabled_set(self, role: str) -> set[str] | None:
        return set(self.enabled[role]) if role in self.enabled else None


class RunConfig(BaseModel):
    """Operator configuration for a single simulation run.

    Everything here feeds the deterministic resolvers. Identical config + environment +
    scenario should always produce an identical timeline (pure core, no wall-clock/RNG),
    which is what makes replay / rollback / fork (Phase 2) possible later.
    """
    difficulty: Difficulty = Difficulty.MEDIUM
    readiness: int = Field(default=60, ge=0, le=100)   # response-team readiness 0..100
    duration_min: int = Field(default=120, ge=5, le=480)
    domain: str = "generic"                             # which plugin drives this run

    focus_role: Side = Side.RESPONSE
    role_drivers: dict[str, str] = Field(default_factory=dict)  # role -> "scripted" | "ai"
    phase_range: tuple[int, int] | None = None
    workflow_config: WorkflowConfig = Field(default_factory=WorkflowConfig)

    seed: int = 0  # reserved for a future seeded-stochastic resolver

    @property
    def readiness_factor(self) -> float:
        return 1.0 - (self.readiness / 200.0)

    @property
    def readiness_norm(self) -> float:
        return self.readiness / 100.0

    @property
    def control_efficacy(self) -> float:
        return round(0.55 + 0.45 * self.readiness_norm, 3)

    def latency(self, base_seconds: float) -> int:
        scaled = base_seconds * self.difficulty.factor * self.readiness_factor
        return max(1, round(scaled))

    def driver_for(self, role: str) -> str:
        return self.role_drivers.get(role, "scripted")
