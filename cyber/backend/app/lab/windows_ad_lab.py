"""Windows Active Directory lab backend (Phase 2) — real domain attacks + real detection.

Unlike the Docker range, the Windows-AD lab is a real Windows Server Domain Controller (provisioned
by infrastructure/Vagrantfile, or any reachable AD on the configured host-only network). It implements
the SAME `LabBackend` interface as the Docker lab, so the engine and the whole live-fire path are
unchanged:

  - `run_in_attacker(cmd)` runs the attack tool (Impacket) **on the host** via subprocess. The host can
    reach the VirtualBox/VMware host-only network (192.168.56.0/24) where the DC lives — which a Docker
    container generally cannot. So Phase-2 attacks run host-native (pip install impacket).
  - `run_in_target(dc, ps)` runs PowerShell **on the DC over WinRM** — used to read the Windows Security
    / Sysmon event log for real detection evidence.
  - `up()` / `down()` drive Vagrant if a Vagrant directory is configured.

Credentials come from settings (defaults match the Vagrantfile: GOALCERT\\vagrant). `credentials()`
feeds the Impacket command templates in live_fire.py.
"""
from __future__ import annotations

import shutil
import subprocess
import time

from .base import CommandResult, LabBackend, LabStatus, LabTarget


class WindowsAdLab(LabBackend):
    """A real Active-Directory range: host-native Impacket + WinRM detection on the DC."""

    name = "windows_ad"

    def __init__(
        self,
        dc_host: str,
        domain: str = "GOALCERT",
        user: str = "vagrant",
        password: str = "vagrant",
        winrm_user: str | None = None,
        winrm_password: str | None = None,
        winrm_port: int = 5985,
        vagrant_dir: str = "",
    ) -> None:
        self.dc_host = dc_host
        self.domain = domain
        self.user = user
        self.password = password
        self.winrm_user = winrm_user or user
        self.winrm_password = winrm_password if winrm_password is not None else password
        self.winrm_port = winrm_port
        self.vagrant_dir = vagrant_dir
        self._targets = [
            LabTarget(
                id="dc01", name="Domain Controller (goalcert.local)", host=dc_host, os="windows",
                role="dc", services=("smb", "ldap", "kerberos", "winrm"), container="dc01",
            ),
        ]

    # ---- LabBackend interface ------------------------------------------------
    def targets(self) -> list[LabTarget]:
        return list(self._targets)

    def credentials(self) -> dict:
        return {"domain": self.domain, "user": self.user, "password": self.password}

    def run_in_attacker(self, command: str, timeout: int = 120) -> CommandResult:
        """Run the attack tool on the HOST (it can reach the host-only AD network)."""
        start = time.time()
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return CommandResult(False, 124, "", f"timed out after {timeout}s", timeout * 1000, command)
        except FileNotFoundError:
            return CommandResult(False, 127, "", "tool not found on host (pip install impacket)", 0, command)
        dur = int((time.time() - start) * 1000)
        # Impacket prints a friendly error and returns 0 on auth failure, so also treat empty output as failure.
        success = proc.returncode == 0 and len((proc.stdout or "").strip()) > 0
        return CommandResult(success, proc.returncode, (proc.stdout or "")[:8000],
                             (proc.stderr or "")[:2000], dur, command)

    def run_in_target(self, target_id: str, command: str, timeout: int = 30) -> CommandResult:
        """Run PowerShell on the DC over WinRM (used for event-log detection)."""
        try:
            import winrm  # lazy: only needed when detection runs and WinRM is configured
        except ImportError:
            return CommandResult(False, 1, "", "pywinrm not installed (pip install pywinrm)", 0, command)
        try:
            session = winrm.Session(
                f"http://{self.dc_host}:{self.winrm_port}/wsman",
                auth=(self.winrm_user, self.winrm_password), transport="ntlm",
            )
            r = session.run_ps(command)
            ok = r.status_code == 0
            return CommandResult(ok, r.status_code, r.std_out.decode("utf-8", "replace")[:8000],
                                 r.std_err.decode("utf-8", "replace")[:2000], 0, command)
        except Exception as exc:  # WinRM unreachable / not configured — detection just stays off
            return CommandResult(False, 1, "", f"winrm error: {exc}"[:500], 0, command)

    def status(self) -> LabStatus:
        impacket_ok = shutil.which("impacket-secretsdump") is not None
        # WinRM reachability is a quick TCP-ish check via a trivial PS command.
        winrm_ok = False
        detail_parts = []
        if not impacket_ok:
            detail_parts.append("impacket not on host PATH (pip install impacket)")
        probe = self.run_in_target("dc01", "$true", timeout=8)
        winrm_ok = probe.success and "True" in probe.stdout
        up = winrm_ok  # the DC answering WinRM is our 'lab is up' signal
        if not winrm_ok:
            detail_parts.append("DC not reachable over WinRM "
                                "(start the VM: vagrant up dc01 — see docs/LIVE-FIRE-AD-SETUP.md)")
        if up and impacket_ok:
            detail_parts = [f"AD lab up — DC {self.dc_host} reachable, attacker tooled"]
        return LabStatus(
            backend=self.name, available=impacket_ok, up=up,
            attacker_ready=impacket_ok and winrm_ok, targets=list(self._targets),
            containers=[{"name": "dc01", "running": winrm_ok}],
            detail="; ".join(detail_parts) or "AD lab ready",
        )

    # ---- provisioning (optional, via Vagrant) --------------------------------
    def _vagrant(self, *args: str, timeout: int = 1800) -> CommandResult:
        if not self.vagrant_dir or shutil.which("vagrant") is None:
            return CommandResult(False, 127, "", "vagrant not available / vagrant_dir not set", 0, "vagrant")
        start = time.time()
        try:
            proc = subprocess.run(["vagrant", *args], cwd=self.vagrant_dir,
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return CommandResult(False, 124, "", f"vagrant timed out after {timeout}s", timeout * 1000, "vagrant")
        return CommandResult(proc.returncode == 0, proc.returncode, (proc.stdout or "")[:8000],
                             (proc.stderr or "")[:2000], int((time.time() - start) * 1000), "vagrant " + " ".join(args))

    def up(self) -> CommandResult:
        return self._vagrant("up", "dc01")

    def down(self) -> CommandResult:
        return self._vagrant("halt", "dc01")
