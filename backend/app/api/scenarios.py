"""GET/POST /scenarios/* — the scenario library + NL authoring.

Per the porting guide: authoring delegates to Agentic AI, this layer never calls an
LLM directly. The model writes the SPEC (fault, decision gate, cascade edges); this
layer validates every reference against the domain catalog, assembles a Scenario
deterministically, registers it, and returns it — immediately runnable.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..engine.catalog.spec import ActionSpec, actions_for_domain
from ..engine.environment import ActorSpec, EnvironmentSpec
from ..engine.models.actors import actor_types_for_domain
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
from ..services.agent_client import AgentUnavailable, author_scenario_from_nl
from ..services.custom_actions import persist_custom_action

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
def list_scenarios(domain: str = "generic"):
    return scenarios_for_domain(domain)


@router.get("/{scenario_id}")
def get_one(scenario_id: str):
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(404, f"Unknown scenario '{scenario_id}'")
    return scenario


class AuthorRequest(BaseModel):
    domain: str
    prompt: str


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:40] or uuid.uuid4().hex[:8]


_RISKS = {"low", "medium", "high", "extreme"}
_IMPACTS = {"low", "medium", "high", "critical"}


@router.post("/author")
async def author(req: AuthorRequest):
    """Author a runnable scenario from natural language, via the Agentic AI.

    The AI writes the spec; everything it references is validated here:
      * fault action must exist in the domain catalog — or be declared as a
        custom action, which we register AND persist (survives restarts);
      * cascade targets must be existing scenarios of this domain;
      * target/actor types and roles must come from the domain plugin.
    422 = the description couldn't be turned into something this domain can run.
    """
    plugin = get_plugin(req.domain)
    if plugin is None:
        raise HTTPException(404, f"Unknown domain '{req.domain}'")
    if not req.prompt.strip():
        raise HTTPException(422, "Describe the failure situation in a sentence or two.")

    actions = actions_for_domain(req.domain)
    actor_types = actor_types_for_domain(req.domain)
    roles = [r.name for r in plugin.roles()]
    existing = scenarios_for_domain(req.domain)

    try:
        resp = await author_scenario_from_nl(
            req.domain, req.prompt.strip(),
            context={
                "actions": [{"key": a.key, "name": a.name, "category": a.category}
                            for a in actions],
                "roles": roles,
                "actor_types": [{"key": t.key} for t in actor_types],
                "existing_scenarios": [{"id": s.id, "name": s.name} for s in existing],
            })
    except AgentUnavailable as exc:
        raise HTTPException(503, f"Scenario authoring needs the Agentic AI service: {exc}")

    spec = resp.result
    action_keys = {a.key for a in actions}
    existing_ids = {s.id for s in existing}

    # ── fault action: catalog key, or a declared custom action ──────────
    fault_key = (spec.get("fault_action") or "").strip()
    custom_registered: list[dict] = []
    if fault_key not in action_keys:
        declared = next((c for c in spec.get("custom_actions", [])
                         if c.get("key") == fault_key and fault_key), None)
        if declared:
            action = ActionSpec(
                key=fault_key,
                name=declared.get("name") or fault_key.replace("_", " ").title(),
                category=declared.get("category") or "fault",
                domain=req.domain,
                requires_target=False,     # authored faults run without a mandatory target
            )
            persist_custom_action(action)
            custom_registered.append({"key": action.key, "name": action.name,
                                      "category": action.category})
            action_keys.add(fault_key)
        elif actions:
            fault_key = actions[0].key    # coerce to the closest thing that can run
        else:
            raise HTTPException(
                422, f"'{req.domain}' has no registered actions and the model "
                     f"declared no custom action — nothing this domain can run.")

    # ── target: only keep a validated actor type ────────────────────────
    target_type = (spec.get("target_type") or "").strip()
    valid_types = {t.key for t in actor_types}
    target = None
    environment = None
    if target_type and target_type in valid_types:
        target = TargetSelector(by="type", value=target_type)
        environment = EnvironmentSpec(
            domain=req.domain,
            actors=[ActorSpec(id="authored-1", type=target_type,
                              name=f"{target_type.replace('_', ' ').title()} (authored)")],
        )

    role = spec.get("role") if spec.get("role") in roles else (roles[0] if roles else "response")

    # ── cascade edges: only to scenarios that actually exist ────────────
    triggers: list[Trigger] = []
    for edge in (spec.get("cascades") or [])[:2]:
        sid = edge.get("scenario_id")
        if sid not in existing_ids:
            continue
        condition = edge.get("condition") or "containment_rate < 1"
        if condition not in ("always",) and "containment_rate" not in condition \
                and "score" not in condition and "prevented" not in condition:
            condition = "containment_rate < 1"
        triggers.append(Trigger(
            kind="kpi_threshold" if condition != "always" else "scenario_complete",
            condition=condition,
            spawns=[CascadeSpawn(scenario_id=sid,
                                 delay_min=float(edge.get("delay_min") or 15.0))],
        ))

    risk = spec.get("risk_level") if spec.get("risk_level") in _RISKS else "high"
    impact = spec.get("impact_level") if spec.get("impact_level") in _IMPACTS else "medium"
    try:
        delay_s = max(60, min(900, int(spec.get("delay_s") or 240)))
    except (TypeError, ValueError):
        delay_s = 240

    name = (spec.get("name") or f"Authored: {req.prompt[:48]}").strip()[:90]
    scenario = Scenario(
        id=f"{req.domain}.authored_{_slug(name)}_{uuid.uuid4().hex[:6]}",
        name=name,
        domain=req.domain,
        description=(spec.get("description") or req.prompt.strip())[:400],
        node_kind="fault",
        category=(spec.get("category") or "operational")[:24],
        impact_level=impact,
        phases=["detect", "diagnose", "respond"],
        steps=[ScenarioStep(
            id="s1", action=fault_key, phase="detect", at_min=0.0, is_inject=True,
            target=target, label=(spec.get("fault_label") or name)[:160],
        )],
        decision_gates=[DecisionGate(
            id="g1", trigger="s1",
            name=(spec.get("gate_name") or "Operator Response")[:80],
            correct_action=(spec.get("correct_action") or "Contain the fault.")[:300],
            risk_level=risk,
            description=(spec.get("gate_description") or "")[:300],
            consequence_of_delay=(spec.get("consequence_of_delay") or "")[:300],
            delay_s=delay_s,
        )],
        objectives=[ScenarioObjective(
            text=(spec.get("objective") or "Fault correctly contained")[:200],
            role=role, condition="containment_rate == 1",
        )],
        recommended_environment=environment,
        tags=list({*(spec.get("tags") or []), "authored", "ai"})[:6],
        triggers=triggers,
    )

    register_scenario(scenario)

    return {
        **scenario.model_dump(mode="json"),
        "custom_actions": custom_registered,
        "authoring_mode": resp.mode,        # "agent" (LLM wrote it) or "stub" (template)
    }
