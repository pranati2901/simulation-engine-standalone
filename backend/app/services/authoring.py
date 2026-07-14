"""Natural-language scenario authoring.

"A signal fails during peak hour and the platform floods" -> a runnable Scenario, with
its steps, decision gate, objectives and cascade triggers, registered and immediately
executable by the deterministic engine.

WHAT THE MODEL DOES AND DOES NOT DO
-----------------------------------
The model *writes the spec*. It does not simulate anything. Once the Scenario is
registered, engine/graph.py computes the cascade exactly as it does for a hand-written
scenario — same deterministic run loop, same triggers, same KPIs. Nothing about the
outcome is generated prose. This distinction is the whole point: an LLM that invented
the consequences would just be telling you a story.

THE TWO GUARDS
--------------
1. SHAPE. The model is given the Scenario JSON Schema and answers under
   `output_config.format`, so it cannot return malformed or partial JSON.

2. VOCABULARY. This is the one that actually bites. A Scenario's `steps[].action` must
   name an action registered by the domain plugin, and `target.value` an actor type it
   knows. The model will cheerfully invent `action: "signal_meltdown"` on a
   `sky_train` — which parses fine, registers fine, and then does *nothing* at run time,
   because the resolver has no such action. So every authored id is checked against the
   live catalog, and anything unknown is either (a) declared up-front as a new
   ActionSpec, which we register, or (b) rejected with the valid options fed back for
   one repair attempt.

Allowing (a) is deliberate: without it, authoring on Railway could only ever recombine
the five actions the plugin already ships, and "author a flooding scenario" would be
impossible. ActionSpec is declarative (category / requires_target / prevention /
telemetry) and the resolver consumes it generically, so a newly registered action is a
first-class fault the moment it exists.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from ..core.settings import settings
from ..engine.catalog.spec import ActionSpec, actions_for_domain, register_action
from ..engine.models.actors import actor_types_for_domain
from ..engine.models.resources import resource_types_for_domain
from ..engine.scenario import Scenario
from ..plugins.registry import get_plugin
from ..scenarios.loader import get_scenario, register_scenario, scenarios_for_domain


class AuthoringError(Exception):
    """Raised when authoring cannot produce a runnable scenario. The message is meant
    to be shown to the operator, so say what went wrong and what to do about it."""


class AuthoredBundle(BaseModel):
    """What the model must return: optionally some new actions, and one scenario that
    uses them. Both are validated before anything is registered."""
    new_actions: list[ActionSpec] = Field(
        default_factory=list,
        description="Actions that do not exist in the catalog yet and are needed by this "
                    "scenario. Omit if the scenario only uses existing actions.",
    )
    scenario: Scenario


SYSTEM = """You author scenarios for a deterministic operational simulation engine.

You are writing a SPEC, not a story. You do not decide what happens — the engine does.
Your job is to express the operator's description as a Scenario the engine can execute:
the fault that is injected, the decision the operator must get right, what "success"
means, and what this fault cascades into if it is NOT contained.

HARD RULES
- `domain` must be exactly the domain given below.
- `id` must be "<domain>.<snake_case_name>_v1" and must not collide with an existing id.
- Every `steps[].action` must be either an action key listed in EXISTING ACTIONS, or an
  action you declare in `new_actions`. Never use an action key you have not either found
  in the list or declared.
- Every `steps[].target.value` (when `by` is "type") must be an actor type listed in
  EXISTING ACTOR TYPES. You may not invent actor types.
- Every `steps[].phase` must appear in `phases`.
- Every `decision_gates[].trigger` must be the id of one of your `steps`.
- You MUST supply `recommended_environment` containing an actor for every actor type your
  steps target, plus any resources that could prevent the fault. A fault injected into a
  world with no actors does nothing at all — the run completes and simulates nothing.
- `triggers[].spawns[].scenario_id` must reference an EXISTING scenario id from the list
  below. You are authoring ONE scenario; you cannot invent its downstream consequences.

THE CASCADE IS THE POINT
`triggers` is what makes this a simulation rather than a checklist. Use two kinds:
- condition "always"  -> an inherent consequence: it happens whether or not the operator
  performs well.
