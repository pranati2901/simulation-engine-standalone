"""Dynamic Scenario Graph — the cascade orchestrator.

A single scenario run answers "did the operator resolve this fault?". The real world
doesn't stop there: an unresolved hydraulic leak cascades into a pump failure, an
emergency landing, gate congestion, a maintenance backlog, financial loss. This module
turns one run into a **run graph** — a DAG of cause → consequence — by evaluating each
scenario's `triggers` against its *actual* run result and spawning child scenario runs.

Design guarantees (all deliberate, all load-bearing):

* Deterministic. `run_graph(scenario, env, config)` is a pure function of its inputs.
  The core engine has no RNG/wall-clock; child run ids are derived from the root id;
  spawn probabilities < 1.0 are resolved from a seeded hash. Same inputs → same graph,
  every time — which is what makes replay / fork / compare possible later.

* Emergent, not scripted. A severe branch only appears when the parent run *actually
  failed to contain* the fault (e.g. trigger condition `containment_rate < 1`). Raise
  the operator-readiness knob and the same root scenario produces a shorter, milder
  cascade. Nothing in the graph is hand-placed — every node traces to a fired trigger.

* A DAG, not a tree. Distinct causes can converge on the same consequence (spares
  shortage AND gate congestion both feed the maintenance backlog; several branches feed
  financial loss). Each scenario runs at most once per graph; convergence adds an edge
  to the existing node. Combined with a per-path visited-set, cycles are impossible.

* Bounded. `MAX_NODES` / `MAX_DEPTH` cap runaway cascades; breaches are surfaced in
  `RunGraph.truncated` rather than silently dropped.
"""
from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .conditions import eval_condition, is_preventable_condition
from .config import RunConfig
from .environment import EnvironmentSpec
from .result import RunResult
from .scenario import Scenario

MAX_DEPTH = 8      # deepest cause→consequence chain the graph will expand
MAX_NODES = 48     # hard ceiling on distinct scenario runs in one graph


# ---- graph data model ---------------------------------------------------------------

class CascadeEdge(BaseModel):
    """A fired cause → consequence link: parent run spawned child run."""
    parent_run_id: str
    child_run_id: str
    parent_scenario_id: str
    child_scenario_id: str
    trigger_kind: str
    condition: str                       # the trigger/spawn condition that fired
    delay_min: float                     # consequence lag after the cause
    probability: float
    preventable: bool                    # True if it fired because the fault wasn't contained
    reason: str                          # human-readable "why this happened"


class RunGraphNode(BaseModel):
    """One scenario run positioned in the cascade graph."""
    run_id: str
    scenario_id: str
    scenario_name: str
    domain: str
    node_kind: str                       # "fault" | "consequence"
    category: str
    impact_level: str
    depth: int                           # shortest cause-distance from the root (graph column)
    t_offset_s: int                      # start time on the master cascade clock
    parent_run_id: str | None
    result: RunResult


class RunGraph(BaseModel):
    root_run_id: str
    domain: str
    scenario_id: str
    scenario_name: str
    config: RunConfig
    nodes: list[RunGraphNode] = Field(default_factory=list)
    edges: list[CascadeEdge] = Field(default_factory=list)
    totals: dict = Field(default_factory=dict)
    truncated: bool = False


# ---- helpers ------------------------------------------------------------------------

def _context(result: RunResult) -> dict[str, float]:
    """The numeric context a trigger condition is evaluated against — the parent run's
    KPIs plus its top-line counters. Mirrors the objective-evaluation context in run.py
    so triggers and objectives speak the same language."""
    summary = result.summary or {}
    clearance = summary.get("clearance") or {}
    ctx: dict[str, float] = {k: float(v) for k, v in (result.kpis or {}).items()}
    ctx.update(
        attempts=float(summary.get("attempts", 0)),
        contained=float(summary.get("contained", 0)),
        prevented=float(summary.get("prevented", 0)),
        successes=float(len([e for e in result.events if e.type.value == "action"])),
        score=float(result.scores.get("operator", 0)),
        certified=1.0 if clearance.get("certified") else 0.0,
    )
    return ctx


