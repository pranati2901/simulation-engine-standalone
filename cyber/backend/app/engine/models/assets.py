"""Asset model framework + registry + concrete asset types.

Each asset *type* describes how that kind of asset behaves: its metadata, default
properties, and the characteristic telemetry it emits when a technique effect hits it
(``react``). This is the "how the asset works" layer. Asset *instances* live in the World.
"""
from __future__ import annotations

from ..enums import AssetCategory, Severity
from ..events import Emit
from ..world import AssetInstance, World


class AssetType:
    """Base class for an asset behaviour model. Subclass + @register."""

    KEY: str = ""
    NAME: str = ""
    CATEGORY: AssetCategory = AssetCategory.SERVER
    ICON: str = "fa-server"
    DESCRIPTION: str = ""
    DEFAULT_ZONE: str = "corp"
    DEFAULT_CRITICALITY: int = 3
    DEFAULT_DATA_SENSITIVITY: int = 1
    SUPPORTED_CONTROLS: tuple[str, ...] = ()

    @classmethod
    def default_props(cls) -> dict:
        return {}

    @classmethod
    def react(cls, asset: AssetInstance, effect_kind: str, world: World) -> list[Emit]:
        """Telemetry this asset emits in reaction to an applied technique effect."""
        return []


_REGISTRY: dict[str, type[AssetType]] = {}


def register(cls: type[AssetType]) -> type[AssetType]:
    if not cls.KEY:
        raise ValueError(f"AssetType {cls.__name__} missing KEY")
    _REGISTRY[cls.KEY] = cls
    return cls


def get_asset_type(key: str) -> type[AssetType]:
    if key not in _REGISTRY:
        raise KeyError(f"Unknown asset type: {key}")
    return _REGISTRY[key]


def all_asset_types() -> list[type[AssetType]]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def catalog() -> list[dict]:
    """Serialisable catalog metadata for the API / asset-selection UI."""
    return [
        {
            "key": t.KEY,
            "name": t.NAME,
            "category": t.CATEGORY.value,
            "icon": t.ICON,
            "description": t.DESCRIPTION,
            "default_zone": t.DEFAULT_ZONE,
            "default_criticality": t.DEFAULT_CRITICALITY,
            "default_data_sensitivity": t.DEFAULT_DATA_SENSITIVITY,
            "supported_controls": list(t.SUPPORTED_CONTROLS),
        }
        for t in all_asset_types()
    ]


# --------------------------------------------------------------------------- #
#  Concrete asset types
# --------------------------------------------------------------------------- #
@register
class Endpoint(AssetType):
    KEY = "endpoint"
    NAME = "Workstation / Endpoint"
    CATEGORY = AssetCategory.ENDPOINT
    ICON = "fa-desktop"
    DESCRIPTION = "User workstation. Phishing entry point; holds cached creds and runs processes."
    DEFAULT_ZONE = "corp"
    DEFAULT_CRITICALITY = 2
    SUPPORTED_CONTROLS = ("edr", "email_sec", "mfa")

    @classmethod
    def default_props(cls) -> dict:
        # user_susceptibility 1..5 — higher means likelier to fall for phishing
        return {"user_susceptibility": 3, "cached_creds": True}

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "compromise":
            return [
                Emit(channel="edr", severity=Severity.HIGH,
                     text=f"{asset.name}: cmd.exe -> powershell.exe -enc (suspicious chain)"),
                Emit(channel="net", severity=Severity.MEDIUM,
                     text=f"{asset.name}: outbound TLS beacon to 185.220.101.45:443 (C2)"),
            ]
        if effect_kind == "credential_dump":
            return [Emit(channel="edr", severity=Severity.HIGH,
                         text=f"{asset.name}: LSASS memory access by non-system process")]
        if effect_kind == "lateral_in":
            return [Emit(channel="auth", severity=Severity.MEDIUM,
                         text=f"{asset.name}: remote logon (type 3) from internal host")]
        if effect_kind == "encrypt":
            return [Emit(channel="edr", severity=Severity.CRITICAL,
                         text=f"{asset.name}: mass file rename *.locked — ransomware behaviour")]
        return []


