"""EnvironmentSpec — the operator-composed environment — and the World builder.

The asset-selection feature produces an EnvironmentSpec (which assets, their zones/criticality,
and which controls are enabled/where). build_world() instantiates it into a live World, applying
asset/control type defaults and auto-attaching asset-scoped controls by category.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import Health, SecurityState
from .models.assets import get_asset_type
from .models.controls import get_control_type
from .world import AssetInstance, ControlInstance, World


class VMBindingSpec(BaseModel):
    """Optional: maps a modeled asset to a real VM for live attack execution."""
    host: str                                    # IP or hostname
    port: int = 5986                             # WinRM HTTPS default
    protocol: str = "winrm"                      # "winrm" or "ssh"
    username: str = "Administrator"
    password: str = ""
    credential_ref: str = ""                     # key into a secrets store
    os: str = "windows"                          # "windows" or "linux"


class AssetSpec(BaseModel):
    id: str
    type: str
    name: str | None = None
    role: str | None = None
    zone: str | None = None
    criticality: int | None = None
    data_sensitivity: int | None = None
    props: dict | None = None
    vm: VMBindingSpec | None = None              # optional: real VM binding


class ControlSpec(BaseModel):
    id: str
    type: str
    name: str | None = None
    enabled: bool = True
    scope: str | None = None             # override default scope
    targets: list[str] | None = None     # asset ids (asset scope) / zones (zone scope)
    props: dict | None = None


class EnvironmentSpec(BaseModel):
    assets: list[AssetSpec] = Field(default_factory=list)
    controls: list[ControlSpec] = Field(default_factory=list)

    def asset_types(self) -> set[str]:
        return {a.type for a in self.assets}


def _build_asset(spec: AssetSpec) -> AssetInstance:
    at = get_asset_type(spec.type)
    props = dict(at.default_props())
    if spec.props:
        props.update(spec.props)
    # Carry VM binding into props so the resolver can check it
    if spec.vm is not None:
        props["vm"] = spec.vm.model_dump()
    return AssetInstance(
        id=spec.id,
        type_key=spec.type,
        name=spec.name or at.NAME,
        role=spec.role,
        zone=spec.zone or at.DEFAULT_ZONE,
        criticality=spec.criticality if spec.criticality is not None else at.DEFAULT_CRITICALITY,
        data_sensitivity=(spec.data_sensitivity if spec.data_sensitivity is not None
                          else at.DEFAULT_DATA_SENSITIVITY),
        security_state=SecurityState.SAFE,
        health=Health.NOMINAL,
        props=props,
    )


# Default semantic roles. Composer/Builder environments usually set only `type`, but playbook steps
# target ROLES like "primary_endpoint" / "sensitive_share". Give each role-less asset a sensible role
# so role-targeted attack steps resolve instead of failing with "no_target" (which otherwise collapses
# the whole kill chain at step 1). The first asset of a role-bearing type claims the primary role; any
# extra assets of that type fall back to a role equal to their type.
_TYPE_DEFAULT_ROLE: dict[str, str] = {
    "endpoint": "primary_endpoint",
    "file_share": "sensitive_share",
    "domain_controller": "domain_controller",
    "erp": "crown_jewel",
    "cloud": "cloud",
    "email_server": "mail_gateway",
    "mes": "ot_boundary",
    "ot_plc": "plc",
}


def _assign_default_roles(assets: list[AssetInstance]) -> None:
    claimed = {a.role for a in assets if a.role}
    for a in assets:  # spec order — deterministic; the first candidate claims the semantic role
        if a.role:
            continue
        dr = _TYPE_DEFAULT_ROLE.get(a.type_key)
        if dr and dr not in claimed:
            a.role = dr
            claimed.add(dr)
        else:
            a.role = a.type_key  # fallback: role == type so type/role targeting both work


def build_world(env: EnvironmentSpec) -> World:
    assets = [_build_asset(a) for a in env.assets]
    _assign_default_roles(assets)
    asset_by_id = {a.id: a for a in assets}

    controls: list[ControlInstance] = []
    for cspec in env.controls:
        ct = get_control_type(cspec.type)
        scope = cspec.scope or ct.DEFAULT_SCOPE
        targets = list(cspec.targets) if cspec.targets is not None else []
        # Composer convenience: asset-scoped control with no explicit targets auto-attaches
        # to every asset whose category it covers.
        if scope == "asset" and not targets and ct.ATTACHES_TO:
            cats = {c.value for c in ct.ATTACHES_TO}
            targets = [a.id for a in assets if get_asset_type(a.type_key).CATEGORY.value in cats]
        controls.append(ControlInstance(
            id=cspec.id,
            type_key=cspec.type,
            name=cspec.name or ct.NAME,
            enabled=cspec.enabled,
            scope=scope,  # type: ignore[arg-type]
            targets=targets,
            props=cspec.props or {},
        ))

    # Validate control targets reference real assets (asset scope).
    for c in controls:
        if c.scope == "asset":
            c.targets = [t for t in c.targets if t in asset_by_id]

    return World(assets=assets, controls=controls)
