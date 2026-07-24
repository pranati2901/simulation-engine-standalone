"""Docker Compose lab backend — a free, local cyber range (one shared, or one per session).

Stands up an attacker box (Kali: nmap / NetExec / Impacket / nikto + a ttyd browser shell) and a few
intentionally vulnerable targets on an isolated docker network. Real tools run via
`docker compose exec attacker`; detection evidence is read from the targets' own service logs.

Project-aware: each instance drives `docker compose -p <project>`, so the same compose file backs ONE
shared range (`project="gclab"`) or many isolated ones (`project="gc-<session>"`, via SessionLabPool).
Each project gets its own network and its own random host ports.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time

from .base import CommandResult, LabBackend, LabStatus, LabTarget

ATTACKER_SERVICE = "attacker"
TTYD_PORT = 7681

# Fixed topology of the range (service names == DNS names within the compose network).
#  - target-web / target-files: the generic DVWA + Samba boxes (live-fire demo).
#  - target-w1 / target-r5 / target-c5: the per-scenario CUSTOM vulnerable web apps that are the
#    "goal" of each Library hack-lab mission (hospital portal / corporate webmail / admin console).
LAB_TARGETS: list[LabTarget] = [
    LabTarget(id="target-web", name="DVWA Web Server", host="target-web", os="linux", role="web",
              services=("http",), container="target-web", http_port=80),
    LabTarget(id="target-files", name="File Server (SMB)", host="target-files", os="linux",
              role="fileserver", services=("smb",), container="target-files"),
    LabTarget(id="target-w1", name="Mercy Health Patient Portal", host="target-w1", os="linux",
              role="web", services=("http",), container="target-w1",
              scenario="scn-wannacry-w1", http_port=80),
    LabTarget(id="target-r5", name="MediumCorp Webmail", host="target-r5", os="linux",
              role="web", services=("http",), container="target-r5",
              scenario="scn-r5-phishing", http_port=80),
    LabTarget(id="target-c5", name="GlobalTech IT Admin Console", host="target-c5", os="linux",
              role="web", services=("http",), container="target-c5",
              scenario="scn-c5-edr", http_port=80),
]


class DockerComposeLab(LabBackend):
    """Drive a range via `docker compose -p <project>` + `docker compose exec`."""

    name = "docker"

    def __init__(self, compose_file: str, project: str = "gclab"):
        self.compose_file = compose_file
        self.project = project

    # ---- low-level helpers ---------------------------------------------------
    @staticmethod
    def _docker_available() -> bool:
        return shutil.which("docker") is not None

    @staticmethod
    def _run(args: list[str], timeout: int = 120) -> CommandResult:
        start = time.time()
        cmd_str = " ".join(args)
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            return CommandResult(False, 127, "", "docker not found in PATH", 0, cmd_str)
        except subprocess.TimeoutExpired:
            return CommandResult(False, 124, "", f"timed out after {timeout}s", timeout * 1000, cmd_str)
        dur = int((time.time() - start) * 1000)
        return CommandResult(
            success=proc.returncode == 0, exit_code=proc.returncode,
            stdout=(proc.stdout or "")[:8000], stderr=(proc.stderr or "")[:2000],
            duration_ms=dur, command=cmd_str,
        )

    def _compose(self, *args: str, timeout: int = 300) -> CommandResult:
        return self._run(["docker", "compose", "-f", self.compose_file, "-p", self.project, *args],
                         timeout=timeout)

    def _exec(self, service: str, command: str, timeout: int) -> CommandResult:
        return self._compose("exec", "-T", service, "sh", "-lc", command, timeout=timeout)

    def _running_services(self) -> set[str]:
        """Service names currently running in this project (robust across compose versions)."""
        r = self._run(["docker", "ps",
                       "--filter", f"label=com.docker.compose.project={self.project}",
                       "--format", "{{.Label \"com.docker.compose.service\"}}"], timeout=15)
        return set(filter(None, (r.stdout or "").splitlines()))

    def _host_port(self, service: str, container_port: int) -> str:
        """Resolve the random host port Docker mapped for a service -> http URL (or '')."""
        r = self._compose("port", service, str(container_port), timeout=15)
        line = (r.stdout or "").strip().splitlines()[0] if r.stdout else ""
        if ":" in line:
            return f"http://localhost:{line.rsplit(':', 1)[1]}"
        return ""

    # ---- LabBackend interface ------------------------------------------------
    def targets(self) -> list[LabTarget]:
        return list(LAB_TARGETS)

    def attacker_terminal_url(self) -> str:
        return self._host_port(ATTACKER_SERVICE, TTYD_PORT) if self._docker_available() else ""

    def status(self) -> LabStatus:
        if not self._docker_available():
            return LabStatus(backend=self.name, available=False, up=False, targets=list(LAB_TARGETS),
                             detail="Docker is not installed / not in PATH. Install Docker Desktop.")
        running = self._running_services()
        up = ATTACKER_SERVICE in running
        attacker_ready = False
        terminal_url = ""
        target_urls: dict[str, str] = {}
        if up:
            chk = self.run_in_attacker("command -v nmap >/dev/null && echo ok", timeout=15)
            attacker_ready = "ok" in chk.stdout
            terminal_url = self.attacker_terminal_url()
            # browsable "View app" URL for every running http target (the per-scenario DVWAs)
            for t in LAB_TARGETS:
                if t.http_port and t.id in running:
                    url = self._host_port(t.id, t.http_port)
                    if url:
                        target_urls[t.id] = url
        containers = [{"name": s, "running": s in running}
                      for s in [ATTACKER_SERVICE, *[t.id for t in LAB_TARGETS]]]
        detail = (f"Range '{self.project}' up." if up else
                  f"Range '{self.project}' not running. Start it from the Live-fire panel or "
                  f"docker compose -f infrastructure/docker-compose.lab.yml -p {self.project} up -d")
        return LabStatus(backend=self.name, available=True, up=up, attacker_ready=attacker_ready,
                         targets=list(LAB_TARGETS), containers=containers, detail=detail,
                         terminal_url=terminal_url, target_urls=target_urls)

    def up(self) -> CommandResult:
        if not self._docker_available():
            return CommandResult(False, 127, "", "Docker is not installed.", 0, "docker compose up")
        return self._compose("up", "-d", timeout=600)

    def down(self) -> CommandResult:
        if not self._docker_available():
            return CommandResult(False, 127, "", "Docker is not installed.", 0, "docker compose down")
        return self._compose("down", "-v", timeout=120)

    def run_in_attacker(self, command: str, timeout: int = 120) -> CommandResult:
        return self._exec(ATTACKER_SERVICE, command, timeout)

    def run_in_target(self, target_id: str, command: str, timeout: int = 30) -> CommandResult:
        if target_id not in {t.id for t in LAB_TARGETS}:
            return CommandResult(False, 1, "", f"unknown lab target: {target_id}", 0, command)
        return self._exec(target_id, command, timeout)
