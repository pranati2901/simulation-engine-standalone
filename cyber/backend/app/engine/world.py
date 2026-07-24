"""Mutable world state: asset & control instances plus attacker progress.

The World is the live environment a run mutates. It is built from an EnvironmentSpec and
carried through the engine. All query helpers are deterministic (sorted where order matters).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .enums import CredScope, Health, SecurityState


class AssetInstance(BaseModel):
    id: str
    type_key: str
    name: str
    role: str | None = None          # selector tag used by playbooks (e.g. "primary_endpoint")
    zone: str = "corp"               # network segment / zone
    criticality: int = 3             # 1..5
    security_state: SecurityState = SecurityState.SAFE
    health: Health = Health.NOMINAL
    data_sensitivity: int = 1        # 1..5 — relevance for exfil/impact scoring
    props: dict[str, Any] = Field(default_factory=dict)

    @property
    def compromised(self) -> bool:
        return self.security_state == SecurityState.COMPROMISED


class ControlInstance(BaseModel):
    id: str
    type_key: str
    name: str
    enabled: bool = True
    scope: Literal["global", "zone", "asset"] = "global"
    targets: list[str] = Field(default_factory=list)  # asset ids (asset scope) / zones (zone scope)
    props: dict[str, Any] = Field(default_factory=dict)
    disabled_by_attacker: bool = False

    @property
    def active(self) -> bool:
        return self.enabled and not self.disabled_by_attacker

    def covers(self, asset: AssetInstance) -> bool:
        if self.scope == "global":
            return True
        if self.scope == "zone":
            return asset.zone in self.targets
        return asset.id in self.targets


class AttackerState(BaseModel):
    footholds: list[str] = Field(default_factory=list)  # asset ids under attacker control
    cred_scope: CredScope = CredScope.NONE
    disabled_control_types: list[str] = Field(default_factory=list)
    flags: dict[str, bool] = Field(default_factory=dict)  # c2, persistence, exfiltrated, in_ot ...

    def has_foothold(self) -> bool:
        return len(self.footholds) > 0

    def add_foothold(self, asset_id: str) -> None:
        if asset_id not in self.footholds:
            self.footholds.append(asset_id)

    def raise_creds(self, scope: CredScope) -> None:
        if scope.rank > self.cred_scope.rank:
            self.cred_scope = scope


class World:
    """Live environment container with deterministic query helpers."""

    def __init__(
        self,
        assets: list[AssetInstance],
        controls: list[ControlInstance],
        attacker: AttackerState | None = None,
    ) -> None:
        self.assets: dict[str, AssetInstance] = {a.id: a for a in assets}
        self.controls: dict[str, ControlInstance] = {c.id: c for c in controls}
        self.attacker: AttackerState = attacker or AttackerState()
        self.t: int = 0  # current sim seconds

    # ---- asset queries -------------------------------------------------------
    def get(self, asset_id: str) -> AssetInstance | None:
        return self.assets.get(asset_id)

    def by_type(self, type_key: str) -> list[AssetInstance]:
        return [a for a in self._sorted_assets() if a.type_key == type_key]

    def by_role(self, role: str) -> list[AssetInstance]:
        return [a for a in self._sorted_assets() if a.role == role]

    def has_type(self, type_key: str) -> bool:
        return any(a.type_key == type_key for a in self.assets.values())

    def _sorted_assets(self) -> list[AssetInstance]:
        return [self.assets[k] for k in sorted(self.assets)]

    def all_assets(self) -> list[AssetInstance]:
        return self._sorted_assets()

    def foothold_assets(self) -> list[AssetInstance]:
        return [self.assets[i] for i in self.attacker.footholds if i in self.assets]

    def zones(self) -> list[str]:
        return sorted({a.zone for a in self.assets.values()})

    def assets_in_zone(self, zone: str) -> list[AssetInstance]:
        return [a for a in self._sorted_assets() if a.zone == zone]

    def foothold_zones(self) -> set[str]:
        return {self.assets[i].zone for i in self.attacker.footholds if i in self.assets}

    # ---- control queries -----------------------------------------------------
    def controls_of_type(self, type_key: str) -> list[ControlInstance]:
        return [self.controls[k] for k in sorted(self.controls)
                if self.controls[k].type_key == type_key]

    def active_control_for(self, asset: AssetInstance, type_key: str) -> ControlInstance | None:
        """Return the first active control of the given type that covers the asset."""
        if type_key in self.attacker.disabled_control_types:
            return None
        for c in self.controls_of_type(type_key):
            if c.active and c.covers(asset):
                return c
        return None

    def active_global_control(self, type_key: str) -> ControlInstance | None:
        if type_key in self.attacker.disabled_control_types:
            return None
        for c in self.controls_of_type(type_key):
            if c.active:
                return c
        return None

    def reachable(self, target: AssetInstance) -> bool:
        """Can the attacker reach the target from a current foothold?

        Reachable if a foothold sits in the target's zone, or no active segmentation
        separates zones, or the attacker holds privileged+ credentials (can pivot).
        """
        if not self.attacker.has_foothold():
            return False
        if target.zone in self.foothold_zones():
            return True
        segmentation = self.active_global_control("segmentation")
        if segmentation is None:
            return True
        return self.attacker.cred_scope.rank >= CredScope.PRIVILEGED.rank
