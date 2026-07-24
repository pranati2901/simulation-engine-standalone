"""Lab backend interface + data models — the seam between GoalCert and real infrastructure.

`LabBackend` is deliberately small and provider-agnostic so the same engine code runs a Docker
range on a laptop today and a Proxmox/cloud range tomorrow. Concrete backends implement it
(`docker_lab.DockerComposeLab` now; `ProxmoxLab` / `CloudLab` are future drop-ins).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
#  Data models
# --------------------------------------------------------------------------- #
@dataclass
class LabTarget:
    """A reachable machine in the lab the attacker can act against."""
    id: str                       # logical id, e.g. "target-web"
    name: str                     # display name
    host: str                     # name/IP reachable from the attacker box (e.g. docker DNS alias)
    os: str = "linux"             # "linux" | "windows"
    role: str = "host"            # "web" | "fileserver" | "dc" | "workstation" | ...
    services: tuple[str, ...] = ()  # ("http", "smb", "ssh", ...)
    container: str = ""           # backend-specific handle (container name) for log/detection access
    scenario: str = ""            # the guided scenario this target is the "goal" web app for (if any)
    http_port: int = 0            # the in-container http port to map to a browsable URL (0 = none)

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "host": self.host, "os": self.os,
                "role": self.role, "services": list(self.services), "scenario": self.scenario}


@dataclass
class CommandResult:
    """Outcome of running a command in the attacker (or a target) box."""
    success: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    command: str = ""

    @property
    def output(self) -> str:
        return self.stdout or self.stderr

    def public(self) -> dict:
        return {"success": self.success, "exit_code": self.exit_code,
                "stdout": self.stdout, "stderr": self.stderr,
                "duration_ms": self.duration_ms, "command": self.command}


@dataclass
class LabStatus:
    """Current state of the lab — drives the UI's 'real lab' indicator."""
    backend: str                  # "docker" | "proxmox" | "cloud" | "none"
    available: bool               # backend tooling is installed/reachable (e.g. docker present)
    up: bool                      # the lab is provisioned and running
    attacker_ready: bool = False  # the attacker box is reachable + tooled
    targets: list[LabTarget] = field(default_factory=list)
    containers: list[dict] = field(default_factory=list)
    detail: str = ""
    terminal_url: str = ""        # browser shell into the attacker box, if the backend offers one
    target_urls: dict[str, str] = field(default_factory=dict)  # target id -> browsable http URL (if up)

    def public(self) -> dict:
        return {"backend": self.backend, "available": self.available, "up": self.up,
                "attacker_ready": self.attacker_ready,
                "targets": [t.public() for t in self.targets],
                "containers": self.containers, "detail": self.detail,
                "terminal_url": self.terminal_url, "target_urls": self.target_urls}


# --------------------------------------------------------------------------- #
#  The backend interface
# --------------------------------------------------------------------------- #
class LabBackend(abc.ABC):
    """A provider that can stand up a range and run commands in it."""

    name: str = "abstract"

    @abc.abstractmethod
    def status(self) -> LabStatus:
        """Inspect the lab (is the tooling present? is it up? which targets exist?)."""
        ...

    @abc.abstractmethod
    def up(self) -> CommandResult:
        """Provision/start the lab."""
        ...

    @abc.abstractmethod
    def down(self) -> CommandResult:
        """Tear the lab down."""
        ...

    def reset(self) -> CommandResult:
        """Default reset = down then up. Backends may override for snapshot-based reset."""
        self.down()
        return self.up()

    @abc.abstractmethod
    def targets(self) -> list[LabTarget]:
        """The lab's target inventory (independent of whether it is currently up)."""
        ...

    def credentials(self) -> dict:
        """The attacker's working credentials against this lab (domain/user/password).

        Default is empty (the Docker range's tools use anonymous/baked-in creds). The Windows-AD
        backend overrides this with the harvested domain credentials the attack chain uses.
        """
        return {"domain": "", "user": "", "password": ""}

    def attacker_terminal_url(self) -> str:
        """A browser shell into the attacker box, if this backend offers one (else '')."""
        return ""

    @abc.abstractmethod
    def run_in_attacker(self, command: str, timeout: int = 120) -> CommandResult:
        """Run a command inside the attacker box (Kali). This is where real tools execute."""
        ...

    @abc.abstractmethod
    def run_in_target(self, target_id: str, command: str, timeout: int = 30) -> CommandResult:
        """Run a command inside a target (used for log-based detection evidence)."""
        ...
