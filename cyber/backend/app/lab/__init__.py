"""Real-infrastructure lab layer — turns the tabletop simulation into a live-fire range.

This package is the bridge between GoalCert's role-based live sessions and a *real*
attack/defence lab (Docker today; Proxmox / cloud later behind the same interface).

Pieces:
- `base`       — the cloud-ready `LabBackend` ABC + data models (LabStatus, LabTarget, CommandResult)
- `docker_lab` — `DockerComposeLab`: a free, local, single-host range (Kali attacker + vulnerable targets)
- `tools`      — the tool registry (1 integrated free tool per function + placeholders to grow into)
- `live_fire`  — maps a live Red action to a real tool command + real log-based detection
- `manager`    — process-wide singleton selecting the configured backend

Everything here is OPTIONAL and OFF by default: a live session only fires real tools when the host
arms live-fire AND the lab is up. Otherwise the existing deterministic simulation is unchanged.
"""
from .base import CommandResult, LabBackend, LabStatus, LabTarget
from .manager import get_lab, lab_status

__all__ = [
    "CommandResult", "LabBackend", "LabStatus", "LabTarget",
    "get_lab", "lab_status",
]