@register
class GenericServer(AssetType):
    KEY = "server"
    NAME = "Application / Historian Server"
    CATEGORY = AssetCategory.SERVER
    ICON = "fa-server"
    DESCRIPTION = "Internal server (app/historian). Common lateral-movement and pivot target."
    DEFAULT_CRITICALITY = 3

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "lateral_in":
            return [Emit(channel="auth", severity=Severity.MEDIUM,
                         text=f"{asset.name}: new service created via SMB (remote exec)")]
        if effect_kind == "compromise":
            return [Emit(channel="net", severity=Severity.MEDIUM,
                         text=f"{asset.name}: anomalous east-west traffic spike")]
        return []


@register
class DomainController(AssetType):
    KEY = "domain_controller"
    NAME = "Active Directory Domain Controller"
    CATEGORY = AssetCategory.IDENTITY
    ICON = "fa-user-shield"
    DESCRIPTION = "AD DC. Issues Kerberos tickets; target for Kerberoasting and DA compromise."
    DEFAULT_ZONE = "corp"
    DEFAULT_CRITICALITY = 5

    @classmethod
    def default_props(cls) -> dict:
        return {"service_accounts": 8}

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "kerberoast":
            return [Emit(channel="auth", severity=Severity.HIGH,
                         text=f"{asset.name}: bulk Kerberos TGS requests (RC4) for service accounts")]
        if effect_kind == "compromise":
            return [Emit(channel="auth", severity=Severity.CRITICAL,
                         text=f"{asset.name}: DCSync / replication request from non-DC host")]
        return []


@register
class EmailServer(AssetType):
    KEY = "email_server"
    NAME = "Email Server"
    CATEGORY = AssetCategory.SERVER
    ICON = "fa-envelope"
    DESCRIPTION = "Mail gateway. Delivery path for phishing lures."
    DEFAULT_CRITICALITY = 3

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "phish_delivered":
            return [Emit(channel="email", severity=Severity.MEDIUM,
                         text=f"{asset.name}: inbound mail w/ macro attachment from look-alike supplier domain")]
        return []


@register
class FileShare(AssetType):
    KEY = "file_share"
    NAME = "File Server / Share"
    CATEGORY = AssetCategory.DATA
    ICON = "fa-folder-open"
    DESCRIPTION = "Sensitive document repository. Target for collection and exfiltration."
    DEFAULT_CRITICALITY = 4
    DEFAULT_DATA_SENSITIVITY = 4
    SUPPORTED_CONTROLS = ("dlp",)

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "collection":
            return [Emit(channel="net", severity=Severity.MEDIUM,
                         text=f"{asset.name}: large recursive read + staging to archive")]
        if effect_kind == "exfiltration":
            return [Emit(channel="net", severity=Severity.HIGH,
                         text=f"{asset.name}: 4.2GB outbound to external cloud storage")]
        return []


@register
class ERP(AssetType):
    KEY = "erp"
    NAME = "ERP System"
    CATEGORY = AssetCategory.SERVER
    ICON = "fa-cubes"
    DESCRIPTION = "Enterprise resource planning. Business-critical; impacts operations if down."
    DEFAULT_CRITICALITY = 5
    DEFAULT_DATA_SENSITIVITY = 4

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "encrypt":
            return [Emit(channel="sys", severity=Severity.CRITICAL,
                         text=f"{asset.name}: database files encrypted — service unavailable")]
        return []


@register
class MES(AssetType):
    KEY = "mes"
    NAME = "Manufacturing Execution System"
    CATEGORY = AssetCategory.OT
    ICON = "fa-industry"
    DESCRIPTION = "IT/OT boundary system bridging corporate and plant-floor networks."
    DEFAULT_ZONE = "ot_dmz"
    DEFAULT_CRITICALITY = 5

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "lateral_in":
            return [Emit(channel="ot", severity=Severity.HIGH,
                         text=f"{asset.name}: IT->OT boundary crossing to historian/MES")]
        return []


