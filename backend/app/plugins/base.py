"""Layer 10 — Domain Plugin interface.

The engine core (engine/) knows nothing about aerospace, railways, or hospitals. A
domain plugin is the only thing that does. It registers:
  - actor types    (engine.models.actors.register_actor_type)
  - resource types (engine.models.resources.register_resource_type)
  - actions        (engine.catalog.spec.register_action)
  - roles          (engine.workflows.register_role)
  - default workflows per role
  - scenario definitions (scenarios/definitions/)
  - domain-specific KPIs / report sections (optional)

Adding a new domain = writing a new plugin package and registering it in
plugins/registry.py. The engine never needs to change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..engine.workflows import RoleInfo, Workflow


class DomainPlugin(ABC):
    """Subclass this once per domain (aerospace, railway, hospital, defence, ev, ...)."""

    key: str          # unique domain id, e.g. "aerospace"
    name: str         # display name, e.g. "Aerospace (Collins Aerospace POC)"

    @abstractmethod
    def register(self) -> None:
        """Register this domain's actor types, resource types, actions and roles into
        the engine's global registries. Called once at startup by registry.load_all().
        """
        raise NotImplementedError

    def default_workflows(self) -> dict[str, Workflow]:
        """role -> Workflow. Override to ship a default procedure per role."""
        return {}

    def roles(self) -> list[RoleInfo]:
        """Override to declare this domain's roles (mapped onto the generic Side enum)."""
        return []

    def extra_kpis(self, world, events) -> dict[str, float]:
        """Override to contribute domain-specific KPIs on top of the generic set."""
        return {}

    def report_sections(self, run_result) -> list[dict]:
        """Override to contribute domain-specific report sections (Layer 9 — Reports)."""
        return []