- condition "containment_rate < 1"  -> a PREVENTABLE consequence: it only happens because
  the operator failed to contain the fault. This is the most valuable thing you can
  express, because it is what the engine will later tell the operator they could have
  avoided. A good scenario has at least one.

`objectives[].condition` is evaluated against the run's KPIs — e.g. "containment_rate == 1".

Set `decision_gates[].risk_level` honestly (low|medium|high|extreme): it sets the operator
readiness threshold needed to pass the gate. High-risk faults should be hard to contain."""


def _catalog_brief(domain: str) -> str:
    actions = actions_for_domain(domain)
    actors = actor_types_for_domain(domain)
    resources = resource_types_for_domain(domain)
    scenarios = scenarios_for_domain(domain)
    roles = get_plugin(domain).roles() if get_plugin(domain) else []

    def line(items, fmt):
        return "\n".join("  - " + fmt(i) for i in items) or "  (none)"

    return f"""
DOMAIN: {domain}

EXISTING ACTIONS (use these keys verbatim in steps[].action):
{line(actions, lambda a: f"{a.key} — {a.name} (category={a.category}, requires_target={a.requires_target})")}

EXISTING ACTOR TYPES (use these keys verbatim in steps[].target.value):
{line(actors, lambda a: f"{a.key} — {a.name}")}

