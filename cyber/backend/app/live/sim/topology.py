"""Live host-graph topology — the heart of the immersive scenario, shared by every team view.

A `Topology` is VLANs of named `Host`s with TCP/445 reachability edges. Hosts move through the W1
state machine (healthy→vulnerable→exploited→infected→propagating→encrypting→impacted, +dormant/
contained/eradicated/recovered). The engine mutates this graph; the frontend renders it as the
structured VLAN map (colour per state, scan rays, strike flashes, expanding red zone).

We model ~24 *named, representative* hosts across 3 VLANs plus an `extra_hosts` counter for the rest
of the 250-host hospital — enough to feel like a real network without drawing 250 nodes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Per-host lifecycle (W1 design doc §8/§12). Colour mapping lives in the frontend.
HOST_STATES = (
    "healthy", "vulnerable", "exploited", "infected", "propagating",
    "encrypting", "impacted", "dormant", "contained", "eradicated", "recovered",
)
# States that count as "the worm holds this host" (a live foothold that can spread / be encrypted).
LIVE_INFECTED = {"infected", "propagating", "encrypting"}


@dataclass
class Host:
    id: str
    name: str
    vlan: str
    role: str = "workstation"          # workstation | fileserver | database | domain_controller | backup | appserver | email
    state: str = "healthy"
    vulnerable: bool = False           # exposes legacy SMBv1 (the worm's vector)
    revealed: bool = False             # discovered by Red's recon yet?
    patient_zero: bool = False
    flags: set[str] = field(default_factory=set)   # persistent, recovery_disabled, encrypted

    def public(self) -> dict:
        return {
            "id": self.id, "name": self.name, "vlan": self.vlan, "role": self.role,
            "state": self.state, "vulnerable": self.vulnerable, "revealed": self.revealed,
            "patient_zero": self.patient_zero, "flags": sorted(self.flags),
        }


@dataclass
class Vlan:
    id: str
    name: str
    reachable: tuple[str, ...] = ()    # vlan ids reachable from here on TCP/445

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "reachable": list(self.reachable)}


@dataclass
class Topology:
    hosts: dict[str, Host]
    vlans: dict[str, Vlan]
    extra_hosts: int = 0               # unnamed remainder of the fleet (still counts toward totals)
    cut_edges: set[tuple[str, str]] = field(default_factory=set)   # segmented vlan pairs (a,b) unordered

    # ---- queries -------------------------------------------------------------
    def by_vlan(self, vlan_id: str) -> list[Host]:
        return [h for h in self.hosts.values() if h.vlan == vlan_id]

    def reachable_vlans(self, vlan_id: str) -> set[str]:
        out = set()
        for dst in self.vlans[vlan_id].reachable:
            pair = tuple(sorted((vlan_id, dst)))
            if pair not in self.cut_edges:
                out.add(dst)
        return out

    def spread_targets(self, src: Host) -> list[Host]:
        """Healthy+vulnerable hosts the worm could reach from an infected `src` (reachability-gated)."""
        reach = self.reachable_vlans(src.vlan)
        return [h for h in self.hosts.values()
                if h.vlan in reach and h.vulnerable and h.state in ("healthy", "vulnerable")]

    def counts(self) -> dict[str, int]:
        c = {s: 0 for s in HOST_STATES}
        for h in self.hosts.values():
            c[h.state] = c.get(h.state, 0) + 1
        return c

    def total_hosts(self) -> int:
        return len(self.hosts) + self.extra_hosts

    def infected_count(self) -> int:
        return sum(1 for h in self.hosts.values() if h.state in LIVE_INFECTED)

    def impacted_count(self) -> int:
        return sum(1 for h in self.hosts.values() if h.state == "impacted")

    def cut_edge(self, a: str, b: str) -> None:
        self.cut_edges.add(tuple(sorted((a, b))))

    def public(self) -> dict:
        return {
            "vlans": [v.public() for v in self.vlans.values()],
            "hosts": [h.public() for h in self.hosts.values()],
            "extra_hosts": self.extra_hosts,
            "cut_edges": [list(e) for e in sorted(self.cut_edges)],
            "counts": self.counts(),
            "total_hosts": self.total_hosts(),
        }


# ===========================================================================
#  W1 — 250-host hospital. Finance / HR user VLANs + a Server VLAN.
# ===========================================================================
def build_w1() -> Topology:
    hosts: dict[str, Host] = {}

    def add(hid: str, name: str, vlan: str, role: str = "workstation",
            vulnerable: bool = False, state: str = "healthy", pz: bool = False) -> None:
        hosts[hid] = Host(id=hid, name=name, vlan=vlan, role=role, vulnerable=vulnerable,
                          state=state, patient_zero=pz)

    # Finance VLAN — patient zero lives here, already infected and unaware.
    add("fin-014", "FIN-WS-014", "fin", vulnerable=True, state="infected", pz=True)
    for i in (1, 2, 3, 5, 8, 11, 17, 22, 26):
        add(f"fin-{i:03d}", f"FIN-WS-{i:03d}", "fin", vulnerable=(i % 3 != 0))
    # HR VLAN
    for i in (1, 2, 4, 7, 9, 13, 18):
        add(f"hr-{i:03d}", f"HR-WS-{i:03d}", "hr", vulnerable=(i % 2 == 1))
    # Server VLAN — the crown jewels (downing these cascades the business impact).
    add("file-01", "FILE-01", "srv", role="fileserver", vulnerable=True)
    add("db-01", "DB-01", "srv", role="database", vulnerable=False)
    add("dc-01", "DC-01", "srv", role="domain_controller", vulnerable=False)
    add("bkp-01", "BKP-01", "srv", role="backup", vulnerable=False)
    add("app-01", "APP-01", "srv", role="appserver", vulnerable=True)
    add("mail-01", "MAIL-01", "srv", role="email", vulnerable=False)

    vlans = {
        "fin": Vlan("fin", "Finance VLAN", reachable=("fin", "hr", "srv")),
        "hr": Vlan("hr", "HR VLAN", reachable=("hr", "fin", "srv")),
        "srv": Vlan("srv", "Server VLAN", reachable=("srv",)),
    }
    # Patient zero is revealed to Red from the start (assumed breach).
    hosts["fin-014"].revealed = True
    return Topology(hosts=hosts, vlans=vlans, extra_hosts=250 - len(hosts))


# ===========================================================================
#  R5 — 85-host corp (Phishing-to-Encrypt ransomware)
# ===========================================================================
def build_r5() -> Topology:
    hosts: dict[str, Host] = {}

    def add(hid: str, name: str, vlan: str, role: str = "workstation",
            vulnerable: bool = False, state: str = "healthy", pz: bool = False) -> None:
        hosts[hid] = Host(id=hid, name=name, vlan=vlan, role=role, vulnerable=vulnerable,
                          state=state, patient_zero=pz)

    # Finance VLAN — j.harper's workstation is patient zero. Starts CLEAN: the attacker must phish
    # the user and land a macro to create the foothold (unlike W1's assumed-breach patient zero).
    add("fin-pc07", "FIN-PC07 (j.harper)", "fin", state="healthy", pz=True, vulnerable=True)
    for i in (1, 2, 3, 4, 5, 8, 10, 12, 15, 18):
        add(f"fin-{i:03d}", f"FIN-WS-{i:03d}", "fin", vulnerable=(i % 4 != 0))
    # Corporate VLAN
    for i in (1, 3, 5, 7, 9, 11, 14, 16, 20):
        add(f"corp-{i:03d}", f"CORP-WS-{i:03d}", "corp", vulnerable=(i % 3 == 0))
    # IT VLAN
    for i in (1, 2, 4):
        add(f"it-{i:03d}", f"IT-WS-{i:03d}", "it", vulnerable=False)
    # Server VLAN
    add("fs-01", "FS-01 (File Server)", "srv", role="fileserver", vulnerable=True)
    add("bkp-01", "BKP-01 (Backup)", "srv", role="backup", vulnerable=False)
    add("dc-01", "DC-01 (Domain Controller)", "srv", role="domain_controller", vulnerable=False)
    add("mail-01", "MAIL-01 (Exchange)", "srv", role="email", vulnerable=False)
    add("app-01", "APP-01 (ERP)", "srv", role="appserver", vulnerable=True)

    vlans = {
        "fin": Vlan("fin", "Finance VLAN", reachable=("fin", "corp", "srv")),
        "corp": Vlan("corp", "Corporate VLAN", reachable=("corp", "fin", "srv")),
        "it": Vlan("it", "IT Admin VLAN", reachable=("it", "srv", "fin", "corp")),
        "srv": Vlan("srv", "Server VLAN", reachable=("srv",)),
    }
    hosts["fin-pc07"].revealed = True
    return Topology(hosts=hosts, vlans=vlans, extra_hosts=85 - len(hosts))


# ===========================================================================
#  C5 — 500-host enterprise (EDR outage exploitation)
# ===========================================================================
def build_c5() -> Topology:
    hosts: dict[str, Host] = {}

    def add(hid: str, name: str, vlan: str, role: str = "workstation",
            vulnerable: bool = False, state: str = "healthy", pz: bool = False) -> None:
        hosts[hid] = Host(id=hid, name=name, vlan=vlan, role=role, vulnerable=vulnerable,
                          state=state, patient_zero=pz)

    # Edge — VPN gateway (attacker's entry point)
    add("vpn-gw", "VPN-GW-01", "edge", role="appserver", vulnerable=True)
    # Corporate VLAN — large fleet, EDR is down. Patient zero starts CLEAN: the crew sprays creds and
    # walks in over the VPN to create the foothold (the EDR outage is what lets it go unnoticed).
    add("eng-ws12", "ENG-WS-12 (m.chen)", "corp", state="healthy", pz=True, vulnerable=True)
    for i in (1, 3, 5, 7, 9, 14, 18, 22, 25, 30, 35, 40):
        add(f"corp-{i:03d}", f"CORP-WS-{i:03d}", "corp", vulnerable=(i % 5 != 0))
    # Dev VLAN
    for i in (1, 4, 8, 11, 15):
        add(f"dev-{i:03d}", f"DEV-WS-{i:03d}", "dev", vulnerable=(i % 3 == 0))
    # Server farm
    add("srv-db01", "SRV-DB-01", "srv", role="database", vulnerable=True)
    add("srv-app03", "SRV-APP-03", "srv", role="appserver", vulnerable=True)
    add("srv-file01", "SRV-FILE-01", "srv", role="fileserver", vulnerable=True)
    add("srv-web01", "SRV-WEB-01", "srv", role="appserver", vulnerable=False)
    # Domain controllers
    add("dc-01", "DC-01", "dc", role="domain_controller", vulnerable=False)
    add("dc-02", "DC-02", "dc", role="domain_controller", vulnerable=False)
    # Data / file shares
    add("data-fs01", "DATA-FS-01", "data", role="fileserver", vulnerable=True)
    add("data-fs02", "DATA-FS-02", "data", role="fileserver", vulnerable=True)
    # Backup
    add("bkp-srv01", "BKP-SRV-01", "bkp", role="backup", vulnerable=False)
    add("bkp-srv02", "BKP-SRV-02", "bkp", role="backup", vulnerable=False)
    # SOC
    add("siem-01", "SIEM-01", "soc", role="appserver", vulnerable=False)
    # Cloud connector
    add("cloud-gw", "CLOUD-GW-01", "cloud", role="appserver", vulnerable=True)

    vlans = {
        "edge": Vlan("edge", "Edge / VPN", reachable=("edge", "corp")),
        "corp": Vlan("corp", "Corporate Endpoints", reachable=("corp", "dev", "srv", "dc")),
        "dev": Vlan("dev", "Dev / Engineering", reachable=("dev", "corp", "srv")),
        "srv": Vlan("srv", "Server Farm", reachable=("srv", "dc", "data")),
        "dc": Vlan("dc", "Domain Controllers", reachable=("dc", "srv", "corp", "data", "bkp")),
        "data": Vlan("data", "Data / File Shares", reachable=("data", "srv")),
        "bkp": Vlan("bkp", "Backup Infrastructure", reachable=("bkp",)),
        "soc": Vlan("soc", "SOC / SIEM", reachable=("soc",)),
        "cloud": Vlan("cloud", "Cloud (Azure/AWS)", reachable=("cloud", "corp")),
    }
    hosts["eng-ws12"].revealed = True
    return Topology(hosts=hosts, vlans=vlans, extra_hosts=500 - len(hosts))
