"""Catalog endpoints — the reusable building blocks (served live from code registries)."""
from __future__ import annotations

from fastapi import APIRouter

from app.engine.catalog import spec
from app.engine.models import assets, controls
from app.engine import workflows as wf

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/assets")
def asset_catalog() -> list[dict]:
    return assets.catalog()


@router.get("/controls")
def control_catalog() -> list[dict]:
    return controls.catalog()


@router.get("/techniques")
def technique_catalog() -> list[dict]:
    return spec.catalog()


@router.get("/roles")
def role_catalog() -> list[dict]:
    """The five teams + their descriptions (for role selection)."""
    return wf.role_catalog()


@router.get("/workflows")
def workflow_catalog() -> list[dict]:
    """Team workflows (the reusable Role & Workflow catalog)."""
    return wf.workflow_catalog()
