"""Run configuration — the operator-tunable knobs that deterministically shape outcomes."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import Difficulty, Side


class WorkflowConfig(BaseModel):
    """Operator customization of each team's workflow.

    `enabled[actor]` = explicit list of enabled task ids. If an actor is absent, that team's
    default-enabled tasks are used. This is how the operator adds/removes tasks per team.
    """
    enabled: dict[str, list[str]] = Field(default_factory=dict)

    def enabled_set(self, actor: str) -> set[str] | None:
        return set(self.enabled[actor]) if actor in self.enabled else None


class RunConfig(BaseModel):
    """Operator configuration for a single simulation run.

    Everything here feeds the deterministic resolvers. Identical config + environment +
    scenario always produces an identical timeline.
    """

    difficulty: Difficulty = Difficulty.MEDIUM
    # Team readiness 0..100 — higher means faster, more reliable detection & response.
    readiness: int = Field(default=60, ge=0, le=100)
    # Total simulated duration in minutes (used for pacing/phase spacing, not outcomes).
    duration_min: int = Field(default=120, ge=5, le=480)
    industry: str = "generic"

    # ---- v2: role lens & drivers --------------------------------------------
    # The team the operator observes/scores by default (every team still acts).
    focus_role: Side = Side.BLUE
    # Which roles are scripted vs (future) AI-driven. POC: all "scripted".
    role_drivers: dict[str, str] = Field(default_factory=dict)
    # Optional [start_phase, end_phase] (1-based inclusive) to run a single-phase drill.
    phase_range: tuple[int, int] | None = None
    # Per-team workflow customization (which tasks are enabled / added / removed).
    workflow_config: WorkflowConfig = Field(default_factory=WorkflowConfig)

    # Reserved for a future seeded-stochastic resolver. Unused in the deterministic core.
    seed: int = 0

    @property
    def readiness_factor(self) -> float:
        """Latency multiplier from readiness: readiness 0 -> 1.0x, 100 -> 0.5x (faster)."""
        return 1.0 - (self.readiness / 200.0)

    @property
    def readiness_norm(self) -> float:
        """Readiness normalised to 0..1."""
        return self.readiness / 100.0

    # ---- readiness -> concrete model knobs (roadmap Part 9.2) ----------------
    @property
    def user_susceptibility(self) -> float:
        """Phishing-click likelihood 0..1; high readiness lowers it."""
        return round(0.85 - 0.6 * self.readiness_norm, 3)

    @property
    def control_efficacy(self) -> float:
        """Multiplier 0..1 on control detect/prevent reliability."""
        return round(0.55 + 0.45 * self.readiness_norm, 3)

    def latency(self, base_seconds: float) -> int:
        """Apply difficulty + readiness to a base latency, in whole sim-seconds (>=1)."""
        scaled = base_seconds * self.difficulty.factor * self.readiness_factor
        return max(1, round(scaled))

    def driver_for(self, role: str) -> str:
        return self.role_drivers.get(role, "scripted")
