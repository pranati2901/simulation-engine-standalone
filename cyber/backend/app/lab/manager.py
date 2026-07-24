"""Process-wide lab singleton — selects and caches the configured backend.

Backend is chosen by `settings.lab_backend` ("docker" today). The compose file is resolved relative
to the repo root unless overridden. Swapping in a Proxmox/cloud backend later is a one-line change
here; nothing else in the app needs to know which backend is active.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.settings import settings

from .base import LabBackend, LabStatus
from .docker_lab import DockerComposeLab
from .windows_ad_lab import WindowsAdLab


def _infra_dir() -> Path:
    # backend/app/lab/manager.py -> parents[3] == repo root
    return Path(__file__).resolve().parents[3] / "infrastructure"


def _default_compose_file() -> str:
    return str(_infra_dir() / "docker-compose.lab.yml")


@lru_cache(maxsize=1)
def get_lab() -> LabBackend:
    backend = (settings.lab_backend or "docker").lower()
    if backend == "docker":
        return DockerComposeLab(compose_file=settings.lab_compose_file or _default_compose_file())
    if backend in ("windows_ad", "ad", "windows"):
        return WindowsAdLab(
            dc_host=settings.ad_dc_host, domain=settings.ad_domain,
            user=settings.ad_user, password=settings.ad_password,
            winrm_user=settings.ad_winrm_user or None,
            winrm_password=settings.ad_winrm_password or None,
            vagrant_dir=settings.ad_vagrant_dir or str(_infra_dir()),
        )
    # Future: "proxmox" / "cloud" backends plug in here behind the same interface.
    raise ValueError(f"unknown lab backend: {backend!r}")


def lab_status() -> LabStatus:
    return get_lab().status()
