"""Conversational scenario revision — "add a coolant failure downstream of the spindle"
turns an existing Scenario into a revised, still-runnable one.

RELATIONSHIP TO authoring.py
----------------------------
Authoring writes a scenario from a blank page. Revision starts from one that already
exists and applies an instruction to it. Both produce an AuthoredBundle, and both are
validated against the LIVE catalog by authoring._validate before anything is runnable —
that check is the whole reason an authored scenario works instead of silently doing
nothing, and a revision needs it exactly as much.

WHY REVISE AND COMMIT ARE SEPARATE
----------------------------------
`revise` returns a proposal and registers NOTHING. The operator sees what changed and
decides. `commit` takes that proposal back and registers it. Two reasons:
  1. The model is not deterministic. If commit re-ran the model, the operator would be
     approving one scenario and registering a different one.
  2. Auto-registering every chat turn would litter the library with half-thoughts.

WHY A REVISION IS A NEW SCENARIO
--------------------------------
It never mutates the original in place. The seed library is SHARED across every tenant
(scenarios/loader.py: org_id NULL = seed), other scenarios cascade INTO those seeds by id,
and an in-place edit would silently change every cascade that spawns them — for every
tenant at once. A revision is a variant with its own id, owned by the org that made it;
the original is untouched.
"""
from __future__ import annotations

import json
import re
import uuid

from pydantic import ValidationError

from ..core.settings import settings
from ..engine.catalog.spec import register_action
from ..engine.scenario import Scenario
from ..plugins.registry import get_plugin
from ..scenarios.loader import get_scenario, register_scenario
from .authoring import AuthoredBundle, AuthoringError, _catalog_brief, _validate

REVISE_SYSTEM = """You revise scenarios for a deterministic operational simulation engine.

You are handed a scenario that ALREADY WORKS and an operator's instruction. Return the
whole revised scenario — not a patch. You are writing a SPEC, not a story: you do not
decide what happens when it runs, the engine does.

REVISION RULES
- Apply ONLY what the instruction asks. Everything the operator did not mention must come
  back byte-identical. You are not here to improve the scenario.
- Keep `domain` exactly as it was.
- Set `id` to the NEW_ID given below, verbatim. Never reuse the original id.
- Same vocabulary rules as authoring: every steps[].action must be an existing action key
  or one you declare in new_actions; every steps[].target.value must be an EXISTING actor
  type (never invented); every steps[].phase must appear in phases; every
  decision_gates[].trigger must be one of your steps[].id; every
  triggers[].spawns[].scenario_id must be an EXISTING scenario id.
- Any actor type your steps target MUST also appear in recommended_environment.actors, or
  the fault injects into an empty world and simulates nothing.
- triggers[].kind is ALWAYS the literal "state". The firing rule goes in "condition":
  "always" for an inherent consequence, "containment_rate < 1" for one the operator could
  have prevented.

ALSO RETURN, as the FIRST line of your reply and OUTSIDE the JSON, nothing at all — reply
with the JSON object only. The change summary goes in the scenario's `description` only if
the instruction actually changed what the scenario represents."""


def _new_id(original_id: str, domain: str) -> str:
    """A fresh id for the variant. Strips any existing _rev_xxxxxx suffix so revising a
    revision doesn't accrete `_rev_a1b2c3_rev_d4e5f6...` forever."""
    stem = re.sub(r"_rev_[0-9a-f]{6}$", "", original_id or f"{domain}.scenario")
    return f"{stem}_rev_{uuid.uuid4().hex[:6]}"