def _fully_prevented(result: RunResult) -> bool:
    """True when every fault this scenario tried to inject was blocked by a safeguard.

    Careful with the counters — they do not mean what they look like. In run.py a blocked
    step `continue`s *before* `attempts += 1`, so a prevented fault is never counted as an
    attempt. A scenario whose only fault was blocked therefore reports
    `attempts == 0, prevented == 1` — not `attempts == 1, prevented == 1`.

    So "the cause never happened" is: something was blocked, and nothing got through.

    The `prevented > 0` half is what keeps consequence nodes working: they inject their
    own (unblockable) action, so they report `attempts == 1, prevented == 0` and must
    still be free to spawn their own children.
    """
    summary = result.summary or {}
    attempts = int(summary.get("attempts", 0))
    prevented = int(summary.get("prevented", 0))
    return prevented > 0 and attempts == 0


def _seeded_fraction(*parts: object) -> float:
    """A deterministic [0,1) fraction from arbitrary parts. Used to resolve spawn
    probabilities without RNG, so the graph stays replayable."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _env_for(scenario: Scenario) -> EnvironmentSpec:
    return scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)


def _reason(condition: str, context: dict[str, float], preventable: bool) -> str:
    c = (condition or "").strip()
    if not c or c.lower() in ("always", "true"):
        return "Inherent downstream consequence — occurs whenever the cause does."
    cr = context.get("containment_rate", 0.0)
    if preventable:
        return (f"Cause was not contained (containment_rate={cr:g}, condition '{c}') — "
                f"this consequence was avoidable.")
    return f"Condition '{c}' held on the cause's result."


# ---- orchestrator -------------------------------------------------------------------

def run_graph(
    scenario: Scenario,
    environment: EnvironmentSpec,
    config: RunConfig,
    *,
    root_run_id: str,
    get_scenario,
    execute,
) -> RunGraph:
    """Expand the full cascade starting from `scenario`.

    `get_scenario(id) -> Scenario | None` and `execute(scenario, env, config) -> RunResult`
    are injected (not imported) so the engine core stays free of the services/loader
    layers — same inversion-of-control the rest of engine/ uses.
    """
    nodes: list[RunGraphNode] = []
    edges: list[CascadeEdge] = []
    by_scenario: dict[str, RunGraphNode] = {}   # dedup → convergence (a scenario runs once)
    truncated = False
    counter = 0

    @dataclass
    class _Pending:
        run_id: str
        scenario: Scenario
        depth: int
        t_offset_s: int
        parent_run_id: str | None
        path: frozenset

    def _new_id() -> str:
        nonlocal counter
        rid = f"{root_run_id}-n{counter}"
        counter += 1
        return rid

    root_id = _new_id()
    queue: deque[_Pending] = deque([_Pending(
        run_id=root_id, scenario=scenario, depth=0, t_offset_s=0,
        parent_run_id=None, path=frozenset(),
    )])

    while queue:
        item = queue.popleft()
        if len(nodes) >= MAX_NODES:
            truncated = True
            break

        result = execute(item.scenario, _env_for(item.scenario), config)
        node = RunGraphNode(
            run_id=item.run_id, scenario_id=item.scenario.id, scenario_name=item.scenario.name,
            domain=item.scenario.domain, node_kind=item.scenario.node_kind,
            category=item.scenario.category, impact_level=item.scenario.impact_level,
            depth=item.depth, t_offset_s=item.t_offset_s, parent_run_id=item.parent_run_id,
            result=result,
        )
        nodes.append(node)
        by_scenario[item.scenario.id] = node

        if item.depth >= MAX_DEPTH:
            continue

        # No cause, no consequence.
        #
        # A fault can be *blocked outright* by a safeguard — an active resource covering
        # the target (resolve/resolver.py: spec.prevention). When that happens the fault
        # never occurs: the run emits "Signal Failure prevented" and nothing else.
        #
        # But the triggers below were still being evaluated against that run, and they
        # fired: `always` spawned the platform overcrowding regardless, and
        # `containment_rate < 1` held (there was nothing to contain, so the rate is 0),
        # which spawned the *preventable* service suspension too. So installing the backup
        # relay blocked the signal failure and the platform still overcrowded, a passenger
        # still collapsed, and the line still shut down — five consequences of an event
        # that did not happen.
        #
        # That is indefensible on its own terms, and it quietly destroys the engine's
        # central claim: you cannot tell an operator a consequence was "preventable" while
        # preventing the cause changes nothing. A scenario whose every fault step was
        # blocked spawns no children.
        if _fully_prevented(result):
            continue

        context = _context(result)
        for trig in item.scenario.triggers:
            if not eval_condition(trig.condition, context):
                continue
            for i, spawn in enumerate(trig.spawns):
                child_scn = get_scenario(spawn.scenario_id)
                if child_scn is None:
                    continue
                if spawn.scenario_id in item.path:        # cycle guard along this path
                    continue
                if spawn.condition and not eval_condition(spawn.condition, context):
                    continue
                if spawn.probability < 1.0 and _seeded_fraction(
                    config.seed, item.scenario.id, spawn.scenario_id, i
                ) >= spawn.probability:
                    continue

                fired_condition = spawn.condition or trig.condition
                preventable = is_preventable_condition(fired_condition)
                child_offset = item.t_offset_s + round(spawn.delay_min * 60)

                existing = by_scenario.get(spawn.scenario_id)
                if existing is not None:
                    # convergence: point a new edge at the already-materialised node
                    child_id = existing.run_id
                    existing.t_offset_s = min(existing.t_offset_s, child_offset)
                else:
                    child_id = _new_id()
                    queue.append(_Pending(
                        run_id=child_id, scenario=child_scn, depth=item.depth + 1,
                        t_offset_s=child_offset, parent_run_id=item.run_id,
                        path=item.path | {item.scenario.id},
                    ))
                    # reserve so a sibling spawn in the same wave converges instead of duplicating
                    by_scenario[spawn.scenario_id] = RunGraphNode(
                        run_id=child_id, scenario_id=child_scn.id, scenario_name=child_scn.name,
                        domain=child_scn.domain, node_kind=child_scn.node_kind,
                        category=child_scn.category, impact_level=child_scn.impact_level,
                        depth=item.depth + 1, t_offset_s=child_offset,
                        parent_run_id=item.run_id, result=result,  # placeholder, replaced when run
                    )

                edges.append(CascadeEdge(
                    parent_run_id=item.run_id, child_run_id=child_id,
                    parent_scenario_id=item.scenario.id, child_scenario_id=spawn.scenario_id,
                    trigger_kind=trig.kind, condition=fired_condition, delay_min=spawn.delay_min,
                    probability=spawn.probability, preventable=preventable,
                    reason=_reason(fired_condition, context, preventable),
                ))

    # placeholder nodes reserved-but-never-run (only possible on MAX_NODES truncation)
    materialised = {n.run_id for n in nodes}
    edges = [e for e in edges if e.child_run_id in materialised or e.child_run_id == root_id]

    return RunGraph(
        root_run_id=root_id, domain=scenario.domain, scenario_id=scenario.id,
        scenario_name=scenario.name, config=config, nodes=nodes, edges=edges,
        totals=_totals(nodes, edges), truncated=truncated,
    )


def _totals(nodes: list[RunGraphNode], edges: list[CascadeEdge]) -> dict:
    fault_nodes = [n for n in nodes if n.node_kind == "fault"]
    certified = [n for n in fault_nodes if (n.result.summary.get("clearance") or {}).get("certified")]
    preventable_children = {e.child_run_id for e in edges if e.preventable}
    by_category: dict[str, int] = {}
    for n in nodes:
        by_category[n.category] = by_category.get(n.category, 0) + 1
    return {
        "total_nodes": len(nodes),
        "downstream_consequences": max(0, len(nodes) - 1),
        "max_depth": max((n.depth for n in nodes), default=0),
        "fault_nodes": len(fault_nodes),
        "certified_faults": len(certified),
        "failed_faults": len(fault_nodes) - len(certified),
        "preventable_consequences": len(preventable_children),
        "by_category": by_category,
        "end_of_cascade_s": max((n.t_offset_s + n.result.duration_s for n in nodes), default=0),
    }