EXISTING RESOURCE TYPES (may be named in a new action's `prevention`):
{line(resources, lambda r: f"{r.key} — {r.name}")}

ROLES (use for objectives[].role and decision-gate ownership):
{line(roles, lambda r: f"{r.key if hasattr(r, 'key') else r.id} — {getattr(r, 'name', '')}")}

EXISTING SCENARIOS (the ONLY valid triggers[].spawns[].scenario_id values):
{line(scenarios, lambda s: f"{s.id} — {s.name} ({s.node_kind})")}
"""


def _validate(bundle: AuthoredBundle, domain: str) -> list[str]:
    """Return a list of human-readable problems. Empty list = runnable."""
    problems: list[str] = []
    scn = bundle.scenario

    if scn.domain != domain:
        problems.append(f"scenario.domain is '{scn.domain}', must be '{domain}'.")
    if get_scenario(scn.id) is not None:
        problems.append(f"scenario id '{scn.id}' already exists — choose a different id.")
    if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", scn.id or ""):
        problems.append(f"scenario id '{scn.id}' must look like '{domain}.some_name_v1'.")

    known_actions = {a.key for a in actions_for_domain(domain)} | {a.key for a in bundle.new_actions}
    known_actors = {a.key for a in actor_types_for_domain(domain)}
    known_scenarios = {s.id for s in scenarios_for_domain(domain)}

    if not scn.steps:
        problems.append("scenario has no steps — it would inject nothing.")

    for step in scn.steps:
        if step.action not in known_actions:
            problems.append(
                f"step '{step.id}' uses unknown action '{step.action}'. Either use one of "
                f"[{', '.join(sorted(known_actions))}] or declare it in new_actions."
            )
        if step.phase not in scn.phases:
            problems.append(f"step '{step.id}' has phase '{step.phase}' which is not in phases {scn.phases}.")
        if step.target and step.target.by == "type" and step.target.value not in known_actors:
            problems.append(
                f"step '{step.id}' targets unknown actor type '{step.target.value}'. "
                f"Valid: [{', '.join(sorted(known_actors))}]. Actor types cannot be invented."
            )

    # A scenario needs a WORLD to inject into.
    #
    # This is the silent killer. A scenario with a step targeting `signal_block` but no
    # `recommended_environment` parses, registers, and runs — and injects nothing, because
    # the world has no actors to select. You get a clean run with zero action events,
    # containment_rate 0, and a cascade that looks plausible but was never caused by
    # anything. Fail loudly instead.
    env_actor_types = {a.type for a in (scn.recommended_environment.actors if scn.recommended_environment else [])}
    for step in scn.steps:
        if step.target and step.target.by == "type" and step.target.value not in env_actor_types:
            problems.append(
                f"step '{step.id}' targets actor type '{step.target.value}', but "
                f"recommended_environment contains no actor of that type "
                f"({sorted(env_actor_types) or 'it has no actors at all'}). The fault would "
                f"inject into an empty world and do nothing. Add the actor to "
                f"recommended_environment.actors."
            )

    step_ids = {s.id for s in scn.steps}
    for gate in scn.decision_gates:
        if gate.trigger not in step_ids:
            problems.append(f"decision gate '{gate.id}' triggers on '{gate.trigger}', which is not a step id.")

    for trig in scn.triggers:
        for spawn in trig.spawns:
            if spawn.scenario_id not in known_scenarios:
                problems.append(
                    f"trigger spawns unknown scenario '{spawn.scenario_id}'. "
                    f"Valid: [{', '.join(sorted(known_scenarios))}]."
                )

    for action in bundle.new_actions:
        if action.domain != domain:
            problems.append(f"new action '{action.key}' has domain '{action.domain}', must be '{domain}'.")
        for res in action.prevention:
            if res not in {r.key for r in resource_types_for_domain(domain)}:
                problems.append(f"new action '{action.key}' names unknown resource type '{res}' in prevention.")

    return problems


async def _ask_model(domain: str, prompt: str, repair: str | None = None) -> AuthoredBundle:
    """One call to Claude. Structured output means we get valid JSON or an SDK error —
    never a half-parsed blob."""
    from anthropic import AsyncAnthropic   # imported lazily so the engine runs without it

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    user = f"{_catalog_brief(domain)}\n\nOPERATOR'S DESCRIPTION:\n{prompt}"
    if repair:
        user += (
            "\n\nYOUR PREVIOUS ATTEMPT WAS NOT RUNNABLE. Fix exactly these problems and "
            "return the whole bundle again:\n" + repair
        )

    resp = await client.messages.create(
        model=settings.authoring_model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": AuthoredBundle.model_json_schema()},
        },
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )

    if resp.stop_reason == "refusal":
        raise AuthoringError("The authoring model declined this request.")

    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return AuthoredBundle.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as e:
        raise AuthoringError(f"The model returned a scenario that does not fit the engine's schema: {e}")


async def author_scenario(domain: str, prompt: str) -> Scenario:
    """Author, validate, register. Returns the runnable Scenario.

    One repair round: if the first attempt names an action or actor the engine doesn't
    have, we hand the model the exact problems and the valid vocabulary and let it fix
    them. If it still fails, we refuse rather than register something that would inject
    nothing at run time.
    """
    if not settings.anthropic_api_key:
        raise AuthoringError(
            "Scenario authoring needs an Anthropic API key. Set ANTHROPIC_API_KEY in the "
            "engine's environment (backend/.env) and restart it."
        )
    if get_plugin(domain) is None:
        raise AuthoringError(f"Unknown domain '{domain}'.")
    if not (prompt or "").strip():
        raise AuthoringError("Describe the scenario you want in a sentence or two.")

    bundle = await _ask_model(domain, prompt)
    problems = _validate(bundle, domain)

    if problems:
        bundle = await _ask_model(domain, prompt, repair="\n".join(f"- {p}" for p in problems))
        problems = _validate(bundle, domain)

    if problems:
        raise AuthoringError(
            "Could not produce a runnable scenario. The model kept using things this "
            "domain doesn't have:\n" + "\n".join(f"• {p}" for p in problems)
        )

    # Carry the new vocabulary ON the scenario, then register.
    #
    # register_action() writes to an in-memory dict; register_scenario() writes to the
    # database. Registering the action *only* in memory means the scenario outlives its
    # own vocabulary: it comes back after a restart and dies with `KeyError: Unknown
    # action`. Attaching them to `custom_actions` persists them in the same row, and
    # loader._materialise() re-registers them on every load. Register in memory too, so
    # the scenario is runnable in THIS process without waiting for a reload.
    scenario = bundle.scenario.model_copy(update={"custom_actions": bundle.new_actions})
    for action in bundle.new_actions:
        register_action(action)
    register_scenario(scenario)

    return scenario
