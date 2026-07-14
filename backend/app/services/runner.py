"""Executes a single run of the deterministic engine core.

Kept separate from run_manager so the streaming (ws/runs.py) and future async/queued
execution can wrap this without touching lifecycle/persistence logic.
"""
from __future__ import annotations

from ..engine import run as engine_run
from ..engine.config import RunConfig
from ..engine.environment import EnvironmentSpec
from ..engine.result import RunResult
from ..engine.scenario import Scenario


def execute(scenario: Scenario, environment: EnvironmentSpec, config: RunConfig) -> RunResult:
    """Run the scenario through the engine core. Synchronous today (the core is pure
    and fast); swap to a background task + ws event stream once runs get long enough
    to need progress streaming (see ws/runs.py).
    """
    return engine_run.run(scenario, environment, config)
