"""Tool registry — what real tooling GoalCert can drive, per function and per team.

Design goals (set by the product owner):
- **Minimal but convincing**: exactly one *integrated* free/open-source tool per important function.
- **Room to grow**: every other function is present as a `planned` placeholder (greyed in the UI),
  so the catalog already shows the full purple-team surface we'll fill in.
- **Reserved provider slot**: `provided` entries are the premium/"GoalCert-managed" tools we keep a
  placeholder for but do NOT integrate yet.

`status`:
  - "integrated" — wired to live-fire right now (see live_fire.py)
  - "planned"    — free/OSS, on the roadmap, not wired yet
  - "provided"   — reserved slot for GoalCert-provided/premium tooling (not integrated)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    function: str               # the capability it provides
    team: str                   # "red" | "blue" | "soc"
    status: str                 # "integrated" | "planned" | "provided"
    license: str = "open-source"
    runner: str = ""            # how it executes (e.g. "kali-attacker", "target-logs")
    backs: tuple[str, ...] = () # live action ids / mitre techniques it supports
    homepage: str = ""
    note: str = ""

    def public(self) -> dict:
        return {
            "id": self.id, "name": self.name, "function": self.function, "team": self.team,
            "status": self.status, "license": self.license, "runner": self.runner,
            "backs": list(self.backs), "homepage": self.homepage, "note": self.note,
        }


TOOLS: list[Tool] = [
    # ---- RED: integrated (1 free tool per function) ----------------------------
    Tool("nmap", "Nmap", "Network recon & service discovery", "red", "integrated",
         runner="kali-attacker", backs=("recon.fingerprint", "intrecon.network"),
         homepage="https://nmap.org", note="Active service fingerprinting + host sweep."),
    Tool("netexec", "NetExec (nxc)", "SMB / AD enumeration & credential testing", "red", "integrated",
         runner="kali-attacker", backs=("intrecon.identity_graph", "access.valid_creds"),
         homepage="https://www.netexec.wiki", note="Successor to CrackMapExec."),
    Tool("nikto", "Nikto", "Web server vulnerability scanning", "red", "integrated",
         runner="kali-attacker", backs=("access.exposed_service",),
         homepage="https://github.com/sullo/nikto", note="Finds exposed web issues on the target."),
    Tool("impacket", "Impacket", "Active Directory credential attacks", "red", "integrated",
         runner="kali-attacker", backs=("cred.lsass", "cred.kerberoast", "cred.dcsync", "lateral.move"),
         homepage="https://github.com/fortra/impacket",
         note="secretsdump / GetUserSPNs / wmiexec — requires the Windows-AD lab (Phase 2)."),

    # ---- SOC/BLUE: integrated --------------------------------------------------
    Tool("target-logs", "Live Log Detection", "Detection from target service logs", "soc", "integrated",
         runner="target-logs", backs=("*",),
         note="Reads the targets' real service logs to confirm attacks — light, no SIEM required."),

    # ---- RED: planned (free/OSS, room to grow) ---------------------------------
    Tool("metasploit", "Metasploit Framework", "Exploitation & post-exploitation", "red", "planned",
         runner="kali-attacker", homepage="https://www.metasploit.com"),
    Tool("bloodhound", "BloodHound CE", "AD attack-path mapping", "red", "planned",
         homepage="https://github.com/SpecterOps/BloodHound"),
    Tool("hydra", "Hydra", "Online password brute-forcing", "red", "planned",
         runner="kali-attacker", homepage="https://github.com/vanhauser-thc/thc-hydra"),
    Tool("caldera", "MITRE Caldera", "Automated adversary emulation", "red", "planned",
         homepage="https://caldera.mitre.org", note="Bridge already scaffolded (engine/bridge/caldera.py)."),
    Tool("atomic-red-team", "Atomic Red Team", "Technique validation (BAS)", "red", "planned",
         homepage="https://github.com/redcanaryco/atomic-red-team"),

    # ---- SOC/BLUE: planned -----------------------------------------------------
    Tool("wazuh", "Wazuh", "SIEM / XDR (alert correlation)", "soc", "planned",
         homepage="https://wazuh.com", note="Bridge already scaffolded (engine/bridge/wazuh.py)."),
    Tool("sysmon", "Sysmon", "Windows endpoint telemetry", "soc", "planned",
         homepage="https://learn.microsoft.com/sysinternals/downloads/sysmon",
         note="Bridge already scaffolded (engine/bridge/sysmon.py)."),
    Tool("suricata", "Suricata", "Network IDS", "soc", "planned",
         homepage="https://suricata.io"),
    Tool("velociraptor", "Velociraptor", "DFIR & threat hunting", "blue", "planned",
         homepage="https://docs.velociraptor.app"),
    Tool("thehive", "TheHive", "SOC case management / SOAR", "soc", "planned",
         homepage="https://thehive-project.org"),

    # ---- PROVIDED: reserved slot for GoalCert-managed/premium tooling -----------
    Tool("goalcert-adversary-pack", "GoalCert Adversary Pack", "Curated managed attack tooling",
         "red", "provided", license="provided",
         note="Reserved slot — GoalCert-provided tooling, not integrated yet."),
    Tool("goalcert-detection-pack", "GoalCert Detection Pack", "Curated managed detection content",
         "soc", "provided", license="provided",
         note="Reserved slot — GoalCert-provided tooling, not integrated yet."),
]

TOOLS_BY_ID = {t.id: t for t in TOOLS}


def integrated_tools() -> list[Tool]:
    return [t for t in TOOLS if t.status == "integrated"]


def registry_public() -> dict:
    """Grouped view for the frontend Tools panel."""
    by_status: dict[str, list[dict]] = {"integrated": [], "planned": [], "provided": []}
    for t in TOOLS:
        by_status.setdefault(t.status, []).append(t.public())
    return {
        "counts": {k: len(v) for k, v in by_status.items()},
        "tools": [t.public() for t in TOOLS],
        "by_status": by_status,
    }
