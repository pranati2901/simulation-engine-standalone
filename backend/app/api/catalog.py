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