def _summarise_changes(before: Scenario, after: Scenario) -> list[str]:
    """A plain-language diff for the operator. Deliberately computed HERE from the two
    specs rather than asked of the model — the model would happily claim it made a change
    it didn't. This reports what actually differs."""
    out: list[str] = []

    if (before.name or "") != (after.name or ""):
        out.append(f"Renamed to “{after.name}”")
    if (before.impact_level or "") != (after.impact_level or ""):
        out.append(f"Impact level {before.impact_level} → {after.impact_level}")
    if (before.category or "") != (after.category or ""):
        out.append(f"Category {before.category} → {after.category}")

    b_steps = {s.id: s for s in before.steps}
    a_steps = {s.id: s for s in after.steps}
    for sid in a_steps.keys() - b_steps.keys():
        out.append(f"Added step “{a_steps[sid].label or sid}” ({a_steps[sid].action})")
    for sid in b_steps.keys() - a_steps.keys():
        out.append(f"Removed step “{b_steps[sid].label or sid}”")
    for sid in b_steps.keys() & a_steps.keys():
        if b_steps[sid].action != a_steps[sid].action:
            out.append(f"Step “{sid}” action {b_steps[sid].action} → {a_steps[sid].action}")

    b_spawn = {(s.scenario_id) for t in before.triggers for s in t.spawns}
    a_spawn = {(s.scenario_id) for t in after.triggers for s in t.spawns}
    for sid in a_spawn - b_spawn:
        out.append(f"Now cascades into {sid}")
    for sid in b_spawn - a_spawn:
        out.append(f"No longer cascades into {sid}")

    b_prev = sum(1 for t in before.triggers if "containment_rate" in (t.condition or ""))
    a_prev = sum(1 for t in after.triggers if "containment_rate" in (t.condition or ""))
    if a_prev != b_prev:
        out.append(f"Preventable consequences {b_prev} → {a_prev}")

    b_gates = {g.id for g in before.decision_gates}
    a_gates = {g.id for g in after.decision_gates}
    for gid in a_gates - b_gates:
        out.append("Added a decision gate")
    for gid in b_gates - a_gates:
        out.append("Removed a decision gate")
    for g_after in after.decision_gates:
        g_before = next((g for g in before.decision_gates if g.id == g_after.id), None)
        if g_before and g_before.risk_level != g_after.risk_level:
            out.append(f"Gate “{g_after.name}” risk {g_before.risk_level} → {g_after.risk_level}")

    b_actors = {a.type for a in (before.recommended_environment.actors if before.recommended_environment else [])}
    a_actors = {a.type for a in (after.recommended_environment.actors if after.recommended_environment else [])}
    for t in a_actors - b_actors:
        out.append(f"Added {t.replace('_', ' ')} to the environment")

    return out or ["No structural change — the spec is unchanged."]


