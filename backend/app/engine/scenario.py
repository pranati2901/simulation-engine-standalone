"""Scenario = a driving storyline (external event / equipment failure / human action /
AI decision) + the environment that makes the run meaningful (intent, not outcome).

A scenario expresses *what happens* and *what world state makes the run realistic*.
Outcomes emerge from the engine resolving the scenario's steps against the world.

Generic replacement for GoalCert's engine/scenario.py (attacker playbook -> generic
scenario steps). Field names are domain-neutral: a "step" here can be an attacker
technique, a heatwave intensifying, a signal failure, or an AI-agent recommendation.

--------------------------------------------------------------------------------------
DYNAMIC SCENARIO GRAPH (now implemented — engine/graph.py):
Scenario.triggers / Trigger / CascadeSpawn are evaluated by the cascade orchestrator
after each scenario run: a fired trigger spawns child scenario runs, turning a single
run into a run **graph** (a DAG of cause → consequence). A run still executes one
scenario end-to-end; graph.py chains those runs. See docs/ARCHITECTURE.md#dynamic-scenario-graph.
--------------------------------------------------------------------------------------
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .environment import EnvironmentSpec


class TargetSelector(BaseModel):
    by: Literal["role", "type"] = "role"
    value: str
    pick: Literal["first", "all"] = "first"


class ExpectedSignal(BaseModel):
    """Expected detection/monitoring signal for a step (drives training/grading)."""
    indicator_type: str = "behavioural"
    signal: str = ""
    source: str = ""                     # which resource/monitor should surface this
    expected_priority: str = "P2"


class ScenarioStep(BaseModel):
    id: str
    action: str                          # action key from the catalog (engine/catalog)
    phase: str                           # phase name (must be in scenario.phases)
    at_min: float = 0.0                  # nominal minute offset within the scenario timeline
    target: TargetSelector | None = None
    is_inject: bool = False
    label: str | None = None
    expected_signals: list[ExpectedSignal] = Field(default_factory=list)
    fallback_action: str | None = None   # alternate step if this one is blocked
    props: dict = Field(default_factory=dict)


class DecisionGate(BaseModel):
    """An IF/THEN decision point the engine enforces and scores against.

    v1 note: `trigger` holds the id of the ScenarioStep this gate is scored against
    (i.e. "when step s1's fault occurs, was the correct response taken in time").
    A richer world-state condition language is reserved for later — see
    resolve/preconditions.py for the same pattern used elsewhere.
    """
    id: str
    name: str
    trigger: str                         # ScenarioStep.id this gate is scored against (v1)
    correct_action: str                  # the response the scenario expects
    risk_level: str = "medium"           # low | medium | high | extreme — sets the pass threshold
    description: str = ""
    approval_required_from: str = ""
    consequence_of_delay: str = ""
    delay_s: int = 180


# ---- Dynamic Scenario Graph (executed by engine/graph.py) --------------------------

class CascadeSpawn(BaseModel):
    """Declares that this scenario, under some condition, spawns another scenario.

    `condition` (optional) is a single comparison against the *parent run's* result
    context (KPIs + counters), e.g. "containment_rate < 1" or "score < 100" — see
    engine/conditions.py. `probability` < 1.0 stays deterministic: the graph resolves
    it from a seeded hash of (config.seed, parent id, child id) so identical inputs
    always produce the identical graph (which is what makes replay/fork possible).
    """
    scenario_id: str
    delay_min: float = 0.0
    probability: float = 1.0             # 1.0 = deterministic; <1.0 = seeded-deterministic branch
    condition: str | None = None         # e.g. "containment_rate < 1"


class Trigger(BaseModel):
    """A condition that starts, branches, or spawns a scenario. Evaluated by graph.py
    after the owning scenario's run completes: if `condition` holds against the run
    context, every CascadeSpawn in `spawns` is (probabilistically) spawned."""
    kind: Literal[
        "time", "state", "sensor", "probability", "kpi_threshold",
        "human_decision", "ai_decision", "scenario_complete", "resource_shortage",
        "workflow_complete", "external_event", "manual_inject",
    ]
    condition: str
    spawns: list[CascadeSpawn] = Field(default_factory=list)


class ScenarioObjective(BaseModel):
    text: str
    role: str = "response"
    condition: str = ""   # e.g. "containment_rate == 1", evaluated against run KPIs/counters (see engine/run.py)


class Scenario(BaseModel):
    id: str
    name: str
    domain: str = "generic"              # which plugin owns this scenario
    description: str = ""
    phases: list[str] = Field(default_factory=list)
    steps: list[ScenarioStep] = Field(default_factory=list)
    decision_gates: list[DecisionGate] = Field(default_factory=list)
    objectives: list[ScenarioObjective] = Field(default_factory=list)
    recommended_environment: EnvironmentSpec | None = None
    tags: list[str] = Field(default_factory=list)

    # Dynamic Scenario Graph metadata (used by the cascade graph view — engine/graph.py):
    #   node_kind    — "fault": a competency-check node (scored, certified/failed);
    #                  "consequence": a downstream impact node (logged, not certified).
    #   category     — causal class for graph colouring/legend: equipment | operational |
    #                  human | safety | supply | financial | environment | cyber | ...
    #   impact_level — low | medium | high | critical (drives node size/severity).
    node_kind: Literal["fault", "consequence"] = "fault"
    category: str = "operational"
    impact_level: Literal["low", "medium", "high", "critical"] = "medium"

    # Dynamic Scenario Graph wiring:
    triggers: list[Trigger] = Field(default_factory=list)
    parent_scenario_id: str | None = None  # set on scenarios spawned mid-run


REGULATORY_CATALOG: dict[str, dict] = {
    # Domain plugins populate/override this with their own regulatory clocks
    # (e.g. aviation AD reporting windows, healthcare breach notification windows).
}
