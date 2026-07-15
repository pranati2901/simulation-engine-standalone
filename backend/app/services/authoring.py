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
import uuid

from pydantic import BaseModel, Field, ValidationError

from ..core.settings import settings
from ..engine.catalog.spec import ActionSpec, actions_for_domain, register_action
from ..engine.environment import ActorSpec, EnvironmentSpec
from ..engine.models.actors import actor_types_for_domain
from ..engine.models.resources import resource_types_for_domain
from ..engine.scenario import (
    CascadeSpawn,
    DecisionGate,
    Scenario,
    ScenarioObjective,
    ScenarioStep,
    TargetSelector,
    Trigger,
)
from ..plugins.registry import get_plugin
from ..scenarios.loader import get_scenario, register_scenario, scenarios_for_domain
from .agent_client import AgentUnavailable, author_scenario_from_nl


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
`triggers` is what makes this a simulation rather than a checklist. Each trigger is an
object of the exact shape:
    {"kind": "state", "condition": "<expr>", "spawns": [{"scenario_id": "<existing id>"}]}
ALWAYS set "kind" to the literal "state". The firing rule goes in "condition" — NEVER put
"always" or a comparison in "kind" (that field only accepts the enum in the schema). Use:
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
{line(roles, lambda r: f"{getattr(r, 'role', None) or getattr(r, 'key', None) or '?'} — {getattr(r, 'name', '')}")}

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


async def _call_once(client, domain: str, prompt: str, repair: str | None) -> str:
    """One model call. Returns the raw JSON text of the AuthoredBundle (schema handed to
    the model as text — the strict json_schema grammar compiles too large for the full
    Scenario shape)."""
    user = f"{_catalog_brief(domain)}\n\nOPERATOR'S DESCRIPTION:\n{prompt}"
    if repair:
        user += (
            "\n\nYOUR PREVIOUS ATTEMPT WAS NOT ACCEPTED. Fix exactly these problems and "
            "return the whole bundle again:\n" + repair
        )
    user += (
        "\n\nReturn ONLY a single JSON object that validates against this JSON Schema — "
        "no prose, no markdown fences:\n" + json.dumps(AuthoredBundle.model_json_schema())
    )
    resp = await client.messages.create(
        model=settings.authoring_model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise AuthoringError("The authoring model declined this request.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    # The model may wrap the JSON in prose or ```json fences — pull out the object.
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    return fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]


async def _ask_model(domain: str, prompt: str, repair: str | None = None) -> AuthoredBundle:
    """One authored bundle, with one automatic schema-repair round: if the model's JSON
    doesn't fit the engine's schema (wrong enum like a trigger `kind`, a missing field, …),
    we hand the exact validation error back and let it fix the whole object once."""
    from anthropic import AsyncAnthropic   # imported lazily so the engine runs without it

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    payload = await _call_once(client, domain, prompt, repair)
    try:
        return AuthoredBundle.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValidationError) as e:
        fix = ("Your JSON did not fit the engine schema. Fix EXACTLY this and return the "
               f"whole object again:\n{e}")
        payload = await _call_once(client, domain, prompt, f"{repair}\n{fix}" if repair else fix)
        try:
            return AuthoredBundle.model_validate(json.loads(payload))
        except (json.JSONDecodeError, ValidationError) as e2:
            raise AuthoringError(f"The model returned a scenario that does not fit the engine's schema: {e2}")


_RISKS = {"low", "medium", "high", "extreme"}
_IMPACTS = {"low", "medium", "high", "critical"}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:40] or uuid.uuid4().hex[:8]