async def _ask_revision(domain: str, current: Scenario, instruction: str, new_id: str,
                        repair: str | None = None, org: str | None = None) -> AuthoredBundle:
    # Lazy import — the rest of the engine runs fine without the SDK. But an unguarded
    # ModuleNotFoundError here escapes as a bare 500 with an EMPTY body: the UI shows
    # nothing and the operator has no idea the package is simply missing. `anthropic` is
    # in requirements.txt, so this only fires on a venv that was never fully installed —
    # which is exactly when a clear message is worth most.
    try:
        from anthropic import AsyncAnthropic
    except ModuleNotFoundError as exc:
        raise AuthoringError(
            "The Anthropic SDK is not installed on this engine — run "
            "`pip install -r requirements.txt` in backend/ and restart. "
            f"({exc})")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    user = (
        f"{_catalog_brief(domain, org)}\n\n"
        f"NEW_ID (use this as the revised scenario's id, verbatim): {new_id}\n\n"
        f"CURRENT SCENARIO (this is what you are revising):\n"
        f"{current.model_dump_json(indent=2, exclude_none=True)}\n\n"
        f"OPERATOR'S INSTRUCTION:\n{instruction}"
    )
    if repair:
        user += ("\n\nYOUR PREVIOUS ATTEMPT WAS NOT ACCEPTED. Fix exactly these problems and "
                 "return the whole bundle again:\n" + repair)
    user += ("\n\nReturn ONLY a single JSON object that validates against this JSON Schema — "
             "no prose, no markdown fences:\n" + json.dumps(AuthoredBundle.model_json_schema()))

    resp = await client.messages.create(
        model=settings.authoring_model,
        max_tokens=16000,
        system=REVISE_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise AuthoringError("The model declined this revision.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    payload = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]

    try:
        return AuthoredBundle.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValidationError) as e:
        if repair:   # already repaired once — don't loop
            raise AuthoringError(f"The model returned a scenario that does not fit the engine's schema: {e}")
        fix = f"Your JSON did not fit the engine schema. Fix EXACTLY this:\n{e}"
        return await _ask_revision(domain, current, instruction, new_id, repair=fix, org=org)


async def revise_scenario(scenario_id: str, instruction: str,
                          base: dict | None = None, org: str | None = None) -> dict:
    """Propose a revision. Validates but registers NOTHING.

    `base` lets the chat revise its own last proposal instead of the stored seed, so a
    conversation compounds ("make it worse" then "and add a gate") rather than each turn
    starting over from the original.

    Returns {scenario, changes, base_id} — hand `scenario` straight back to commit().
    """
    if not (instruction or "").strip():
        raise AuthoringError("Say what you'd like to change.")

    if base:
        try:
            current = Scenario.model_validate(base)
        except ValidationError as e:
            raise AuthoringError(f"The scenario being revised is not a valid spec: {e}")
    else:
        current = get_scenario(scenario_id, org)
        if current is None:
            raise AuthoringError(f"Scenario '{scenario_id}' not found.")

    domain = current.domain
    if get_plugin(domain) is None:
        raise AuthoringError(f"Unknown domain '{domain}'.")
    if not settings.anthropic_api_key:
        raise AuthoringError(
            "Scenario revision needs an Anthropic API key on this engine (ANTHROPIC_API_KEY).")

    new_id = _new_id(current.id, domain)
    bundle = await _ask_revision(domain, current, instruction, new_id, org=org)

    problems = _validate(bundle, domain, org)
    if problems:
        bundle = await _ask_revision(domain, current, instruction, new_id,
                                     repair="\n".join(f"- {p}" for p in problems), org=org)
        problems = _validate(bundle, domain, org)
    if problems:
        raise AuthoringError(
            "Could not produce a runnable revision. The model kept using things this "
            "domain doesn't have:\n" + "\n".join(f"• {p}" for p in problems))

    revised = bundle.scenario.model_copy(update={"custom_actions": bundle.new_actions})
    return {
        "scenario": revised.model_dump(mode="json", exclude_none=True),
        "changes": _summarise_changes(current, revised),
        "base_id": current.id,
    }


async def commit_scenario(spec: dict, org: str | None = None) -> Scenario:
    """Register a previewed revision. Re-validates from scratch — this arrives from the
    browser, so the fact that we validated it before proves nothing about what came back.
    """
    try:
        scenario = Scenario.model_validate(spec)
    except ValidationError as e:
        raise AuthoringError(f"That is not a valid scenario spec: {e}")

    domain = scenario.domain
    if get_plugin(domain) is None:
        raise AuthoringError(f"Unknown domain '{domain}'.")

    bundle = AuthoredBundle(new_actions=list(scenario.custom_actions or []), scenario=scenario)
    problems = _validate(bundle, domain, org)
    if problems:
        raise AuthoringError("This revision is not runnable:\n" + "\n".join(f"• {p}" for p in problems))

    # Same ordering rule as authoring: the vocabulary rides ON the scenario row
    # (custom_actions) so it survives a restart, AND registers in memory so it's runnable
    # in this process without waiting for a reload.
    for action in (scenario.custom_actions or []):
        register_action(action)
    try:
        register_scenario(scenario, org)
    except PermissionError as e:
        # Defence in depth. _validate already rejects a duplicate id, so this ownership
        # guard shouldn't be reachable from here — but "shouldn't be reachable" is exactly
        # what turns into a 500 later. Surface it as the 422 the caller can act on.
        raise AuthoringError(str(e))
    return scenario
