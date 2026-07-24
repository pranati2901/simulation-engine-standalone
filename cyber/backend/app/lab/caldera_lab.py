"""Caldera lab backend — drives MITRE Caldera as an adversary emulation layer on top of any lab.

Instead of running individual tool commands, this backend:
1. Connects to a Caldera server (local or remote)
2. Finds abilities matching the requested action's MITRE technique
3. Creates a single-ability adversary profile
4. Launches a Caldera operation against connected agents
5. Polls until complete, collects decoded results

This is a *wrapper* around another LabBackend: it uses Caldera for attack execution
but delegates target management, status, and detection to the underlying lab.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

from .base import CommandResult, LabBackend, LabStatus, LabTarget
from .live_fire import FireSpec, FIRE_BY_ACTION


# Map live-fire action IDs to MITRE technique IDs (for Caldera ability lookup)
ACTION_TO_MITRE: dict[str, str] = {
    "recon.fingerprint": "T1046",
    "intrecon.network": "T1046",
    "access.exposed_service": "T1190",
    "intrecon.identity_graph": "T1087.002",
    "access.valid_creds": "T1078",
    "cred.lsass": "T1003.001",
    "cred.kerberoast": "T1558.003",
    "cred.dcsync": "T1003.006",
    "lateral.move": "T1047",
}


@dataclass
class CalderaLabConfig:
    base_url: str = "http://localhost:8888"
    api_key: str = "ADMIN123"
    agent_group: str = "red"
    timeout_s: float = 120.0
    poll_s: float = 2.0


class CalderaLab(LabBackend):
    """Wraps an existing lab backend, adding Caldera orchestration for supported actions.

    For actions that have a Caldera mapping, runs via Caldera operation.
    For actions without mapping, falls through to the inner lab's direct execution.
    Detection always delegates to the inner lab.
    """

    name = "caldera"

    def __init__(self, inner: LabBackend, config: CalderaLabConfig | None = None):
        self.inner = inner
        self.cfg = config or CalderaLabConfig()
        self._headers = {"KEY": self.cfg.api_key, "Content-Type": "application/json"}

    def _api(self, method: str, path: str, **kwargs) -> dict | list | None:
        if requests is None:
            return None
        url = f"{self.cfg.base_url.rstrip('/')}/api/v2{path}"
        try:
            resp = requests.request(method, url, headers=self._headers, timeout=30, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def _caldera_available(self) -> bool:
        health = self._api("GET", "/health")
        return health is not None

    def _find_ability(self, technique_id: str, platform: str = "windows") -> str | None:
        abilities = self._api("GET", "/abilities")
        if not abilities:
            return None
        for a in abilities:
            if a.get("technique_id") != technique_id:
                continue
            for ex in a.get("executors", []):
                if platform in ex.get("platform", ""):
                    return a["ability_id"]
        return None

    def _run_operation(self, ability_id: str) -> CommandResult:
        """Create adversary + operation, poll until done, return result."""
        ts = int(time.time())
        adv = self._api("POST", "/adversaries", json={
            "name": f"gc-{ts}", "description": "GoalCert auto",
            "atomic_ordering": [ability_id],
        })
        if not adv:
            return CommandResult(False, 1, "", "Failed to create Caldera adversary", 0, "")

        op = self._api("POST", "/operations", json={
            "name": f"gc-op-{ts}",
            "adversary": {"adversary_id": adv["adversary_id"]},
            "planner": {"id": "aaa7c857-37a0-4c4a-85f7-4e9f7f30e31a"},
            "source": {"id": "ed32b9c3-9593-4c33-b0db-e2007315096b"},
            "group": self.cfg.agent_group, "auto_close": True,
            "obfuscator": "plain-text", "jitter": "2/8",
        })
        if not op:
            return CommandResult(False, 1, "", "Failed to create Caldera operation", 0, "")

        op_id = op["id"]
        start = time.time()
        while time.time() - start < self.cfg.timeout_s:
            status = self._api("GET", f"/operations/{op_id}")
            if status and status.get("state") == "finished":
                break
            time.sleep(self.cfg.poll_s)
        else:
            return CommandResult(False, 124, "", f"Caldera operation timed out after {self.cfg.timeout_s}s",
                                int(self.cfg.timeout_s * 1000), f"operation:{op_id}")

        # Collect results
        links = self._api("GET", f"/operations/{op_id}/links") or []
        output_parts = []
        success = False
        for link in links:
            if link.get("status") == -3:  # collected = success
                success = True
                try:
                    raw = self._api("GET", f"/operations/{op_id}/links/{link['id']}/result") or {}
                    decoded = base64.b64decode(raw.get("result", "")).decode("utf-8", errors="replace")
                    output_parts.append(decoded)
                except Exception:
                    output_parts.append("[output decode failed]")

        duration_ms = int((time.time() - start) * 1000)
        return CommandResult(
            success=success, exit_code=0 if success else 1,
            stdout="\n".join(output_parts)[:8000], stderr="",
            duration_ms=duration_ms, command=f"caldera:operation:{op_id}",
        )

    # ---- LabBackend interface (delegates to inner, adds Caldera) ----

    def targets(self) -> list[LabTarget]:
        return self.inner.targets()

    def credentials(self) -> dict:
        return self.inner.credentials()

    def attacker_terminal_url(self) -> str:
        return self.inner.attacker_terminal_url()

    def status(self) -> LabStatus:
        inner_status = self.inner.status()
        caldera_up = self._caldera_available()
        agents = self._api("GET", "/agents") or []
        alive = [a for a in agents if a.get("group") == self.cfg.agent_group]
        inner_status.detail += (
            f" | Caldera: {'connected' if caldera_up else 'offline'}"
            f", {len(alive)} agent(s)"
        )
        inner_status.backend = f"{self.inner.name}+caldera"
        return inner_status

    def up(self) -> CommandResult:
        return self.inner.up()

    def down(self) -> CommandResult:
        return self.inner.down()

    def run_in_attacker(self, command: str, timeout: int = 120) -> CommandResult:
        """Try Caldera first for mapped commands, fall back to inner lab."""
        return self.inner.run_in_attacker(command, timeout)

    def run_in_target(self, target_id: str, command: str, timeout: int = 30) -> CommandResult:
        return self.inner.run_in_target(target_id, command, timeout)

    def run_caldera_action(self, action_id: str) -> CommandResult:
        """Run an action via Caldera operation instead of direct tool execution."""
        mitre_id = ACTION_TO_MITRE.get(action_id)
        if not mitre_id:
            return CommandResult(False, 1, "", f"No MITRE mapping for action {action_id}", 0, "")

        if not self._caldera_available():
            return CommandResult(False, 1, "", "Caldera server not reachable", 0, "")

        ability_id = self._find_ability(mitre_id)
        if not ability_id:
            return CommandResult(False, 1, "", f"No Caldera ability for {mitre_id}", 0, "")

        return self._run_operation(ability_id)