@register
class DigitalTwin(AssetType):
    KEY = "digital_twin"
    NAME = "Digital Twin Platform"
    CATEGORY = AssetCategory.OT
    ICON = "fa-clone"
    DESCRIPTION = "Simulation/mirror of plant processes; reconnaissance value for OT attacks."
    DEFAULT_ZONE = "ot_dmz"
    DEFAULT_CRITICALITY = 3


@register
class CloudTenant(AssetType):
    KEY = "cloud"
    NAME = "Cloud Infrastructure"
    CATEGORY = AssetCategory.CLOUD
    ICON = "fa-cloud"
    DESCRIPTION = "Cloud tenant (IAM, storage, compute). Exfil destination and persistence surface."
    DEFAULT_ZONE = "cloud"
    DEFAULT_CRITICALITY = 4
    DEFAULT_DATA_SENSITIVITY = 3

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "persistence":
            return [Emit(channel="sys", severity=Severity.HIGH,
                         text=f"{asset.name}: new IAM principal + access key created from unknown IP")]
        if effect_kind == "exfiltration":
            return [Emit(channel="net", severity=Severity.HIGH,
                         text=f"{asset.name}: unusual write volume to external storage bucket")]
        return []


@register
class OTPlc(AssetType):
    KEY = "ot_plc"
    NAME = "OT PLC / Controller"
    CATEGORY = AssetCategory.OT
    ICON = "fa-microchip"
    DESCRIPTION = "Programmable logic controller driving a physical process. Safety-critical."
    DEFAULT_ZONE = "ot"
    DEFAULT_CRITICALITY = 5

    @classmethod
    def default_props(cls) -> dict:
        return {"safety_interlocks": True, "setpoint": "nominal"}

    @classmethod
    def react(cls, asset, effect_kind, world):
        if effect_kind == "ot_modify":
            return [
                Emit(channel="ot", severity=Severity.CRITICAL,
                     text=f"{asset.name}: unauthorized setpoint change — process values drifting"),
                Emit(channel="ot", severity=Severity.CRITICAL,
                     text=f"{asset.name}: PLC program write outside maintenance window"),
            ]
        return []


# ---- security / infra assets (also rendered as map nodes) ------------------ #
@register
class SiemPlatform(AssetType):
    KEY = "siem_platform"
    NAME = "SOC SIEM Platform"
    CATEGORY = AssetCategory.SECURITY
    ICON = "fa-lock"
    DESCRIPTION = "Central log correlation. Hosts the 'siem' detection control when present."
    DEFAULT_ZONE = "soc"
    DEFAULT_CRITICALITY = 4


@register
class EdrPlatform(AssetType):
    KEY = "edr_platform"
    NAME = "EDR Platform"
    CATEGORY = AssetCategory.SECURITY
    ICON = "fa-virus-slash"
    DESCRIPTION = "Endpoint detection & response console. Hosts the 'edr' control when present."
    DEFAULT_ZONE = "soc"
    DEFAULT_CRITICALITY = 4


@register
class FirewallAppliance(AssetType):
    KEY = "firewall"
    NAME = "Firewall / IDS-IPS"
    CATEGORY = AssetCategory.NETWORK
    ICON = "fa-shield-alt"
    DESCRIPTION = "Perimeter & segmentation enforcement. Hosts firewall_ids / segmentation controls."
    DEFAULT_ZONE = "perimeter"
    DEFAULT_CRITICALITY = 4


@register
class VulnMgmt(AssetType):
    KEY = "vuln_mgmt"
    NAME = "Vulnerability Management"
    CATEGORY = AssetCategory.SECURITY
    ICON = "fa-clipboard-check"
    DESCRIPTION = "Vulnerability scanner/inventory. Informs exposure but is not a live detector."
    DEFAULT_ZONE = "soc"
    DEFAULT_CRITICALITY = 2
