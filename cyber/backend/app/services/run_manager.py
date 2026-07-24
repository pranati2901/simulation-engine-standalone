"""In-memory streaming sessions for live run monitoring.

A run is fully precomputed and persisted; a RunSession replays its timeline at a controllable
pace (pause/resume/speed/seek). A manual inject re-runs the engine with an extra technique
spliced in at the current sim-time and swaps in the recomputed tail (deterministic).
"""
from __future__ import annotations

from app.engine.config import RunConfig
from app.engine.environment import EnvironmentSpec
from app.engine.scenario import PlaybookStep, Scenario, TargetSelector
from app.core.settings import settings
from app.db.models import Run

from .runner import compute


def _sorted_events(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: (e["t"], e["seq"]))


class RunSession:
    def __init__(self, run: Run, scenario: Scenario, env: EnvironmentSpec, config: RunConfig):
        self.run_id = run.id
        self.scenario = scenario
        self.env = env
        self.config = config
        self.duration_s = run.duration_s
        self.events = _sorted_events(run.events)
        self.scores = dict(run.scores)
        self.kpis = dict(run.kpis)
        self.summary = dict(run.summary)
        self.objectives = dict(run.objectives)
        self.final_assets = list(run.final_assets)
        self.environment = list(run.environment)
        self.role_tasks = dict(run.role_tasks)
        self.workflows = list(run.workflows)
        self.injected: list[PlaybookStep] = []

        self.sim_t: float = 0.0
        self.speed: float = settings.default_stream_speed
        self.paused: bool = False
        self.ptr: int = 0
        self.finished: bool = False

    # ---- pacing --------------------------------------------------------------
    def advance(self, dt: float) -> None:
        if not self.paused and self.sim_t < self.duration_s:
            self.sim_t = min(self.duration_s, self.sim_t + self.speed * dt)

    def due_events(self) -> list[dict]:
        out: list[dict] = []
        while self.ptr < len(self.events) and self.events[self.ptr]["t"] <= self.sim_t:
            out.append(self.events[self.ptr])
            self.ptr += 1
        return out

    def at_end(self) -> bool:
        return self.sim_t >= self.duration_s and self.ptr >= len(self.events)

    # ---- controls ------------------------------------------------------------
    def set_speed(self, speed: float) -> None:
        self.speed = max(1.0, min(600.0, float(speed)))

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def seek(self, t: float) -> None:
        self.sim_t = max(0.0, min(float(t), float(self.duration_s)))
        self.ptr = sum(1 for e in self.events if e["t"] <= self.sim_t)

    def inject(self, technique: str, target_by: str | None = None,
               target_value: str | None = None, label: str | None = None) -> None:
        """Splice a technique at current sim-time and recompute the tail deterministically."""
        at_min = (self.sim_t + 1) / 60.0
        target = (TargetSelector(by=target_by, value=target_value)  # type: ignore[arg-type]
                  if target_by and target_value else None)
        step = PlaybookStep(
            id=f"inject_{len(self.injected) + 1}", technique=technique,
            phase=self.scenario.phases[-1] if self.scenario.phases else "Inject",
            at_min=at_min, target=target, is_inject=True,
            label=label or f"Operator inject: {technique}",
        )
        self.injected.append(step)
        result = compute(self.scenario, self.env, self.config, self.injected)
        self.events = _sorted_events([e.model_dump(mode="json") for e in result.events])
        self.scores = result.scores
        self.kpis = result.kpis
        self.summary = result.summary
        self.objectives = result.model_dump(mode="json")["objectives"]
        self.final_assets = result.final_assets
        self.role_tasks = result.role_tasks
        # everything at/under current sim-time is considered already streamed
        self.ptr = sum(1 for e in self.events if e["t"] <= self.sim_t)

    def complete_payload(self) -> dict:
        return {
            "scores": self.scores, "kpis": self.kpis, "summary": self.summary,
            "objectives": self.objectives, "final_assets": self.final_assets,
            "role_tasks": self.role_tasks,
        }


_SESSIONS: dict[str, RunSession] = {}


def get_session(run_id: str) -> RunSession | None:
    return _SESSIONS.get(run_id)


def open_session(run: Run, scenario: Scenario, env: EnvironmentSpec, config: RunConfig) -> RunSession:
    session = RunSession(run, scenario, env, config)
    _SESSIONS[run.id] = session
    return session


def close_session(run_id: str) -> None:
    _SESSIONS.pop(run_id, None)
