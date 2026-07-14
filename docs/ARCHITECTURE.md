# NextXR Simulation Hub — Scenario Engine: Architecture

## What this is

The Scenario Engine, extracted from GoalCert and made domain-agnostic. This is now a
**working v1**: 4 domains, real fault-injection → detect → respond → clearance runs,
real KPIs, real pass/fail scoring — not a stub.

This repo is meant to live at `Goalcert_Hub/simulation-engine/`, developed standalone,
then merged with the new Digital Twin and Agentic AI repos your teammates are building.

## v1 scope decision: single-operator competency check, not multi-role adversarial

GoalCert's original architecture is built for adversarial red/blue-team incident
response. Two different documents describe two different things this engine could be:
the giant architecture prompt (multi-role, cascading, multiplayer) vs. the GoalCert
User Flow doc (single frontline operator, one fault-injected competency check, scored
pass/fail, feeding a signed clearance record).

**v1 builds the User Flow doc's version.** One response role per domain (maintenance
crew, signal technician, facilities engineer, signals operator). A scenario injects a
fault; the engine deterministically evaluates whether that role responds correctly and
in time (modelled by `RunConfig.readiness`, not a live player yet); the result is a
`ClearanceRecord` — matching Step 5 of the user flow ("cleared for procedure X") and
Rule 7 ("every competency claim has an evidence chain").

Multi-role adversarial scheduling, cascading scenario graphs, and multiplayer are
**architected and documented** (see below) but **not built** in v1 — they require the
Digital Twin (for physics-real cascades) and/or a live multiplayer transport, neither
of which exist yet. Building fake versions of those now would just be new stubs to
throw away later.

## Your role in the three-service split (from `porting-scenario-engine.md`)

You are the **orchestrator**, not the physics engine and not the reasoning engine:

| Concern | Owner |
|---|---|
| Scenario spec, run lifecycle, scoring, KPIs | **You (this repo)** — real |
| Physics what-if projection | Digital Twin (`services/twin_client.py`) — stub, correctly deferred |
| NL authoring, outcome narration, coaching | Agentic AI (`services/agent_client.py`) — stub, correctly deferred |

Never re-implement physics or call an LLM directly from this repo — delegate.

## What's real vs. what's still deferred

**Real and tested** (see the smoke tests below — every number changes when you change
`readiness`/`difficulty`, nothing is hardcoded):
- `engine/run.py` — the actual deterministic scheduling loop: fault injection →
  prevention check → detection latency → decision-gate scoring (readiness vs. a
  risk-level threshold) → response → world-state mutation → KPI computation →
  objective evaluation → `ClearanceRecord`.
- `engine/resolve/resolver.py` — prevention checks against active resources.
- 4 working domain plugins (`aerospace`, `railway`, `hospital`, `defence`) each with
  real actor types, resource types, actions, one response role, and one full scenario
  with a decision gate and computable objective conditions.
- The frontend (`static/index.html`) — browse all 4 domains, see every scenario per
  domain, preview a scenario's full timeline/gates/objectives/environment *before*
  running it, tune difficulty + readiness, run it, see a real clearance banner, real
  KPIs, real event timeline, real evidence chain, and a Domain Catalog tab that lists
  every registered actor type / resource type / action / role per domain.

**Correctly still deferred** (would require a service that doesn't exist yet, or is
explicitly out of v1 scope per the decision above):
- `services/twin_client.py`, `services/agent_client.py` — real HTTP calls once those
  repos exist.
- `db/` — currently in-memory dicts in `run_manager.py` / `loader.py`. Fine for a
  single-process demo; swap in before this is a shared multi-user deployment.
- Multi-role/adversarial scheduling, multiplayer, Monte Carlo forking, replay/rollback
  — architected below, not implemented. (Dynamic Scenario Graph cascades: now DONE —
  see below.)

## Layers (mapped to folders)

| # | Layer | Folder | Status |
|---|---|---|---|
| 1 | Core Simulation Engine (deterministic run loop) | `engine/run.py` | **real** — fault-inject → detect → decide → respond → score |
| 2 | World Model | `engine/world.py`, `engine/environment.py` | real |
| 3 | State Engine | `engine/enums.py` (ActorState, Health) | real |
| 4 | Actor Engine | `engine/models/actors.py`, `engine/models/resources.py` | real |
| 5 | Workflow Engine | `engine/workflows.py`, `engine/posture.py` | data model real; not yet wired into run.py (v1 has one role, not a multi-role workflow tuning UI) |
| 6 | Scenario Engine + Cascade Graph | `engine/scenario.py`, `engine/graph.py`, `scenarios/loader.py` | **real** — triggers evaluated, cascades spawned into a DAG |
| 7 | AI Authoring | `services/agent_client.py`, `api/scenarios.py` (`/scenarios/author`) | stub — needs the Agentic AI repo |
| 8 | Live Multiplayer | `ws/runs.py` | stub — explicitly out of v1 scope |
| 9 | Reports | `reports/generator.py` | real, plugin-extensible |
| 10 | Domain Plugins | `plugins/` | real — 4 domains: aerospace, railway, hospital, defence |

## Why a plugin architecture

`engine/` never imports anything from `plugins/`. Every actor type, resource type,
action, and role is *registered into* the engine by a plugin at startup
(`plugins/registry.py::load_all()`). Adding railway or hospital means writing a new
`plugins/<domain>/plugin.py` implementing `DomainPlugin` — engine code doesn't change.

