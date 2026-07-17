"""GET/POST /studio/* — scenario authoring studio.

Create scenarios from natural language descriptions using AI, browse available
domains and fault types, and run authored scenarios directly.
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..core.settings import settings
from ..engine.catalog.spec import actions_for_domain
from ..engine.config import RunConfig
from ..engine.environment import EnvironmentSpec
from ..engine.scenario import (
    DecisionGate,
    Scenario,
    ScenarioObjective,
    ScenarioStep,
    TargetSelector,
)
from ..plugins.registry import get_plugin, list_plugins
from ..core.tenancy import current_org
from ..scenarios.loader import register_scenario
from ..services import runner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/studio", tags=["studio"])

# Map Hub twin domains to simulation engine domains
_DOMAIN_MAP = {
    "datacenter": "aerospace",
    "manufacturing": "aerospace",
    "edm-machine": "aerospace",
    "gas-turbine": "aerospace",
    "tram-network": "railway",
    "mrt-line": "railway",
    "ev-network": "railway",
    "naval-vessel": "defence",
}

def _resolve_domain(domain: str) -> str:
    return _DOMAIN_MAP.get(domain, domain)


@router.get("/domains")
def list_domains():
    """List available domains from the plugin registry."""
    return [
        {
            "key": p.key,
            "name": p.name,
            "roles": [{"name": r.name, "side": r.side} for r in p.roles()],
            "has_scenarios": True,
        }
        for p in list_plugins()
    ]


@router.get("/faults")
def list_faults(domain: str = Query(..., description="Domain key")):
    """List fault/action types available for a domain."""
    domain = _resolve_domain(domain)
    plugin = get_plugin(domain)
    if plugin is None:
        return []  # graceful fallback instead of 404
    actions = actions_for_domain(domain)
    return [
        {
            "key": a.key,
            "name": a.name,
            "category": a.category,
            "domain": a.domain,
            "requires_target": a.requires_target,
            "preconditions": a.preconditions,
        }
        for a in actions
    ]


class AuthorRequest(BaseModel):
    description: str
    domain: str


def _generate_scenario_with_anthropic(description: str, domain: str) -> dict:
    """Call Anthropic Claude to generate a scenario spec from natural language.

    Falls back to a template-based generator if the API key is not configured.
    """
    if not settings.anthropic_api_key:
        return _generate_scenario_fallback(description, domain)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        actions = actions_for_domain(domain)
        action_keys = [a.key for a in actions]
        plugin = get_plugin(domain)
        roles = [r.name for r in plugin.roles()] if plugin else []

        system_prompt = (
            "You are a simulation scenario author for the GoalCert Simulation Engine. "
            "Generate a structured scenario specification as JSON. "
            f"Domain: {domain}. "
            f"Available action keys: {action_keys}. "
            f"Available roles: {roles}. "
            "Return ONLY valid JSON with this structure: "
            '{"name": "...", "description": "...", "phases": ["detect", "diagnose", "respond"], '
            '"steps": [{"id": "s1", "action": "<action_key>", "phase": "<phase>", "at_min": 0, '
            '"label": "..."}], '
            '"decision_gates": [{"id": "g1", "trigger": "s1", "name": "...", '
            '"correct_action": "...", "risk_level": "high", "description": "...", '
            '"consequence_of_delay": "...", "delay_s": 300}], '
            '"objectives": [{"text": "...", "role": "response"}], '
            '"tags": ["..."], "impact_level": "medium", "category": "operational"}'
        )

        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": description}],
        )

        response_text = message.content[0].text
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response_text[start:end])
        return json.loads(response_text)

    except ImportError:
        logger.warning("anthropic package not installed, using fallback scenario generator")
        return _generate_scenario_fallback(description, domain)
    except Exception as e:
        logger.warning("Anthropic API call failed (%s), using fallback scenario generator", e)
        return _generate_scenario_fallback(description, domain)


def _generate_scenario_fallback(description: str, domain: str) -> dict:
    """Template-based fallback when Anthropic API is unavailable."""
    actions = actions_for_domain(domain)
    primary_action = actions[0].key if actions else "generic_fault"
    action_name = actions[0].name if actions else "System Fault"

    plugin = get_plugin(domain)
    primary_role = plugin.roles()[0].name if plugin and plugin.roles() else "response"

    return {
        "name": f"Generated: {description[:60]}",
        "description": description,
        "phases": ["detect", "diagnose", "respond"],
        "steps": [
            {
                "id": "s1",
                "action": primary_action,
                "phase": "detect",
                "at_min": 0,
                "label": f"{action_name} detected in the {domain} environment",
            },
        ],
        "decision_gates": [
            {
                "id": "g1",
                "trigger": "s1",
                "name": f"{action_name} Response",
                "correct_action": f"Identify root cause and apply corrective action for {action_name.lower()}",
                "risk_level": "high",
                "description": f"Respond to {action_name.lower()} within the required timeframe",
                "consequence_of_delay": "Fault escalates and impacts downstream operations",
                "delay_s": 300,
            },
        ],
        "objectives": [
            {"text": f"Fault correctly resolved by the {primary_role} team", "role": primary_role},
        ],
        "tags": [domain, "generated", "studio"],
        "impact_level": "medium",
        "category": "operational",
    }


@router.post("/scenarios/author")
async def author_scenario(req: AuthorRequest, org: str | None = Depends(current_org)):
    """Generate a scenario spec from natural language using AI."""
    domain = _resolve_domain(req.domain)
    plugin = get_plugin(domain)
    if plugin is None:
        plugin = get_plugin("aerospace")
        domain = "aerospace"

    spec = _generate_scenario_with_anthropic(req.description, domain)

    scenario_id = f"{domain}.studio_{uuid.uuid4().hex[:8]}"
    scenario = Scenario(
        id=scenario_id,
        name=spec.get("name", f"Studio Scenario - {req.description[:40]}"),
        domain=req.domain,
        description=spec.get("description", req.description),
        phases=spec.get("phases", ["detect", "diagnose", "respond"]),
        steps=[ScenarioStep(**s) for s in spec.get("steps", [])],
        decision_gates=[DecisionGate(**g) for g in spec.get("decision_gates", [])],
        objectives=[ScenarioObjective(**o) for o in spec.get("objectives", [])],
        tags=spec.get("tags", [req.domain, "studio"]),
        impact_level=spec.get("impact_level", "medium"),
        category=spec.get("category", "operational"),
        node_kind="fault",
    )

    # Owned by the calling tenant. Registering unscoped here would publish one org's
    # studio scenario into every other org's library.
    register_scenario(scenario, org)

    return {
        "scenario_id": scenario.id,
        "scenario": scenario.model_dump(mode="json"),
        "source": "anthropic" if settings.anthropic_api_key else "fallback",
    }


class StudioRunRequest(BaseModel):
    scenario_id: str
    config: RunConfig = RunConfig()
    environment: EnvironmentSpec | None = None


@router.post("/runs")
def studio_run(req: StudioRunRequest, org: str | None = Depends(current_org)):
    """Run a scenario created in the studio."""
    from ..scenarios.loader import get_scenario

    scenario = get_scenario(req.scenario_id, org)
    if scenario is None:
        raise HTTPException(404, f"Scenario '{req.scenario_id}' not found")

    env = req.environment or scenario.recommended_environment or EnvironmentSpec(domain=scenario.domain)
    config = req.config
    if config.domain == "generic":
        config = config.model_copy(update={"domain": scenario.domain})

    result = runner.execute(scenario, env, config)

    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "domain": scenario.domain,
        "duration_s": result.duration_s,
        "scores": result.scores,
        "kpis": result.kpis,
        "events_count": len(result.events),
        "objectives": result.objectives,
        "summary": result.summary,
    }