async def _author_via_agentic(domain: str, prompt: str) -> Scenario:
    """Fallback authoring path when no Anthropic key is set on the engine.

    Delegates to the AUTOMIND Agentic AI platform (which authors with whatever LLM key
    IT holds — OpenAI or Anthropic — or its deterministic template stub). AUTOMIND
    returns a FLAT spec (fault_action, gate_*, cascades, custom_actions); we validate
    every reference against the live catalog here and assemble the Scenario ourselves,
    exactly as the Anthropic path does — so the engine stays the source of truth for
    what is runnable, regardless of which platform wrote the spec.
    """
    actions = actions_for_domain(domain)
    actor_types = actor_types_for_domain(domain)
    roles = [r.name for r in get_plugin(domain).roles()]
    existing = scenarios_for_domain(domain)

    try:
        resp = await author_scenario_from_nl(
            domain, prompt.strip(),
            context={
                "actions": [{"key": a.key, "name": a.name, "category": a.category}
                            for a in actions],
                "roles": roles,
                "actor_types": [{"key": t.key} for t in actor_types],
                "existing_scenarios": [{"id": s.id, "name": s.name} for s in existing],
            })
    except AgentUnavailable as exc:
        raise AuthoringError(
            "Scenario authoring needs either an Anthropic API key on this engine "
            f"(ANTHROPIC_API_KEY) or a reachable Agentic AI service: {exc}")

    spec = resp.result
    action_keys = {a.key for a in actions}
    existing_ids = {s.id for s in existing}
    valid_types = {t.key for t in actor_types}

    # fault action: an existing catalog key, or a declared custom action we register
    fault_key = (spec.get("fault_action") or "").strip()
    new_actions: list[ActionSpec] = []
    if fault_key not in action_keys:
        declared = next((c for c in spec.get("custom_actions", [])
                         if c.get("key") == fault_key and fault_key), None)
        if declared:
            new_actions.append(ActionSpec(
                key=fault_key,
                name=declared.get("name") or fault_key.replace("_", " ").title(),
                category=declared.get("category") or "fault",
                domain=domain, requires_target=False))
        elif actions:
            fault_key = actions[0].key
        else:
            raise AuthoringError(
                f"'{domain}' has no registered actions and none was declared — "
                "nothing this domain can run.")

    # target: keep only a validated actor type, and give it a world to inject into
    target_type = (spec.get("target_type") or "").strip()
    target = None
    environment = None
    if target_type and target_type in valid_types:
        target = TargetSelector(by="type", value=target_type)
        environment = EnvironmentSpec(
            domain=domain,
            actors=[ActorSpec(id="authored-1", type=target_type,
                              name=f"{target_type.replace('_', ' ').title()} (authored)")])

    role = spec.get("role") if spec.get("role") in roles else (roles[0] if roles else "response")

    # cascade edges: only to scenarios that actually exist in this domain
    triggers: list[Trigger] = []
    for edge in (spec.get("cascades") or [])[:2]:
        sid = edge.get("scenario_id")
        if sid not in existing_ids:
            continue
        condition = edge.get("condition") or "containment_rate < 1"
        if condition != "always" and not any(
                k in condition for k in ("containment_rate", "score", "prevented")):
            condition = "containment_rate < 1"
        triggers.append(Trigger(
            kind="kpi_threshold" if condition != "always" else "scenario_complete",
            condition=condition,
            spawns=[CascadeSpawn(scenario_id=sid, delay_min=float(edge.get("delay_min") or 15.0))]))

    risk = spec.get("risk_level") if spec.get("risk_level") in _RISKS else "high"
    impact = spec.get("impact_level") if spec.get("impact_level") in _IMPACTS else "medium"
    try:
        delay_s = max(60, min(900, int(spec.get("delay_s") or 240)))
    except (TypeError, ValueError):
        delay_s = 240

    name = (spec.get("name") or f"Authored: {prompt[:48]}").strip()[:90]
    scenario = Scenario(
        id=f"{domain}.authored_{_slug(name)}_{uuid.uuid4().hex[:6]}",
        name=name, domain=domain,
        description=(spec.get("description") or prompt.strip())[:400],
        node_kind="fault", category=(spec.get("category") or "operational")[:24],
        impact_level=impact,
        phases=["detect", "diagnose", "respond"],
        steps=[ScenarioStep(id="s1", action=fault_key, phase="detect", at_min=0.0,
                            is_inject=True, target=target,
                            label=(spec.get("fault_label") or name)[:160])],
        decision_gates=[DecisionGate(
            id="g1", trigger="s1", name=(spec.get("gate_name") or "Operator Response")[:80],
            correct_action=(spec.get("correct_action") or "Contain the fault.")[:300],
            risk_level=risk, description=(spec.get("gate_description") or "")[:300],
            consequence_of_delay=(spec.get("consequence_of_delay") or "")[:300],
            delay_s=delay_s)],
        objectives=[ScenarioObjective(
            text=(spec.get("objective") or "Fault correctly contained")[:200],
            role=role, condition="containment_rate == 1")],
        recommended_environment=environment,
        tags=list({*(spec.get("tags") or []), "authored", "ai"})[:6],
        triggers=triggers,
        custom_actions=new_actions,
    )
    for action in new_actions:
        register_action(action)
    register_scenario(scenario)
    return scenario


async def author_scenario(domain: str, prompt: str) -> Scenario:
    """Author, validate, register. Returns the runnable Scenario.

    Provider selection:
      * ANTHROPIC_API_KEY set on the engine → author directly with Claude (below),
        with structured output + a one-round repair loop.
      * otherwise → delegate to the AUTOMIND Agentic AI platform, which authors with
        whatever key it holds (OpenAI or Anthropic) or its deterministic stub.
    Either way the spec is validated against the live catalog before anything registers.
    """
    if get_plugin(domain) is None:
        raise AuthoringError(f"Unknown domain '{domain}'.")
    if not (prompt or "").strip():
        raise AuthoringError("Describe the scenario you want in a sentence or two.")

    if not settings.anthropic_api_key:
        return await _author_via_agentic(domain, prompt)

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