```
engine/          <- knows nothing about "hydraulic leak" or "signal failure"
  ↑ registers into
plugins/aerospace/plugin.py   -> ActorType("aircraft_hydraulic_system"), ...
plugins/railway/plugin.py     -> ActorType("signal_block"), ...
plugins/hospital/plugin.py    -> ActorType("ward_hvac"), ...
```

### Worked example: adding a Railway plugin

```python
# plugins/railway/plugin.py
class RailwayPlugin(DomainPlugin):
    key = "railway"
    name = "Railway (SMRT-style)"

    def register(self):
        register_actor_type(ActorType(key="signal_block", ..., domain=self.key))
        register_actor_type(ActorType(key="train_unit", ..., domain=self.key))
        register_resource_type(ResourceType(key="backup_signal_relay", domain=self.key))
        register_action(ActionSpec(key="signal_failure", category="spread", domain=self.key,
                                    prevention={"backup_signal_relay": 2}))
        for role in self.roles():
            register_role(role)
```
Then one line in `plugins/registry.py::load_all()`: `register(RailwayPlugin())`.
A hospital plugin follows the identical shape with `ward_hvac`, `backup_generator`, etc.

## What's a real port vs. a stub in this scaffold

**Ported and working** (imports, runs, and is exercised by the smoke test):
`enums`, `world`, `environment`, `events`, `scenario` (+cascade fields), `config`,
`kpis`, `result`, `workflows`, plugin registry + aerospace reference plugin, scenario
loader + example scenario, API routers, `main.py`.

**Structural skeletons with TODOs, not yet ported** (highest-value next work):
- `engine/run.py` — the actual heapq scheduling loop from GoalCert's 754-line `run.py`.
  This is the single most important thing to port next; everything else depends on it.
- `engine/posture.py` / `engine/resolve/resolver.py` — the effect-aggregation and
  prevention-check logic (patterns are copied, cyber-specific levers are placeholder).
- `services/twin_client.py`, `services/agent_client.py` — real HTTP calls once the
  other two repos exist.
- `db/` — currently in-memory dicts in `run_manager.py` / `loader.py`; the porting
  guide explicitly warns against shipping that as final.

## Dynamic Scenario Graph (Phase 2 — IMPLEMENTED)

`Scenario.triggers`, `Trigger`, `CascadeSpawn` are now **executed** by
`engine/graph.py`. A run is no longer a single scenario end-to-end — it is a **run
graph**: a DAG of cause → consequence.

How it works (`engine/graph.py::run_graph`):
1. Run the root scenario through the existing pure `run.py` loop.
2. Build a numeric context from its result (KPIs + counters — `containment_rate`,
   `certified`, `score`, ...) and evaluate each `Trigger.condition` against it
   (`engine/conditions.py`, the same evaluator `run.py` uses for objectives).
3. Every fired `CascadeSpawn` spawns a child scenario run (recursively), with a
   `t_offset_s` = parent start + `delay_min`. Children reuse the same `RunConfig`, so
   one operator-readiness value shapes the whole cascade.
4. Distinct causes converge on the same consequence (dedup by scenario id → real DAG,
   not a tree). A per-path visited-set makes cycles impossible; `MAX_NODES`/`MAX_DEPTH`
   bound runaway cascades (`RunGraph.truncated` flags a breach).

**Emergent, not scripted.** A severe branch (`condition="containment_rate < 1"`) only
fires when the operator actually *failed to contain* the fault — raise readiness past
the decision-gate threshold and the same root produces a shorter, milder graph. Every
node traces to a fired trigger; nothing is hand-placed. `CascadeEdge.preventable` marks
edges that fired because of a containment failure, which drives the "which consequences
were avoidable?" analysis in the UI.

**Still deterministic.** No RNG/wall-clock; child run ids derive from the root id;
spawn `probability < 1.0` resolves from a seeded hash of `(seed, parent, child)`. Same
`(scenario, env, config, root_run_id)` → byte-identical graph — which is exactly what
makes replay / fork / compare (snapshot `World` at T, branch into N futures) tractable
next.

Reference cascade: `scenarios/definitions/aerospace/cascade.py` (10-node branching DAG,
built with the `scenarios/factory.py` `fault_node`/`consequence_node` helpers). API:
`POST /runs/graph` → `RunGraph`; the frontend renders it as the Scenario Evolution
Graph. Adding a cascade to another domain = author child scenarios + add `triggers` to
the root; the engine is untouched.

## Multi-domain sprint plan alignment

Your 62-task sprint plan across six verticals maps onto this scaffold as: **one
`plugins/<domain>/` package + matching `scenarios/definitions/<domain>/` per
vertical**, all built against the same `engine/` core. The Multi-Domain Scenario
Library feature you've already shipped is effectively `plugins/registry.py` +
`scenarios/loader.py` here — reconcile naming with whatever you already have in your
sprint branch before merging.

## Integration point with the Hub

When Digital Twin and Agentic AI repos land in `Goalcert_Hub`, the seams are already
drawn: `services/twin_client.py` and `services/agent_client.py` are the only two files
that need real endpoints filled in. The user-facing flow (open webpage → Digital Twin →
agents collaborate → hand off to Scenario Engine → fix the problem) is: Digital Twin
detects/represents the fault → Agentic AI decides a scenario is worth running → calls
this engine's `/scenarios/author` or `/runs` → this engine calls back into the Twin for
physics and into Agentic AI for narration → results stream back to the Hub UI.
