"""Session lab pool — per-session isolated ranges (the multi-tenant core of Phase 3).

Each live session can get its OWN range: an isolated Docker compose project (`gc-<session>`) with its
own network and its own random host ports, so concurrent sessions/teams can't see or touch each other.
This is the local, verifiable equivalent of the per-user environments TryHackMe/HTB spin up — and the
same `SessionLabPool` interface is what a cloud/Proxmox backend slots into for the hosted product.

A concurrency cap keeps a laptop demo sane. Provisioning is blocking (docker compose up) — call it from
an endpoint/thread, not the event loop.
"""
from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path

from app.core.settings import settings

from .docker_lab import DockerComposeLab


def _default_compose_file() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    return str(repo_root / "infrastructure" / "docker-compose.lab.yml")


class SessionLabPool:
    """Provision and track one isolated Docker range per session."""

    def __init__(self, compose_file: str, max_concurrent: int = 3):
        self.compose_file = compose_file
        self.max_concurrent = max_concurrent
        self._labs: dict[str, DockerComposeLab] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _project(session_id: str) -> str:
        # docker project names: lowercase alphanumeric / hyphen / underscore
        safe = "".join(c for c in session_id.lower() if c.isalnum() or c in "-_")[:20]
        return f"gc-{safe}"

    def provision(self, session_id: str) -> tuple[DockerComposeLab | None, str]:
        """Create (if needed) and start this session's isolated range. Blocking."""
        with self._lock:
            lab = self._labs.get(session_id)
            if lab is None:
                if len(self._labs) >= self.max_concurrent:
                    return None, f"lab pool at capacity ({self.max_concurrent} concurrent ranges)"
                lab = DockerComposeLab(self.compose_file, project=self._project(session_id))
                self._labs[session_id] = lab
        result = lab.up()
        if not result.success:
            return lab, result.output or "failed to start range"
        return lab, ""

    def get(self, session_id: str) -> DockerComposeLab | None:
        return self._labs.get(session_id)

    def teardown(self, session_id: str) -> bool:
        with self._lock:
            lab = self._labs.pop(session_id, None)
        if lab is None:
            return False
        lab.down()
        return True

    def active(self) -> list[str]:
        return list(self._labs.keys())


@lru_cache(maxsize=1)
def get_pool() -> SessionLabPool:
    return SessionLabPool(
        compose_file=settings.lab_compose_file or _default_compose_file(),
        max_concurrent=settings.lab_pool_max,
    )
