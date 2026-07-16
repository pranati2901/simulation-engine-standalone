"""Plugin registry: the single place the engine looks to discover what domains exist.

Adding a new vertical (hospital, EV, DroneForce, ...) means writing a new package
under plugins/<domain>/ implementing DomainPlugin, and adding one line here. Nothing
in engine/ ever needs to change.
"""
from __future__ import annotations

from .base import DomainPlugin

_PLUGINS: dict[str, DomainPlugin] = {}
_loaded = False


def register(plugin: DomainPlugin) -> None:
    plugin.register()
    _PLUGINS[plugin.key] = plugin


def get_plugin(key: str) -> DomainPlugin | None:
    return _PLUGINS.get(key)


def list_plugins() -> list[DomainPlugin]:
    return sorted(_PLUGINS.values(), key=lambda p: p.key)


def load_all() -> None:
    """Import and register every domain plugin. Called once at app startup
    (see app/main.py). Add new verticals here as they're built:

        from .aerospace.plugin import AerospacePlugin
        from .railway.plugin import RailwayPlugin
        from .hospital.plugin import HospitalPlugin
        from .defence.plugin import DefencePlugin
        from .ev.plugin import EVPlugin
        from .droneforce.plugin import DroneForcePlugin

        for plugin_cls in (AerospacePlugin, RailwayPlugin, HospitalPlugin,
                           DefencePlugin, EVPlugin, DroneForcePlugin):
            register(plugin_cls())
    """
    global _loaded
    if _loaded:
        return
    from .aerospace.plugin import AerospacePlugin
    from .railway.plugin import RailwayPlugin
    from .hospital.plugin import HospitalPlugin
    from .defence.plugin import DefencePlugin
    from .ev.plugin import EVPlugin

    for plugin_cls in (AerospacePlugin, RailwayPlugin, HospitalPlugin, DefencePlugin, EVPlugin):
        register(plugin_cls())
    _loaded = True
