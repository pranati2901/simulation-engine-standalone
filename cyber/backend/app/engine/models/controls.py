"""Control model framework + registry + concrete control types.

Controls are the defensive layer. Their *detection* and *prevention* relationships to
techniques are declared by the techniques themselves (single source of truth in the
technique catalog). A ControlType here provides metadata, default scope, and which asset
categories it can attach to — used by the environment composer and the selection UI.
"""
from __future__ import annotations

from ..enums import AssetCategory


class ControlType:
    KEY: str = ""
    NAME: str = ""
    ICON: str = "fa-lock"
    DESCRIPTION: str = ""
    DEFAULT_SCOPE: str = "global"          # global | zone | asset
    DEFAULT_ENABLED: bool = True
    # Asset categories an asset-scoped control auto-attaches to (composer convenience).
    ATTACHES_TO: tuple[AssetCategory, ...] = ()


_REGISTRY: dict[str, type[ControlType]] = {}


def register(cls: type[ControlType]) -> type[ControlType]:
    if not cls.KEY:
        raise ValueError(f"ControlType {cls.__name__} missing KEY")
    _REGISTRY[cls.KEY] = cls
    return cls


def get_control_type(key: str) -> type[ControlType]:
    if key not in _REGISTRY:
        raise KeyError(f"Unknown control type: {key}")
    return _REGISTRY[key]


def all_control_types() -> list[type[ControlType]]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def catalog() -> list[dict]:
    return [
        {
            "key": c.KEY,
            "name": c.NAME,
            "icon": c.ICON,
            "description": c.DESCRIPTION,
            "default_scope": c.DEFAULT_SCOPE,
            "default_enabled": c.DEFAULT_ENABLED,
            "attaches_to": [cat.value for cat in c.ATTACHES_TO],
        }
        for c in all_control_types()
    ]


# --------------------------------------------------------------------------- #
#  Concrete control types
# --------------------------------------------------------------------------- #
@register
class EDR(ControlType):
    KEY = "edr"
    NAME = "Endpoint Detection & Response"
    ICON = "fa-virus-slash"
    DESCRIPTION = "Detects malicious endpoint behaviour (process chains, LSASS access, ransomware)."
    DEFAULT_SCOPE = "asset"
    ATTACHES_TO = (AssetCategory.ENDPOINT, AssetCategory.SERVER, AssetCategory.IDENTITY)


@register
class SIEM(ControlType):
    KEY = "siem"
    NAME = "SIEM Correlation"
    ICON = "fa-lock"
    DESCRIPTION = "Correlates logs org-wide; broad but higher-latency detection."
    DEFAULT_SCOPE = "global"


@register
class FirewallIDS(ControlType):
    KEY = "firewall_ids"
    NAME = "Firewall / IDS-IPS"
    ICON = "fa-shield-alt"
    DESCRIPTION = "Inspects network flows; can detect/block C2 and known-bad egress."
    DEFAULT_SCOPE = "global"


@register
class Segmentation(ControlType):
    KEY = "segmentation"
    NAME = "Network Segmentation"
    ICON = "fa-network-wired"
    DESCRIPTION = "Restricts cross-zone movement (corp/OT/cloud). Blocks lateral pivots without privilege."
    DEFAULT_SCOPE = "global"


@register
class DLP(ControlType):
    KEY = "dlp"
    NAME = "Data Loss Prevention"
    ICON = "fa-file-shield"
    DESCRIPTION = "Watches sensitive data movement; detects/blocks large or anomalous exfiltration."
    DEFAULT_SCOPE = "asset"
    ATTACHES_TO = (AssetCategory.DATA, AssetCategory.CLOUD)


@register
class MFA(ControlType):
    KEY = "mfa"
    NAME = "Multi-Factor Authentication"
    ICON = "fa-key"
    DESCRIPTION = "Blocks credential reuse/replay except against advanced (Expert) adversaries."
    DEFAULT_SCOPE = "global"


@register
class Backups(ControlType):
    KEY = "backups"
    NAME = "Tested Offline Backups"
    ICON = "fa-database"
    DESCRIPTION = "Reduces ransomware/business impact and recovery time. Not a detector."
    DEFAULT_SCOPE = "global"


@register
class EmailSecurity(ControlType):
    KEY = "email_sec"
    NAME = "Email Security Gateway"
    ICON = "fa-envelope-circle-check"
    DESCRIPTION = "Filters malicious mail; blocks commodity phishing below advanced difficulty."
    DEFAULT_SCOPE = "global"
