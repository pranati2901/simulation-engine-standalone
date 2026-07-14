"""GET /catalog/* — actor types, resource types, actions, roles for a domain.

Mirrors GoalCert's api/catalog.py, generalized. The Twin's own /faults-equivalent
catalog can be cross-referenced here once that service exists (see the porting guide's
note: "GET /faults returns the catalogue sourced from the Twin").
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..engine.catalog.spec import actions_for_domain
from ..engine.models.actors import actor_types_for_domain
from ..engine.models.resources import resource_types_for_domain
from ..plugins.registry import get_plugin, list_plugins

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/domains")
def domains():
    return [{"key": p.key, "name": p.name} for p in list_plugins()]


@router.get("/assets")
def all_assets():
    """All actor types across every registered domain — the Hub expects this at
    /catalog/assets as a flat list."""
    results = []
    for plugin in list_plugins():
        for at in actor_types_for_domain(plugin.key):
            results.append({
                "key": at.key,
                "name": at.name,
                "category": at.category,
                "domain": plugin.key,
                "default_criticality": at.default_criticality,
            })
    return results


@router.get("/techniques")
def all_techniques():
    """All actions across every registered domain — the Hub expects this at
    /catalog/techniques (named 'techniques' for GoalCert legacy compat)."""
    results = []
    for plugin in list_plugins():
        for action in actions_for_domain(plugin.key):
            results.append({
                "key": action.key,
                "name": action.name,
                "category": action.category,
                "domain": plugin.key,
                "requires_target": action.requires_target,
            })
    return results


@router.get("/roles")
def all_roles():
    """All roles across every registered domain."""
    results = []
    for plugin in list_plugins():
        for role in plugin.roles():
            results.append({
                "name": role.name,
                "side": role.side,
                "domain": plugin.key,
            })
    return results


@router.get("/{domain}/actor-types")
def actor_types(domain: str):
    if get_plugin(domain) is None:
        raise HTTPException(404, f"Unknown domain '{domain}'")
    return actor_types_for_domain(domain)


@router.get("/{domain}/resource-types")
def resource_types(domain: str):
    if get_plugin(domain) is None:
        raise HTTPException(404, f"Unknown domain '{domain}'")
    return resource_types_for_domain(domain)


@router.get("/{domain}/actions")
def actions(domain: str):
    if get_plugin(domain) is None:
        raise HTTPException(404, f"Unknown domain '{domain}'")
    return actions_for_domain(domain)


@router.get("/{domain}/roles")
def roles(domain: str):
    plugin = get_plugin(domain)
    if plugin is None:
        raise HTTPException(404, f"Unknown domain '{domain}'")
    return plugin.roles()
