"""GoalCert deterministic, model-driven simulation engine (pure; no web/db deps).

Importing this package registers the asset, control and technique catalogs so the engine
is ready to use.
"""
# Side-effect imports populate the registries.
from .models import assets as _assets  # noqa: F401
from .models import controls as _controls  # noqa: F401
from .catalog import techniques as _techniques  # noqa: F401
