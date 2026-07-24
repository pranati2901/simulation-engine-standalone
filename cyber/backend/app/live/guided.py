"""Guided scenario scripts — the per-phase, per-role tutorial layer that rides on a LiveSession.

A LiveSession gives us the multi-user substrate (Red/Blue/SOC seats, auto-drivers, the shared World,
real-tool live-fire against the Docker/Kali range, WS broadcast). A *guided scenario* adds the thing
the substrate lacks: a **scripted walkthrough** that teaches each team what to do, phase by phase, and
reacts as they do it.

This layer is **dynamic per scenario**: every scenario (W1/R5/C5) carries its OWN per-phase Red/Blue/SOC
behaviour here. The runtime (`live/guided_runtime.py`) is generic — it just walks whatever phases/tasks
the active scenario defines. The common `red_playbook`/`blue_playbook`/`soc_playbook` are NOT the
actionable layer for guided play; they are only reused under the hood for the real-tool FireSpec
mappings and the world model.

Each `GuidedTask` spells out a team's REAL behaviour for one phase across three lenses the UI renders
as **Does / How / Outcome**:
  - does    — WHAT this team does this phase (the real-world behaviour),
  - how     — HOW: the method / tool / command / technique (+ MITRE),
  - outcome — what it ACCOMPLISHES toward attacking or defending the mission.

`kind` decides how a task completes:
  - "real_tool" — runs a REAL tool against the lab (maps to a live red action with a FireSpec:
    nmap / NetExec). The only steps that can be literally real on the Docker range.
  - "sim_red"   — a scripted attacker step; the engine applies it in-model and emits the doc's telemetry.
  - "soc"/"blue"— a defender move; may carry a `mitigates` lever that bends the worm's growth when in time.
  - "observe"   — a read-only "look at X" beat (auto-completes; teaches where to look).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
#  Worm / host-population model (W1 §8) — the simulated state behind the map
# ---------------------------------------------------------------------------
HOST_STATES = (
    "healthy", "vulnerable", "exploited", "infected", "propagating",
    "encrypting", "impacted", "dormant", "contained", "eradicated", "recovered",
)


@dataclass
class WormNetwork:
    """Population-level worm state + live cost ledger (W1 §8/§9). Tunable defaults from the doc."""
    total_hosts: int = 250
    vulnerable_density: float = 0.6
    infected: int = 0
    encrypting: int = 0
    impacted: int = 0
    contained: int = 0
    dormant: int = 0
    recovered: int = 0
    backups_safe: bool = True
    recovery_disabled: bool = False
    segmented: bool = False
    smbv1_patched: bool = False
    kill_switch_tripped: bool = False
    r_value: float = 2.4
    files_per_host: int = 8000
    cost_per_user_hour: float = 85.0
    reimage_cost: float = 750.0

    def infected_ratio(self) -> float:
        return self.infected / self.total_hosts if self.total_hosts else 0.0

    def encrypted_files(self) -> int:
        return self.impacted * self.files_per_host

    def financial_loss(self) -> int:
        return int(self.impacted * self.cost_per_user_hour + self.impacted * self.reimage_cost)

    def outcome_band(self) -> str:
        ratio = self.infected_ratio()
        if ratio < 0.10 and self.backups_safe:
            return "Contained"
        if ratio < 0.45:
            return "Degraded"
        return "Catastrophic"

    def snapshot(self) -> dict:
        return {
            "total_hosts": self.total_hosts, "infected": self.infected, "encrypting": self.encrypting,
            "impacted": self.impacted, "contained": self.contained, "dormant": self.dormant,
            "recovered": self.recovered, "infected_ratio": round(self.infected_ratio(), 3),
            "backups_safe": self.backups_safe, "recovery_disabled": self.recovery_disabled,
            "segmented": self.segmented, "smbv1_patched": self.smbv1_patched,
            "kill_switch_tripped": self.kill_switch_tripped, "r_value": round(self.r_value, 2),
            "encrypted_files": self.encrypted_files(), "financial_loss": self.financial_loss(),
            "outcome_band": self.outcome_band(),
        }


# ---------------------------------------------------------------------------
#  Script data model
# ---------------------------------------------------------------------------
TASK_KINDS = ("real_tool", "sim_red", "soc", "blue", "observe")


@dataclass(frozen=True)
class GuidedTask:
    id: str
    role: str                       # "red" | "blue" | "soc"
    kind: str                       # one of TASK_KINDS
    label: str                      # short imperative shown in the checklist
    does: str                       # WHAT this team does this phase
    how: str                        # HOW — method / tool / command / technique (+MITRE)
    outcome: str                    # what it ACCOMPLISHES toward the mission
    action_id: str = ""             # live action id to invoke (real_tool → must have a FireSpec)
    tool: str = ""                  # display hint, e.g. "nmap", "NetExec"
    hint: str = ""                  # nudge shown if the learner is stuck
    mitigates: str = ""             # for soc/blue: a worm lever this bends
    optional: bool = False          # does NOT gate phase advance when True

    def public(self) -> dict:
        return {
            "id": self.id, "role": self.role, "kind": self.kind, "label": self.label,
            "does": self.does, "how": self.how, "outcome": self.outcome,
            "action_id": self.action_id, "tool": self.tool, "hint": self.hint,
            "mitigates": self.mitigates, "optional": self.optional,
        }


@dataclass(frozen=True)
class DecisionPoint:
    """A W1 §11 decision node — the highest-leverage defender choice in a phase."""
    id: str
    prompt: str
    detect: str = ""
    investigate: str = ""
    contain: str = ""
    eradicate: str = ""
    inaction: str = ""

    def public(self) -> dict:
        return {"id": self.id, "prompt": self.prompt, "detect": self.detect,
                "investigate": self.investigate, "contain": self.contain,
                "eradicate": self.eradicate, "inaction": self.inaction}


@dataclass(frozen=True)
class GuidedPhase:
    id: str
    index: int
    name: str
    mitre: str
    stage_kind: str                 # "real" | "simulated"
    briefing: str                   # top pop-up when the phase opens
    attacker_goal: str
    victim_experience: str          # §4
    soc_signal: str                 # §5 (funnel + signal strength)
    tasks: tuple[GuidedTask, ...] = ()
    decision_point: DecisionPoint | None = None
    network_effect: dict = field(default_factory=dict)

    def tasks_for(self, role: str) -> list[GuidedTask]:
        return [t for t in self.tasks if t.role == role]

    def gating_tasks(self) -> list[GuidedTask]:
        return [t for t in self.tasks if not t.optional]

    def public(self) -> dict:
        return {
            "id": self.id, "index": self.index, "name": self.name, "mitre": self.mitre,
            "stage_kind": self.stage_kind, "briefing": self.briefing,
            "attacker_goal": self.attacker_goal, "victim_experience": self.victim_experience,
            "soc_signal": self.soc_signal, "tasks": [t.public() for t in self.tasks],
            "decision_point": self.decision_point.public() if self.decision_point else None,
        }


@dataclass(frozen=True)
class GuidedScenario:
    id: str
    name: str
    subtitle: str
    summary: str
    total_hosts: int
    phases: tuple[GuidedPhase, ...]
    mitre_chain: tuple[str, ...] = ()

    def phase(self, index: int) -> GuidedPhase | None:
        return self.phases[index] if 0 <= index < len(self.phases) else None

    def meta(self) -> dict:
        return {"id": self.id, "name": self.name, "subtitle": self.subtitle, "summary": self.summary,
                "total_hosts": self.total_hosts, "phase_count": len(self.phases),
                "mitre_chain": list(self.mitre_chain)}

    def public(self) -> dict:
        return {**self.meta(), "phases": [p.public() for p in self.phases]}


# ===========================================================================
#  W1 — WannaCry-style SMB worm (from "WannaCry Ransomware Worm.pdf")
# ===========================================================================
# Stages 1–2 are REAL (nmap host sweep + NetExec SMB enumeration vs the Docker range).
# Stages 3–11 are simulated worm behaviour the doc explicitly forbids running for real.

_W1_PHASES: tuple[GuidedPhase, ...] = (
    GuidedPhase(
        id="discovery", index=0, name="Network Discovery", mitre="T1046", stage_kind="real",
        briefing="Patient-zero (FIN-WS-014) is quietly compromised. The worm's first move is to find "
                 "neighbours it can reach over SMB. Nothing looks wrong to the business yet — which is "
                 "exactly why this is the cheapest moment to catch it.",
        attacker_goal="Enumerate live hosts reachable on the local subnet(s).",
        victim_experience="Silent. CPU and disk normal; the user keeps working, unaware.",
        soc_signal="A spike in short-lived TCP/445 connections from one source — a horizontal scan "
                   "pattern. Signal: LOW / easy to miss (often deprioritised as noise).",
        tasks=(
            GuidedTask(
                id="d_red_sweep", role="red", kind="real_tool", action_id="intrecon.network", tool="nmap",
                label="Sweep the subnet for live hosts",
                does="Enumerate every reachable host on patient-zero's subnet — the worm's opening move.",
                how="Real nmap host-discovery sweep from Kali (nmap -sn) across the lab range (T1046).",
                outcome="Produces the live-host list the worm will probe for SMBv1 — and the first scan the SOC could catch.",
                hint="Use the Network Discovery action; it runs nmap -sn against the lab subnet."),
            GuidedTask(
                id="d_soc_scan", role="soc", kind="soc", mitigates="early_detect",
                label="Promote the port-445 scan alert",
                does="Notice the one-source-to-many TCP/445 fan-out the SIEM logged at low priority and refuse to write it off as noise.",
                how="Tune/promote the horizontal-scan detection rule; pivot on the source host.",
                outcome="Catches the worm at its cheapest stage — detection opportunity #1, before any host is exploited."),
            GuidedTask(
                id="d_blue_isolate", role="blue", kind="blue", mitigates="isolate",
                label="Isolate patient-zero",
                does="Pull the scanning source host off the network before it can exploit a neighbour.",
                how="NAC/EDR network isolation of the source host; queue an SMBv1 disable for the fleet.",
                outcome="Removes the worm's launch point — done here, the spread never really starts (Contained)."),
        ),
        decision_point=DecisionPoint(
            id="DP-1", prompt="Port-445 scan spike from a single host.",
            detect="Promote the scan alert", investigate="Pivot on the source host",
            contain="Isolate patient-zero (NAC/EDR)", eradicate="Disable SMBv1 + patch the fleet",
            inaction="The worm reaches Stage 3 (exploit) on its neighbours."),
        network_effect={"state": "propagating"},
    ),
    GuidedPhase(
        id="smb_id", index=1, name="SMB Target Identification", mitre="T1018", stage_kind="real",
        briefing="The worm filters the live hosts down to those still speaking legacy SMBv1 — the "
                 "vulnerable population. On a modern network, an SMBv1 negotiation is itself a red flag.",
        attacker_goal="Identify which live hosts expose the vulnerable SMBv1 service.",
        victim_experience="Still silent — sustained SMB handshake traffic, nothing user-visible.",
        soc_signal="Repeated SMB session setups to many hosts; unusual SMBv1 dialect negotiation. "
                   "Signal: LOW–MEDIUM (possible 'scanning' alert).",
        tasks=(
            GuidedTask(
                id="s_red_enum", role="red", kind="real_tool", action_id="intrecon.identity_graph", tool="NetExec",
                label="Enumerate SMB shares & sessions",
                does="Filter the live hosts down to those exposing SMB, and list their shares.",
                how="Real NetExec SMB enumeration (nxc smb --shares) against the file-server target (T1018).",
                outcome="Yields the target shortlist the worm will exploit — and reveals exposed file shares you can read.",
                hint="Use the SMB Enumeration action; it runs nxc smb --shares against the file target."),
            GuidedTask(
                id="s_red_ver", role="red", kind="real_tool", action_id="recon.fingerprint", tool="nmap", optional=True,
                label="Fingerprint SMB service versions",
                does="Confirm which hosts run the vulnerable SMB dialect.",
                how="nmap -sV service/version detection on the target.",
                outcome="Turns 'live' into a per-host 'vulnerable vs patched' verdict."),
            GuidedTask(
                id="s_soc_smbv1", role="soc", kind="soc", mitigates="early_detect",
                label="Alert on SMBv1 negotiation",
                does="Flag the legacy-protocol negotiations and repeated SMB setups from one source.",
                how="Enable the SMBv1-dialect detection rule; tag the source as a probable scanner.",
                outcome="A second early tell — legacy SMBv1 on a modern net is itself suspicious."),
            GuidedTask(
                id="s_blue_disable", role="blue", kind="blue", mitigates="patch",
                label="Disable SMBv1 on exposed hosts",
                does="Start removing the vulnerable service from hosts that don't need it.",
                how="Push a GPO/config to disable SMBv1, prioritising the hosts the scan just touched.",
                outcome="Shrinks the vulnerable population before the worm can exploit it."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="exploit", index=2, name="Exploit Vulnerable Host", mitre="T1210", stage_kind="simulated",
        briefing="The worm sends its SMBv1 exploit at a vulnerable target. (Simulated — a success "
                 "probability that emits an IDS signature; no exploit code runs.) That IDS hit is the "
                 "highest-confidence EARLY signal in the whole chain.",
        attacker_goal="Gain code execution on a vulnerable target.",
        victim_experience="Compromised but symptom-free — the machine is owned, the user notices nothing.",
        soc_signal="IDS/IPS exploit-pattern signature on SMB traffic. Signal: MEDIUM–HIGH — should "
                   "trigger investigation. Inline IPS could block here.",
        tasks=(
            GuidedTask(
                id="e_red_exploit", role="red", kind="sim_red",
                label="Fire the SMBv1 exploit at a vulnerable host",
                does="Attempt remote code execution against a vulnerable target.",
                how="Simulated exploit (T1210) — a success-probability gate that emits an IDS exploit signature; no exploit code runs.",
                outcome="Gains a foothold (Vulnerable→Exploited) and produces the loudest early detection signal."),
            GuidedTask(
                id="e_soc_ids", role="soc", kind="soc", mitigates="early_detect",
                label="Confirm the IDS exploit signature",
                does="Validate the exploit-pattern signature on SMB traffic and raise its priority.",
                how="Confirm the IDS/IPS alert; escalate to investigation (Medium–High confidence).",
                outcome="Highest-confidence early signal — acting here beats payload + persistence setting in."),
            GuidedTask(
                id="e_blue_block", role="blue", kind="blue", mitigates="segment",
                label="Block TCP/445 at the segment boundary",
                does="Stop SMB from crossing the segment so the exploit can't reach more hosts.",
                how="Boundary firewall rule denying 445 east-west; inline IPS can drop the signature.",
                outcome="Caps reachability at the segment edge — buys time before propagation."),
        ),
        decision_point=DecisionPoint(
            id="DP-2", prompt="IDS exploit signature on SMB traffic.",
            detect="Confirm the signature", investigate="Triage the exploited host",
            contain="Block 445 at the boundary", eradicate="Patch the vulnerable hosts",
            inaction="Payload deploys and persistence sets in."),
        network_effect={"infect": 3, "state": "exploited"},
    ),
    GuidedPhase(
        id="payload", index=3, name="Payload Deployment", mitre="T1059.003", stage_kind="simulated",
        briefing="With a foothold, the worm writes its payload to a system directory and launches it. "
                 "EDR can see the file-write and the odd process lineage — if anyone's watching the endpoint.",
        attacker_goal="Place and run the worm/ransomware payload on the exploited host.",
        victim_experience="Still nothing visible — faint background disk activity as the dropper installs.",
        soc_signal="File-creation in a system dir + a process spawned from an unexpected parent. "
                   "Signal: MEDIUM — an EDR alert if endpoint telemetry is tuned.",
        tasks=(
            GuidedTask(
                id="p_red_drop", role="red", kind="sim_red",
                label="Drop & launch the payload",
                does="Write the worm payload to a system directory and execute it via the command interpreter.",
                how="Simulated file-write + process spawn (T1059.003); host Exploited→Infected.",
                outcome="The worm is now resident and running on the host."),
            GuidedTask(
                id="p_soc_edr", role="soc", kind="soc", mitigates="early_detect",
                label="Triage the EDR file-write / process alert",
                does="Inspect the suspicious system-dir file write and the odd process lineage.",
                how="EDR file/process-anomaly alert review; flag 'service spawned cmd/script'.",
                outcome="A mid-funnel chance to catch the infection on the endpoint before it persists."),
            GuidedTask(
                id="p_blue_quarantine", role="blue", kind="blue", mitigates="contain",
                label="Quarantine the infected host",
                does="Network-quarantine the host at the EDR level.",
                how="EDR host containment — isolate from the network, retain for forensics.",
                outcome="Stops this host seeding others before it can persist."),
        ),
        network_effect={"infect": 1, "state": "infected"},
    ),
    GuidedPhase(
        id="persistence", index=4, name="Establish Persistence", mitre="T1543", stage_kind="simulated",
        briefing="The worm registers a service / auto-run so it survives reboot. The moment this lands, "
                 "recovery cost jumps — a process-kill no longer cleans the host; it needs reimaging.",
        attacker_goal="Survive reboot and re-execute.",
        victim_experience="No change for the user — a new service quietly exists.",
        soc_signal="New-service creation / autorun-registry modification event. Signal: MEDIUM "
                   "(classic persistence detection on EDR/Sysmon).",
        tasks=(
            GuidedTask(
                id="per_red_persist", role="red", kind="sim_red",
                label="Register service / auto-run persistence",
                does="Install a persistence mechanism so the payload survives reboot.",
                how="Simulated new-service / autorun creation (T1543).",
                outcome="Raises recovery cost — the host now needs reimaging, not just a process-kill."),
            GuidedTask(
                id="per_soc_newsvc", role="soc", kind="soc", mitigates="early_detect",
                label="Raise the new-service alert",
                does="Detect the service-creation / autorun-registry change.",
                how="Sysmon/EDR new-persistence detection rule.",
                outcome="A reliable mid-funnel tell that the host is owned, not just touched."),
            GuidedTask(
                id="per_blue_kill", role="blue", kind="blue", mitigates="eradicate",
                label="Kill service + remove persistence",
                does="Stop the malicious service and delete its autorun.",
                how="EDR / remote eradication of the persistence mechanism on the host.",
                outcome="A reboot can no longer revive the payload on this host."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="c2", index=5, name="C2 / Kill-Switch Callback", mitre="T1071.001", stage_kind="simulated",
        briefing="Each infected host makes ONE outbound request to a hardcoded domain — the worm's "
                 "kill-switch check. If that domain answers, the worm halts. Sinkhole it and you freeze "
                 "new encryption fleet-wide: the famous accidental off-switch.",
        attacker_goal="Perform the external kill-switch lookup (continue-or-abort).",
        victim_experience="Nothing visible — a single odd outbound connection per host.",
        soc_signal="Outbound DNS/HTTP to an unusual, newly-seen domain. Signal: MEDIUM "
                   "(proxy/DNS / newly-registered-domain anomaly).",
        tasks=(
            GuidedTask(
                id="c_red_c2", role="red", kind="sim_red",
                label="Perform the C2 / kill-switch lookup",
                does="Make the single hardcoded outbound check that decides continue-or-abort.",
                how="Simulated DNS/HTTP callback to a newly-seen domain (T1071.001); unreachable → proceed to encrypt.",
                outcome="If the domain stays unreachable, the worm commits to encryption."),
            GuidedTask(
                id="c_soc_dns", role="soc", kind="soc", mitigates="early_detect",
                label="Identify the callback domain",
                does="Spot the rare outbound domain in DNS/proxy logs and identify it.",
                how="Newly-registered-domain / DNS anomaly detection; extract the domain for Blue.",
                outcome="Hands Blue the exact domain to sinkhole — enabling the kill switch."),
            GuidedTask(
                id="c_blue_sinkhole", role="blue", kind="blue", mitigates="sinkhole",
                label="Sinkhole the kill-switch domain",
                does="Make the domain resolve to a sinkhole so every host's check 'succeeds'.",
                how="DNS sinkhole / internal redirect of the kill-switch domain.",
                outcome="Trips the kill switch fleet-wide — infected hosts go Dormant, new encryption halts."),
        ),
        decision_point=DecisionPoint(
            id="DP-3", prompt="C2 / kill-switch callback to a newly-seen domain.",
            detect="DNS/proxy alert", investigate="Identify the domain",
            contain="Sinkhole the domain (the historical kill switch)", eradicate="—",
            inaction="Encryption proceeds unhalted."),
        network_effect={"infect": 2, "state": "propagating"},
    ),
    GuidedPhase(
        id="lateral", index=6, name="Lateral Movement", mitre="T1021.002", stage_kind="simulated",
        briefing="Infected hosts repeat Stages 1–3 against adjacent subnets over SMB. The same scan+exploit "
                 "pattern now comes from MULTIPLE internal sources at once — the unambiguous 'this is an "
                 "active worm' signal. Segmentation here converts exponential growth into a bounded blast radius.",
        attacker_goal="Reach hosts beyond the original subnet.",
        victim_experience="Some hosts feel slightly slow; east-west SMB traffic spikes.",
        soc_signal="Scan + exploit patterns from many internal sources simultaneously. Signal: HIGH — "
                   "a clear 'it's spreading' signal (multi-source correlation).",
        tasks=(
            GuidedTask(
                id="l_red_lateral", role="red", kind="sim_red",
                label="Pivot over SMB into the next VLAN",
                does="Spawn the worm's propagation thread from an infected host into an adjacent segment.",
                how="Simulated SMB lateral movement (T1021.002); engine seeds exploited hosts in a neighbour VLAN, emitting scan+exploit telemetry from multiple sources.",
                outcome="Red zone crosses a segment boundary — pushing toward the server-VLAN objective."),
            GuidedTask(
                id="l_soc_correlate", role="soc", kind="soc", mitigates="early_detect",
                label="Correlate the multi-source scan pattern",
                does="Recognise the same scan/exploit behaviour now coming from several internal hosts and fuse the alerts into one incident.",
                how="Multi-source correlation in the SIEM (group by signature across source IPs); declare an 'active worm propagation' incident and hand to IR.",
                outcome="Turns scattered alerts into the unambiguous 'it's spreading' signal — the trigger Blue needs to justify segmentation."),
            GuidedTask(
                id="l_blue_segment", role="blue", kind="blue", mitigates="segment",
                label="Segment the network — sever inter-VLAN SMB",
                does="Cut the TCP/445 edges between segments so infected hosts can only reach already-infected neighbours.",
                how="Emergency segmentation at the firewall/NAC (deny 445 across VLAN boundaries) — the single most effective W1 containment.",
                outcome="Converts exponential growth into a bounded blast radius."),
        ),
        decision_point=DecisionPoint(
            id="DP-4", prompt="Multi-source lateral movement detected.",
            detect="Correlate the sources", investigate="Map the infected set",
            contain="Segment the network", eradicate="Mass-isolate infected hosts",
            inaction="The worm crosses into the server VLAN."),
        network_effect={"infect": 8, "state": "propagating"},
    ),
    GuidedPhase(
        id="propagation", index=7, name="Repeat Propagation", mitre="T1210", stage_kind="simulated",
        briefing="Every infected host now runs the full loop independently. Without intervention the "
                 "infected count climbs geometrically until vulnerable hosts are exhausted or you cap the "
                 "blast radius. Network performance starts to visibly degrade.",
        attacker_goal="Sustain exponential growth across the host population.",
        victim_experience="Noticeable slowness; helpdesk tickets about the network begin.",
        soc_signal="Network-wide port-445 storm; SMB saturation. Signal: aggregate volume anomaly / "
                   "segment-level traffic alarms.",
        tasks=(
            GuidedTask(
                id="prop_red_spread", role="red", kind="sim_red",
                label="Sustain exponential growth",
                does="Let every infected host run the full loop independently.",
                how="Population-level spread: infected × R while vulnerable+reachable hosts remain.",
                outcome="Infected count climbs geometrically; network performance starts to degrade."),
            GuidedTask(
                id="prop_soc_storm", role="soc", kind="soc",
                label="Escalate the network-wide 445 storm",
                does="Confirm fleet-wide saturation and brief leadership on the blast-radius trajectory.",
                how="Aggregate volume anomaly + infection-count curve + R-value gauge; segment-level traffic alarms.",
                outcome="Gives management the picture to authorise drastic fleet-wide containment."),
            GuidedTask(
                id="prop_blue_patch", role="blue", kind="blue", mitigates="patch",
                label="Push the SMBv1 patch fleet-wide",
                does="Eradicate the propagation vector across the whole fleet.",
                how="Emergency patch / disable SMBv1 (WSUS/GPO) on all hosts.",
                outcome="New infections stop even inside reachable segments — collapses R toward zero."),
        ),
        network_effect={"infect": 18, "state": "propagating"},
    ),
    GuidedPhase(
        id="disable_recovery", index=8, name="Disable Recovery", mitre="T1490", stage_kind="simulated",
        briefing="Before encrypting, the worm deletes volume shadow copies and the backup catalog on "
                 "each host — one of the STRONGEST ransomware tells, and the last moment offline backups "
                 "can still save you. Caught here, isolation still spares files not yet encrypted.",
        attacker_goal="Prevent local restoration before encryption.",
        victim_experience="A brief micro-freeze on some hosts as recovery is torn down.",
        soc_signal="High-fidelity command-line events: shadow-copy deletion, backup-catalog deletion. "
                   "Signal: HIGH / unambiguous ransomware precursor.",
        tasks=(
            GuidedTask(
                id="dr_red_shadow", role="red", kind="sim_red",
                label="Delete shadow copies & backup catalog",
                does="Tear down local recovery on infected hosts before encrypting.",
                how="Simulated shadow-copy / backup-catalog deletion commands (T1490); recovery_disabled=true.",
                outcome="Local restore is gone — recovery now depends entirely on offline backups."),
            GuidedTask(
                id="dr_soc_shadow", role="soc", kind="soc", mitigates="early_detect",
                label="Alert on shadow-copy deletion",
                does="Catch the high-fidelity shadow-delete command lines and declare a major incident.",
                how="Ransomware-precursor detection rule on the shadow-delete / backup-catalog commands.",
                outcome="Near-certain ransomware indicator — caught here, isolation still saves un-encrypted files."),
            GuidedTask(
                id="dr_blue_backups", role="blue", kind="blue", mitigates="backups",
                label="Preserve backups offline",
                does="Pull backups offline / immutable so the worm can't reach them.",
                how="Air-gap or immutable-lock the backup repository; verify last-known-good.",
                outcome="The one move that meaningfully cuts recovery cost after encryption."),
        ),
        decision_point=DecisionPoint(
            id="DP-5", prompt="Shadow-copy deletion across infected hosts.",
            detect="Shadow-delete alert", investigate="Confirm pre-encryption stage",
            contain="Emergency host isolation", eradicate="Protect / verify offline backups",
            inaction="Files become unrecoverable locally."),
        network_effect={"recovery_disabled": True, "infect": 6, "state": "encrypting"},
    ),
    GuidedPhase(
        id="encrypt", index=9, name="Encrypt Files", mitre="T1486", stage_kind="simulated",
        briefing="The worm enumerates documents/images/databases and encrypts them, renames with a new "
                 "extension, drops ransom notes, and throws up a lock screen. (Simulated as file-state flips "
                 "— no real cipher.) Detection here only limits SPREAD, not local damage.",
        attacker_goal="Render business data inaccessible to force ransom payment.",
        victim_experience="Files turn to generic icons and gain a new extension; apps throw 'corrupted' "
                          "errors; ransom notes appear; a full-screen lock seizes the display.",
        soc_signal="Mass file-modify + rename burst; new extension en masse; ransom-note creation; disk "
                   "I/O spike. Signal: VERY HIGH — ransomware confirmed.",
        tasks=(
            GuidedTask(
                id="enc_red_encrypt", role="red", kind="sim_red",
                label="Encrypt files & drop ransom notes",
                does="Enumerate and encrypt documents, rename with a new extension, drop notes, lock the screen.",
                how="Simulated file-state flips (T1486) — no real cipher; hosts Encrypting→Impacted.",
                outcome="Business data inaccessible on impacted hosts; ransom demand presented."),
            GuidedTask(
                id="enc_soc_massrename", role="soc", kind="soc",
                label="Fire the mass-rename detection",
                does="Confirm ransomware and scope encrypting vs already-impacted hosts.",
                how="Mass-modify / entropy + ransom-note signature ('many files changed by one process in seconds').",
                outcome="Confirms the incident's worst stage and scopes what can still be saved."),
            GuidedTask(
                id="enc_blue_isolate", role="blue", kind="blue", mitigates="contain",
                label="Isolate to stop the spread",
                does="Quarantine encrypting hosts so they can't seed neighbours.",
                how="Mass EDR / network isolation of hosts showing the mass-rename burst.",
                outcome="Can't un-encrypt what's done, but walls off the clean hosts."),
        ),
        decision_point=DecisionPoint(
            id="DP-6", prompt="Mass encryption / ransom notes appearing.",
            detect="Mass-rename alert", investigate="Scope the impact",
            contain="Quarantine to stop spread", eradicate="Begin restore from clean backups",
            inaction="Blast radius keeps growing."),
        network_effect={"encrypt_all": True, "state": "impacted"},
    ),
    GuidedPhase(
        id="impact", index=10, name="Business Impact & Recovery", mitre="T1486", stage_kind="simulated",
        briefing="The consequence stage: outages, downtime, and a running financial-loss counter. The "
                 "debrief overlays YOUR action timeline on the cost curve — the money saved (or lost) by "
                 "acting at minute X. Recovery now depends entirely on clean offline backups.",
        attacker_goal="(Consequence) Maximise disruption to force payment.",
        victim_experience="Hosts unusable; shared services down; work stops across affected departments.",
        soc_signal="Availability monitors firing; service-health red; helpdesk surge; SLA-breach alarms. "
                   "Signal: CRITICAL — major incident.",
        tasks=(
            GuidedTask(
                id="imp_blue_restore", role="blue", kind="blue", mitigates="restore",
                label="Restore impacted systems from clean backups",
                does="Rebuild and restore impacted hosts from the preserved offline backup set.",
                how="Reimage + restore from offline backups (only possible if they were protected at DP-5).",
                outcome="The only move that recovers data after encryption."),
            GuidedTask(
                id="imp_soc_timeline", role="soc", kind="observe",
                label="Assemble the incident timeline",
                does="Reconstruct when each signal first appeared versus when the team acted.",
                how="Build the funnel timeline for the After-Action Report + cost-curve overlay.",
                outcome="Quantifies the money saved/lost by acting at minute X — the core lesson."),
            GuidedTask(
                id="imp_red_review", role="red", kind="observe", optional=True,
                label="Review the blast radius achieved",
                does="See how far the worm got against this defender.",
                how="Read the final infection/impact map and the cost curve.",
                outcome="Against an early-acting team, a fraction of the catastrophic no-intervention curve."),
        ),
        network_effect={},
    ),
)

W1 = GuidedScenario(
    id="scn-wannacry-w1",
    name="Operation Tripwire",
    subtitle="WannaCry-Style SMB Worm",
    summary="A self-propagating ransomware worm sweeps a 250-host hospital network over SMBv1. Run the "
            "real early kill-chain (nmap host sweep + NetExec SMB enumeration) from Kali, then watch the "
            "simulated worm spread, disable recovery, and encrypt — learning that the cheapest detection "
            "is always the earliest one.",
    total_hosts=250,
    phases=_W1_PHASES,
    mitre_chain=("T1046", "T1018", "T1210", "T1059.003", "T1543", "T1071.001",
                 "T1021.002", "T1490", "T1486"),
)


# ===========================================================================
#  R5 — Phishing-to-Encrypt ransomware campaign (from "Ransomware Scenario.pdf")
# ===========================================================================
# A targeted, human-operated campaign on an 85-host corp (corp.northwind.local). Stages 7–8
# (discovery + credentialed reach) are REAL on the Docker range (NetExec SMB enum + auth); the
# phishing, macro, beacon, encryption and recovery-inhibition stages are simulated.

_R5_PHASES: tuple[GuidedPhase, ...] = (
    GuidedPhase(
        id="phish", index=0, name="Spear Phishing", mitre="T1566.001", stage_kind="simulated",
        briefing="A lookalike-domain invoice lands in a Finance user's inbox (j.harper). Nothing is "
                 "compromised yet — reporting or quarantining the mail here is the cleanest possible win.",
        attacker_goal="Deliver a weaponized macro lure to a high-value user.",
        victim_experience="A new email: vendor branding, urgent 'Overdue Invoice', an .xlsm attachment, "
                          "an external-sender banner and a subtly wrong sender domain.",
        soc_signal="Email-gateway: SPF fail + macro attachment + lookalike domain. Signal: LOW "
                   "(correlation rule) — the earliest possible kill-chain break.",
        tasks=(
            GuidedTask(id="r_red_phish", role="red", kind="sim_red",
                label="Send the invoice lure",
                does="Deliver a macro-enabled invoice to the Finance user from a lookalike domain.",
                how="Simulated email injection (T1566.001) — gateway event with SPF fail + external sender.",
                outcome="The lure sits in the inbox awaiting a click — the cheapest stage to stop the chain."),
            GuidedTask(id="r_soc_gw", role="soc", kind="soc", mitigates="early_detect",
                label="Flag the inbound phish",
                does="Catch the SPF-fail + macro-attachment + lookalike-domain correlation.",
                how="Email-gateway anti-phish rule; raise a low-confidence inbound-mail alert.",
                outcome="Spots the lure before anyone opens it — the earliest detection opportunity."),
            GuidedTask(id="r_blue_quarantine", role="blue", kind="blue", mitigates="isolate",
                label="Quarantine the mail org-wide",
                does="Purge the lure from every mailbox before it's opened.",
                how="Mail-flow quarantine / purge by sender + subject across the org.",
                outcome="Removes the lure pre-open — a Platinum-tier break, no execution ever occurs."),
        ),
        decision_point=DecisionPoint(id="DP-1", prompt="Phish delivered to a Finance user.",
            detect="Gateway anti-phish alert", investigate="Inspect sender/SPF/domain",
            contain="Quarantine the mail org-wide", eradicate="Block the sender domain",
            inaction="The user opens the attachment and enables macros."),
        network_effect={"state": "infected"},
    ),
    GuidedPhase(
        id="execution", index=1, name="User Execution", mitre="T1204.002", stage_kind="simulated",
        briefing="The user clicks Enable Content. The Office macro spawns PowerShell — delivery has "
                 "become code execution. Patient zero (WKSTN-FIN-07) turns SUSPICIOUS.",
        attacker_goal="Convert delivery into execution by inducing the macro.",
        victim_experience="The document shows a blurred 'protected' page with an Enable Content banner; "
                          "clicking it triggers the chain — the desktop looks normal afterwards.",
        soc_signal="Sysmon EID1: EXCEL.EXE → powershell.exe. Signal: MEDIUM — the classic macro-execution "
                   "parent/child signature.",
        tasks=(
            GuidedTask(id="x_red_macro", role="red", kind="sim_red",
                label="Induce macro execution",
                does="The victim enables content; the macro spawns a hidden PowerShell child.",
                how="Simulated Office→PowerShell process_create (Sysmon EID1, T1204.002).",
                outcome="Patient zero turns SUSPICIOUS — the foothold begins."),
            GuidedTask(id="x_soc_ppid", role="soc", kind="soc", mitigates="early_detect",
                label="Catch Office spawning PowerShell",
                does="Spot the EXCEL.EXE→powershell.exe parent/child anomaly.",
                how="Macro-execution detection rule (Office app spawning a script interpreter).",
                outcome="A medium-confidence early signal — act before C2 establishes."),
            GuidedTask(id="x_blue_isolate", role="blue", kind="blue", mitigates="isolate",
                label="Isolate the victim workstation",
                does="Network-quarantine WKSTN-FIN-07 before C2 comes up.",
                how="EDR host isolation.",
                outcome="Breaks the chain pre-C2 — a Gold-tier containment window."),
        ),
        decision_point=DecisionPoint(id="DP-2", prompt="Office spawned PowerShell on a Finance host.",
            detect="Macro-execution alert", investigate="Open the process tree",
            contain="Isolate WKSTN-FIN-07 pre-C2", eradicate="Kill the PowerShell chain",
            inaction="The download cradle runs and the loader lands."),
        network_effect={"infect": 1, "state": "infected"},
    ),
    GuidedPhase(
        id="powershell", index=2, name="PowerShell Download Cradle", mitre="T1059.001", stage_kind="simulated",
        briefing="PowerShell runs an encoded download cradle and pulls the loader into memory from a "
                 "newly-registered staging domain. The host is now COMPROMISED — but only if 4104 "
                 "script-block logging is on can the SOC see it.",
        attacker_goal="Fetch and launch the loader in memory.",
        victim_experience="Faint disk/CPU activity; otherwise invisible.",
        soc_signal="PowerShell 4104: encoded command + IEX/DownloadString indicators + DNS to a new "
                   "domain. Signal: MEDIUM–HIGH (coverage gap if 4104 is disabled).",
        tasks=(
            GuidedTask(id="ps_red_cradle", role="red", kind="sim_red",
                label="Run the download cradle",
                does="PowerShell pulls the loader into memory from the staging domain.",
                how="Simulated encoded-command cradle (4104 indicators) + DNS to a newly-registered domain.",
                outcome="Host COMPROMISED; the loader is resident in memory."),
            GuidedTask(id="ps_soc_4104", role="soc", kind="soc", mitigates="early_detect",
                label="Alert on encoded PowerShell",
                does="Catch the 4104 script-block with encoded-command + download-cradle indicators.",
                how="Script-block logging (4104) + newly-registered-domain network rule.",
                outcome="A precise signal on the loader — teaches the cost of telemetry gaps if 4104 is off."),
            GuidedTask(id="ps_blue_dns", role="blue", kind="blue", mitigates="contain",
                label="Block the staging domain",
                does="Sinkhole/deny the loader's staging + future C2 domain.",
                how="DNS / proxy egress block of the newly-registered domain.",
                outcome="Cuts the loader fetch and pre-empts the coming C2 channel."),
        ),
        network_effect={"state": "infected"},
    ),
    GuidedPhase(
        id="persistence", index=3, name="Scheduled Task Persistence", mitre="T1053.005", stage_kind="simulated",
        briefing="A masquerading scheduled task (\\UpdateOrchestrator\\NWUpdate) relaunches the loader at "
                 "logon. The foothold now survives reboot — a process-kill alone won't clean it.",
        attacker_goal="Persist across reboots.",
        victim_experience="Nothing visible.",
        soc_signal="Security EID 4698: new scheduled task with a masquerading name running a script "
                   "interpreter. Signal: MEDIUM.",
        tasks=(
            GuidedTask(id="pe_red_task", role="red", kind="sim_red",
                label="Create a masquerading scheduled task",
                does="Register an UpdateOrchestrator task that relaunches the loader at logon.",
                how="Simulated task-creation (Security EID 4698, AtLogon trigger, T1053.005).",
                outcome="The foothold survives reboot — eradication now needs more than a kill."),
            GuidedTask(id="pe_soc_4698", role="soc", kind="soc", mitigates="early_detect",
                label="Raise the new-scheduled-task alert",
                does="Detect the masquerading-name task running a script interpreter.",
                how="4698 task-creation monitoring against a baseline of normal tasks.",
                outcome="A reliable mid-funnel persistence tell."),
            GuidedTask(id="pe_blue_remove", role="blue", kind="blue", mitigates="contain",
                label="Remove persistence on the host",
                does="Delete the scheduled task and kill the loader.",
                how="EDR remediation of the persistence mechanism.",
                outcome="Stops reboot re-launch — but only full cleanup (task+beacon+creds) truly evicts."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="injection", index=4, name="Process Injection", mitre="T1055.012", stage_kind="simulated",
        briefing="The beacon is injected into a trusted svchost.exe context. Killing PowerShell no longer "
                 "kills the beacon — this is where EDR clearly outperforms a log-only SOC.",
        attacker_goal="Run the beacon inside a trusted process to evade inspection.",
        victim_experience="Nothing visible.",
        soc_signal="EDR behavioral: cross-process thread injection into a system binary; later C2 appears "
                   "to originate from svchost. Signal: HIGH (behavioral).",
        tasks=(
            GuidedTask(id="in_red_inject", role="red", kind="sim_red",
                label="Inject the beacon into svchost",
                does="Move the beacon into a legitimate svchost.exe context.",
                how="Simulated remote-thread injection (EDR behavioral, T1055.012).",
                outcome="Killing PowerShell no longer kills the beacon — eradication difficulty rises."),
            GuidedTask(id="in_soc_edr", role="soc", kind="soc", mitigates="early_detect",
                label="Catch the cross-process injection",
                does="Spot the anomalous thread into a system binary (parent/owner mismatch).",
                how="EDR behavioral injection detection.",
                outcome="A high-confidence behavioral signal a log-only SOC would miss."),
            GuidedTask(id="in_blue_kill", role="blue", kind="blue", mitigates="contain",
                label="Kill the beacon process state",
                does="Terminate the injected beacon thread.",
                how="EDR process kill on the svchost beacon.",
                outcome="Removes hands-on-keyboard — but persistence may re-establish if not also removed."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="c2", index=5, name="Command & Control", mitre="T1071.001", stage_kind="simulated",
        briefing="The beacon checks into C2 over HTTPS on a jittered interval — the operator now has an "
                 "interactive session. Blocking the C2 destination here severs hands-on-keyboard.",
        attacker_goal="Establish reliable interactive remote control.",
        victim_experience="None visible; small periodic network traffic.",
        soc_signal="Network: periodic low-variance HTTPS beacon to a newly-seen destination. Signal: "
                   "MEDIUM–HIGH (beacon analytics / JA3 / NRD reputation).",
        tasks=(
            GuidedTask(id="c2_red_beacon", role="red", kind="sim_red",
                label="Establish the HTTPS beacon",
                does="Beacon checks into C2 on a jittered interval, enabling hands-on-keyboard.",
                how="Simulated periodic HTTPS beacon (T1071.001) to a newly-seen domain.",
                outcome="Interactive session live — the operator can now drive lateral movement."),
            GuidedTask(id="c2_soc_beacon", role="soc", kind="soc", mitigates="early_detect",
                label="Detect the beaconing pattern",
                does="Spot the low-variance periodic egress to a new destination.",
                how="Beacon-interval analytics + JA3/TLS fingerprint + NRD reputation.",
                outcome="Identifies the C2 domain for Blue to sever."),
            GuidedTask(id="c2_blue_block", role="blue", kind="blue", mitigates="contain",
                label="Block the C2 destination",
                does="Sever the beacon at the egress.",
                how="Proxy/DNS block of the C2 domain.",
                outcome="Operator loses hands-on-keyboard (DP-3) — then eradicate the host."),
        ),
        decision_point=DecisionPoint(id="DP-3", prompt="Periodic beaconing to a new destination.",
            detect="Beacon analytics alert", investigate="Confirm the C2 domain",
            contain="Block the C2 destination", eradicate="Full host remediation",
            inaction="The operator gains hands-on-keyboard and begins discovery."),
        network_effect={"state": "propagating"},
    ),
    GuidedPhase(
        id="discovery", index=6, name="File & Host Discovery", mitre="T1083", stage_kind="real",
        briefing="Hands-on-keyboard, the operator enumerates shares, hosts and the over-privileged "
                 "svc_backup account — building the reachable-asset list (FS01/BKP01/DC01). This recon "
                 "burst is a strong early-internal signal that's often missed.",
        attacker_goal="Locate valuable data, shares and high-value targets.",
        victim_experience="None visible.",
        soc_signal="Unusual share enumeration by a Finance user + recon-command burst (honey-token share "
                   "access). Signal: LOW–MEDIUM — the last quiet warning before lateral movement.",
        tasks=(
            GuidedTask(id="ds_red_enum", role="red", kind="real_tool",
                action_id="intrecon.identity_graph", tool="NetExec",
                label="Enumerate reachable shares & hosts",
                does="Map file shares, hosts and high-value servers from the foothold.",
                how="REAL NetExec SMB enumeration (nxc smb --shares) against the file target (T1083).",
                outcome="Builds the reachable-asset list (FS01/BKP01/DC01) and reveals exposed files."),
            GuidedTask(id="ds_red_sweep", role="red", kind="real_tool",
                action_id="intrecon.network", tool="nmap", optional=True,
                label="Sweep for reachable hosts",
                does="Discover live internal hosts from the foothold.",
                how="REAL nmap host sweep (nmap -sn) across the reachable subnet.",
                outcome="Expands the target map for lateral movement."),
            GuidedTask(id="ds_soc_recon", role="soc", kind="soc", mitigates="early_detect",
                label="Flag the recon / share-enum burst",
                does="Notice the unusual share enumeration by a Finance user.",
                how="Recon-command detection + anomalous-share-access-by-role (honey-token shares).",
                outcome="A strong early-internal signal — the last quiet warning before lateral movement."),
            GuidedTask(id="ds_blue_scope", role="blue", kind="blue", mitigates="isolate",
                label="Scope & isolate before lateral movement",
                does="Scope the foothold and isolate it before it pivots to servers.",
                how="EDR isolation of the compromised host + blast-radius scoping.",
                outcome="Contains the intrusion before it reaches the servers (DP-4)."),
        ),
        decision_point=DecisionPoint(id="DP-4", prompt="Recon / share-enumeration burst from a Finance host.",
            detect="Recon-command alert", investigate="Scope reachable assets",
            contain="Scope + isolate the foothold", eradicate="Remove the foothold",
            inaction="The operator moves laterally to the servers."),
        network_effect={},
    ),
    GuidedPhase(
        id="lateral", index=7, name="Lateral Movement (RDP)", mitre="T1021.001", stage_kind="real",
        briefing="Using the over-privileged svc_backup credential, the operator reaches FS01, BKP01 and "
                 "DC01. Disabling the account or isolating the servers here is the last clean save before "
                 "encryption.",
        attacker_goal="Reach and control the high-value servers.",
        victim_experience="None on patient zero; the target servers are now compromised.",
        soc_signal="Security 4624 type-10: workstation→server RDP using a service account. Signal: HIGH "
                   "(service-account interactive logon, workstation→multiple-servers pattern).",
        tasks=(
            GuidedTask(id="lm_red_auth", role="red", kind="real_tool",
                action_id="access.valid_creds", tool="NetExec",
                label="Authenticate to the server with harvested creds",
                does="Use the over-privileged svc_backup credential to reach the file/backup/DC servers.",
                how="REAL NetExec credential authentication (nxc smb -u … -p …) against the file target.",
                outcome="High-value footholds — the spread radius grows toward the backups and the DC."),
            GuidedTask(id="lm_soc_rdp", role="soc", kind="soc", mitigates="early_detect",
                label="Detect workstation→server RDP by a service account",
                does="Catch the logon-type-10 from a workstation to servers using svc_backup.",
                how="Service-account interactive-logon + workstation→server RDP anomaly (4624 type 10).",
                outcome="A high-confidence lateral-movement signal — the last clean save before impact."),
            GuidedTask(id="lm_blue_disable", role="blue", kind="blue", mitigates="segment",
                label="Disable the abused account + isolate servers",
                does="Disable svc_backup and isolate FS01/BKP01/DC01.",
                how="Account disable + server EDR isolation.",
                outcome="Stops the spread before encryption (DP-5)."),
        ),
        decision_point=DecisionPoint(id="DP-5", prompt="RDP lateral movement to servers via svc_backup.",
            detect="Lateral-movement alert", investigate="Map compromised servers",
            contain="Disable account + isolate servers", eradicate="Reset the service credential",
            inaction="The operator stages the encryptor on the servers."),
        network_effect={"infect": 6, "state": "propagating"},
    ),
    GuidedPhase(
        id="encrypt", index=8, name="Data Encrypted for Impact", mitre="T1486", stage_kind="simulated",
        briefing="The encryptor is staged to the compromised hosts and detonated over a synthetic file "
                 "set — files become .locked, a ransom note drops, wallpaper changes. Detection here is "
                 "late: high impact is already incurred.",
        attacker_goal="Encrypt data across reachable systems to force payment.",
        victim_experience="Files turn to .locked; wallpaper switches to a ransom message; "
                          "README_RESTORE.txt opens automatically; the user is locked out of work.",
        soc_signal="EDR: mass file-modification (rename burst, .locked) + canary/honeyfile trigger + "
                   "ransom-note signature. Signal: CRITICAL — ransomware confirmed.",
        tasks=(
            GuidedTask(id="en_red_encrypt", role="red", kind="sim_red",
                label="Stage & detonate the encryptor",
                does="Push the encryptor to compromised hosts and detonate over a synthetic file set.",
                how="Simulated mass file-rename to .locked + ransom note (T1486) — no real cryptography.",
                outcome="Shared data inaccessible; business operations halt."),
            GuidedTask(id="en_soc_canary", role="soc", kind="soc",
                label="Fire the mass-modification / canary alert",
                does="Confirm ransomware from the mass rename + honeyfile trigger.",
                how="Mass-modification rate threshold + ransom-note signature + canary file.",
                outcome="Confirms impact — detection here only limits blast radius, not local damage."),
            GuidedTask(id="en_blue_isolate", role="blue", kind="blue", mitigates="contain",
                label="Mass-isolate + invoke IR",
                does="Quarantine encrypting hosts and declare a major incident.",
                how="Bulk EDR isolation + IR activation.",
                outcome="Limits the encryption blast radius to already-hit hosts (DP-6)."),
        ),
        decision_point=DecisionPoint(id="DP-6", prompt="Mass file-modification (ransomware behaviour).",
            detect="Mass-modification alert", investigate="Scope encrypted hosts",
            contain="Mass-isolate + invoke IR", eradicate="Begin restore from clean backups",
            inaction="Encryption spreads across reachable hosts."),
        network_effect={"encrypt_all": True, "state": "impacted"},
    ),
    GuidedPhase(
        id="inhibit", index=9, name="Inhibit Recovery & Aftermath", mitre="T1490", stage_kind="simulated",
        briefing="The operator deletes shadow copies and tampers the backup catalog on BKP01 — turning a "
                 "recoverable incident into a potential-payment one. If you protected the backups in time, "
                 "you still recover; if not, the outage extends.",
        attacker_goal="Prevent restoration to force ransom payment.",
        victim_experience="Even IT cannot quickly restore; the outage extends; an 'incident' contact "
                          "channel appears.",
        soc_signal="Sysmon/EDR: vssadmin/wbadmin shadow-copy deletion + backup-service tamper. Signal: "
                   "CRITICAL — a well-known high-fidelity ransomware tell.",
        tasks=(
            GuidedTask(id="ih_red_shadow", role="red", kind="sim_red",
                label="Delete shadow copies & tamper backups",
                does="Wipe shadow copies and the backup catalog on BKP01.",
                how="Simulated vssadmin/wbadmin + backup-service tamper (T1490).",
                outcome="Converts a recoverable incident into a potential-payment / extended-outage one."),
            GuidedTask(id="ih_soc_shadow", role="soc", kind="soc", mitigates="early_detect",
                label="Alert on shadow-copy deletion & backup tamper",
                does="Catch the vssadmin/wbadmin commands and the backup-service stop.",
                how="Shadow-deletion command detection + backup-service-stop monitoring.",
                outcome="A high-fidelity ransomware tell — caught in time, recovery survives."),
            GuidedTask(id="ih_blue_backups", role="blue", kind="blue", mitigates="backups",
                label="Protect / disconnect the backups",
                does="Air-gap or disconnect the backups before they're tampered.",
                how="Immutable / offline backup isolation (works only if reached in time).",
                outcome="Preserves recovery — restore stays possible."),
            GuidedTask(id="ih_blue_restore", role="blue", kind="blue", mitigates="restore",
                label="Restore impacted systems from clean backups",
                does="Rebuild and restore impacted hosts once the bleeding has stopped.",
                how="Reimage + restore from the preserved offline backups.",
                outcome="The only path that recovers data after encryption."),
        ),
        decision_point=DecisionPoint(id="DP-7", prompt="Shadow-copy deletion / backup tampering.",
            detect="Shadow-deletion alert", investigate="Confirm backup state",
            contain="Protect / disconnect the backups", eradicate="Full remediation + restore",
            inaction="recovery_available=false — the max-impact path locks in."),
        network_effect={"recovery_disabled": True, "state": "impacted"},
    ),
)

R5 = GuidedScenario(
    id="scn-r5-phishing",
    name="Phishing to Encrypt",
    subtitle="Human-Operated Ransomware Campaign",
    summary="A targeted phish to a Finance user (corp.northwind.local, 85 hosts) becomes macro execution, "
            "an in-memory loader, persistence, a beacon, and — via an over-privileged service account — "
            "lateral movement to the file server, DC and backups, then enterprise encryption. Run the real "
            "discovery + credentialed reach (NetExec) from Kali; everything before and after is simulated. "
            "The lesson: every earlier break is cheaper than the last.",
    total_hosts=85,
    phases=_R5_PHASES,
    mitre_chain=("T1566.001", "T1204.002", "T1059.001", "T1053.005", "T1055.012", "T1071.001",
                 "T1083", "T1021.001", "T1486", "T1490"),
)


# ===========================================================================
#  C5 — Attacker piggybacks on an EDR outage (from "C5_EDR_Outage_Scenario.pdf")
# ===========================================================================
# Human-operated ransomware on a 500-host enterprise during an EDR-vendor outage. The teaching
# twist: EDR is BLIND, so the highest-fidelity detections (credential dump, shadow deletion) are
# invisible — defenders must fall back to netflow / auth / proxy / Sysmon. Real on the Docker
# range: the password-spray credential check and the network-discovery enumeration; the rest is
# simulated (and the AD-credential stages stay narrated since this is the Docker-only lab).

_C5_PHASES: tuple[GuidedPhase, ...] = (
    GuidedPhase(
        id="outage", index=0, name="EDR Outage & Targeting", mitre="T1592", stage_kind="simulated",
        briefing="An EDR vendor pushes a faulty update; sensors crash fleet-wide and visibility "
                 "collapses. A human-operated crew spots the outage and lines you up as a target. The "
                 "single most important move now is restoring visibility before they move.",
        attacker_goal="Identify the exploitable visibility gap and build a target list.",
        victim_experience="Security teams warn that endpoint protection is degraded; users keep working "
                          "as normal, unaware.",
        soc_signal="EDR agent-heartbeat failures + service crashes. Signal: HIGH / obvious — but it's the "
                   "outage, not the attacker; everything downstream gets quieter.",
        tasks=(
            GuidedTask(id="o_red_osint", role="red", kind="sim_red",
                label="Spot the outage & build a target list",
                does="Monitor OSINT for the EDR vendor's bad-update outage and enumerate orgs running blind.",
                how="OSINT gathering (T1592) — no telemetry; purely external recon.",
                outcome="A prioritised target list with confirmed EDR blindness — the attack window opens."),
            GuidedTask(id="o_soc_health", role="soc", kind="soc", mitigates="early_detect",
                label="Confirm the EDR agent-health collapse",
                does="Notice the mass agent-heartbeat failures and sensor crashes.",
                how="Monitor EDR agent health / service crashes (the one HIGH, obvious signal).",
                outcome="Confirms the outage scope — the trigger to deploy alternative monitoring fast."),
            GuidedTask(id="o_blue_altmon", role="blue", kind="blue", mitigates="early_detect",
                label="Deploy alternative monitoring",
                does="Stand up Sysmon + network sensors to replace the lost EDR visibility.",
                how="Push a Sysmon GPO + enable netflow / auth-log forwarding — the highest-leverage C5 move.",
                outcome="Restores partial visibility for the blind window (DP-1); without it you fight blind."),
        ),
        decision_point=DecisionPoint(id="DP-1", prompt="EDR failure — fleet-wide visibility lost.",
            detect="Monitor agent health", investigate="Check vendor status",
            contain="Enable audit logging / segment", eradicate="Deploy alternative tools (Sysmon/netflow)",
            inaction="A 12-hour blind window the attacker owns."),
        network_effect={"state": "infected"},
    ),
    GuidedPhase(
        id="spray", index=1, name="Password Spray", mitre="T1110", stage_kind="real",
        briefing="With defenders distracted by the outage, the crew sprays common passwords against the "
                 "external auth portals. A single valid credential is the key to the front door.",
        attacker_goal="Obtain valid authentication credentials.",
        victim_experience="Occasional unusual authentication prompts; otherwise nothing visible.",
        soc_signal="Failed-auth spike + account lockouts in Azure/AD logs. Signal: MEDIUM — often lost in "
                   "noise.",
        tasks=(
            GuidedTask(id="sp_red_spray", role="red", kind="real_tool",
                action_id="access.valid_creds", tool="NetExec",
                label="Spray for valid credentials",
                does="Low-and-slow spray common passwords against the auth portals to find one that works.",
                how="REAL NetExec credential check (nxc smb -u … -p …) against the target — a landed spray.",
                outcome="A valid credential pair — the key to the front door."),
            GuidedTask(id="sp_soc_authspike", role="soc", kind="soc", mitigates="early_detect",
                label="Catch the failed-auth spike",
                does="Spot the failed-authentication spike and lockouts in the cloud auth logs.",
                how="Auth-anomaly / impossible-travel detection (Medium signal, easily missed in noise).",
                outcome="The earliest cloud-side warning — catch it and force MFA before a credential lands."),
            GuidedTask(id="sp_blue_mfa", role="blue", kind="blue", mitigates="isolate",
                label="Force global MFA + password reset",
                does="Enforce MFA on all accounts and reset exposed passwords.",
                how="Emergency MFA enforcement + scoped password reset (DP-2).",
                outcome="Invalidates sprayed credentials before they're used — stops initial compromise."),
        ),
        decision_point=DecisionPoint(id="DP-2", prompt="Authentication anomalies (spray pattern).",
            detect="Review auth logs", investigate="Correlate failures",
            contain="Global password reset + MFA", eradicate="Reset exposed passwords",
            inaction="Initial compromise via a valid credential."),
        network_effect={"state": "infected"},
    ),
    GuidedPhase(
        id="access", index=2, name="Initial Access (VPN)", mitre="T1078", stage_kind="simulated",
        briefing="The crew logs in over the VPN with the valid credential — a normal-looking session from "
                 "an abnormal place. Disabling the account here is the last cheap save.",
        attacker_goal="Establish network presence with valid credentials.",
        victim_experience="None apparent; a new remote session exists.",
        soc_signal="Successful VPN/RDP logon from an unusual location/time. Signal: LOW–MEDIUM (may flag "
                   "for review).",
        tasks=(
            GuidedTask(id="ia_red_vpn", role="red", kind="sim_red",
                label="Log in over the VPN",
                does="Authenticate to the corporate VPN/RDP with the valid credential.",
                how="Simulated valid-account logon (T1078) — a session from an unusual location.",
                outcome="Initial foothold inside the network."),
            GuidedTask(id="ia_soc_vpn", role="soc", kind="soc", mitigates="early_detect",
                label="Flag the anomalous VPN logon",
                does="Notice the VPN connection from an unusual location / time.",
                how="VPN-anomaly detection (Low–Medium signal).",
                outcome="A chance to verify the user and revoke before the implant lands."),
            GuidedTask(id="ia_blue_revoke", role="blue", kind="blue", mitigates="isolate",
                label="Disable the account + revoke sessions",
                does="Disable the suspicious account and kill its active sessions.",
                how="Account disable + session revoke (DP-3).",
                outcome="Severs the foothold before persistence — the last cheap save."),
        ),
        decision_point=DecisionPoint(id="DP-3", prompt="Suspicious VPN access established.",
            detect="VPN anomaly detection", investigate="Verify user activity",
            contain="Disable remote access / account", eradicate="Revoke sessions",
            inaction="A durable foothold is established."),
        network_effect={"infect": 1, "state": "infected"},
    ),
    GuidedPhase(
        id="c2", index=3, name="C2 / Payload Deployment", mitre="T1055", stage_kind="simulated",
        briefing="A Cobalt-Strike-style implant lands and opens a C2 channel. With EDR down, the beacon "
                 "in network flow is one of the few things you can still see.",
        attacker_goal="Establish persistent remote control.",
        victim_experience="None visible; periodic small network traffic.",
        soc_signal="Periodic C2 callbacks / DNS beaconing in netflow (no EDR to see the process). Signal: "
                   "network-only.",
        tasks=(
            GuidedTask(id="c_red_implant", role="red", kind="sim_red",
                label="Deploy the implant & open C2",
                does="Drop a Cobalt-Strike-style implant and establish a C2 channel.",
                how="Simulated implant + periodic C2 callbacks (T1055) — DNS/HTTPS beacon.",
                outcome="Persistent remote control of the foothold."),
            GuidedTask(id="c_soc_netflow", role="soc", kind="soc", mitigates="early_detect",
                label="Hunt the C2 beacon in netflow",
                does="Find the periodic callbacks in network flow data.",
                how="Netflow beacon analytics + DNS anomaly (one of the few remaining signals).",
                outcome="Identifies the C2 for Blue to isolate — alternative-detection in action."),
            GuidedTask(id="c_blue_isolate", role="blue", kind="blue", mitigates="contain",
                label="Isolate the network from the C2",
                does="Block the C2 and isolate the affected segment.",
                how="Full network isolation / egress block (DP-4).",
                outcome="Cuts hands-on-keyboard before lateral movement."),
        ),
        decision_point=DecisionPoint(id="DP-4", prompt="C2 beaconing detected in netflow.",
            detect="Network anomaly", investigate="Trace the callbacks",
            contain="Full network isolation", eradicate="Block C2 + remediate host",
            inaction="The crew begins lateral movement."),
        network_effect={"state": "infected"},
    ),
    GuidedPhase(
        id="persistence", index=4, name="Persistence Establishment", mitre="T1053", stage_kind="simulated",
        briefing="The crew lays down multiple persistence mechanisms — tasks, WMI subscriptions, services. "
                 "Without EDR, these are extremely hard to see; removing one leaves the others.",
        attacker_goal="Survive reboots and maintain access.",
        victim_experience="None visible.",
        soc_signal="Windows Event Log service/task creation — IF centralised. Signal: VERY LOW (rarely "
                   "collected centrally).",
        tasks=(
            GuidedTask(id="pe_red_persist", role="red", kind="sim_red",
                label="Establish multiple persistence mechanisms",
                does="Create scheduled tasks, WMI subscriptions and services to survive reboot.",
                how="Simulated multi-mechanism persistence (T1053).",
                outcome="Entrenched — removing one mechanism leaves the others."),
            GuidedTask(id="pe_soc_manual", role="soc", kind="soc",
                label="Manually hunt new tasks/services",
                does="Manually check the few centralised Windows logs for new tasks/services.",
                how="Manual system checks (extremely limited without EDR).",
                outcome="A faint, easily-missed tell — illustrates the visibility gap."),
            GuidedTask(id="pe_blue_reimage", role="blue", kind="blue", mitigates="contain",
                label="Network-isolate & queue reimage",
                does="Isolate the entrenched host and queue it for a rebuild.",
                how="Network isolation + reimage planning.",
                outcome="Contains the host; full eradication needs a clean rebuild."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="evasion", index=5, name="Defence Evasion", mitre="T1562", stage_kind="simulated",
        briefing="The crew disables what logging remains and clears event logs, living off legitimate "
                 "tools. The blind window gets darker — but 'the logs went quiet' is itself a signal.",
        attacker_goal="Avoid the remaining detection.",
        victim_experience="None visible; security posture quietly degrades.",
        soc_signal="Event-log clearing / logging-service stops — IF noticed. Signal: log gaps themselves.",
        tasks=(
            GuidedTask(id="ev_red_clear", role="red", kind="sim_red",
                label="Disable logging & clear event logs",
                does="Turn off logging and clear event logs, using legitimate tools to blend in.",
                how="Simulated log tampering (T1562) — log gaps / service stops.",
                outcome="Shrinks the already-degraded detection surface further."),
            GuidedTask(id="ev_soc_gaps", role="soc", kind="soc", mitigates="early_detect",
                label="Alert on log gaps & service stops",
                does="Detect suspicious logging-service stops and event-log clears.",
                how="Log-integrity monitoring (the absence of logs is the indicator).",
                outcome="'The logs went quiet' is itself a tell — one of the last alternative signals."),
            GuidedTask(id="ev_blue_forward", role="blue", kind="blue", mitigates="early_detect",
                label="Re-enable & forward logs off-host",
                does="Restore logging and forward logs to the SIEM out of the attacker's reach.",
                how="Re-enable audit policy + off-host log forwarding.",
                outcome="Denies the attacker their blindness and preserves evidence."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="creddump", index=6, name="Credential Dumping", mitre="T1003", stage_kind="simulated",
        briefing="The crew dumps LSASS and runs DCSync to reach Domain Admin. This is the most important "
                 "detection in the whole chain — and it is COMPLETELY invisible without EDR. The lesson of "
                 "EDR dependency, in one stage.",
        attacker_goal="Escalate to domain-admin privileges.",
        victim_experience="None visible.",
        soc_signal="Nothing — EDR would catch this; without it you are completely blind (subtle DCSync "
                   "traffic at best).",
        tasks=(
            GuidedTask(id="cd_red_dump", role="red", kind="sim_red",
                label="Dump credentials → Domain Admin",
                does="Harvest credentials from LSASS/SAM and DCSync to reach Domain Admin.",
                how="Simulated LSASS dump + DCSync (T1003) — invisible without EDR (Docker-only: narrated).",
                outcome="Domain-admin credentials — total compromise of the identity plane."),
            GuidedTask(id="cd_soc_blind", role="soc", kind="soc",
                label="Acknowledge the blind spot",
                does="Recognise that credential dumping is completely invisible without EDR.",
                how="There is no signal — only post-hoc DCSync replication traffic might hint.",
                outcome="Teaches the cost of EDR dependency — the most critical detection is simply gone."),
            GuidedTask(id="cd_blue_rotate", role="blue", kind="blue", mitigates="contain",
                label="Rotate all credentials + krbtgt ×2",
                does="Rotate all credentials and reset krbtgt twice.",
                how="Domain-wide credential rotation (the only response to an unseen dump).",
                outcome="Invalidates harvested credentials/tickets — blunts the privilege just gained."),
        ),
        network_effect={"state": "propagating"},
    ),
    GuidedPhase(
        id="discovery", index=7, name="Network Discovery", mitre="T1018", stage_kind="real",
        briefing="With domain admin, the crew maps the whole estate — AD, hosts, shares. The LDAP/SMB "
                 "noise is one of the few things still visible in netflow.",
        attacker_goal="Map the environment and locate the crown jewels.",
        victim_experience="Minor network-drive slowdowns from the scanning.",
        soc_signal="LDAP query bursts + SMB enumeration in netflow. Signal: LOW (needs correlation).",
        tasks=(
            GuidedTask(id="di_red_enum", role="red", kind="real_tool",
                action_id="intrecon.identity_graph", tool="NetExec",
                label="Map the domain & shares",
                does="Enumerate AD, hosts and shares to build a complete infrastructure map.",
                how="REAL NetExec SMB enumeration (nxc smb --shares) against the target (T1018).",
                outcome="An omniscient map of targets and sensitive shares to collect from."),
            GuidedTask(id="di_red_sweep", role="red", kind="real_tool",
                action_id="intrecon.network", tool="nmap", optional=True,
                label="Sweep the internal subnet",
                does="Discover live internal hosts across the reachable subnet.",
                how="REAL nmap host sweep (nmap -sn).",
                outcome="Expands the target map for lateral movement."),
            GuidedTask(id="di_soc_ldap", role="soc", kind="soc", mitigates="early_detect",
                label="Spot unusual AD-query / scan patterns",
                does="Notice the spike in LDAP queries and internal SMB scanning.",
                how="AD-enumeration + internal-scan detection in the remaining logs/netflow.",
                outcome="An alternative-detection signal that the intrusion is mapping the estate."),
            GuidedTask(id="di_blue_segment", role="blue", kind="blue", mitigates="segment",
                label="Segment the network",
                does="Cut east-west paths to wall off the discovery and what comes next.",
                how="Emergency network segmentation.",
                outcome="Limits how far the attacker can reach in the next stage."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="lateral", index=8, name="Lateral Movement", mitre="T1021", stage_kind="simulated",
        briefing="Domain-admin in hand, the crew spreads via RDP/PSExec/WMI. Without EDR the only trace is "
                 "the east-west RDP/SMB pattern in netflow.",
        attacker_goal="Spread across the environment.",
        victim_experience="More performance impact as adjacent systems are touched.",
        soc_signal="RDP/SMB connections in netflow; unusual admin-tool usage. Signal: LOW (requires "
                   "correlation).",
        tasks=(
            GuidedTask(id="la_red_spread", role="red", kind="sim_red",
                label="Spread with domain-admin creds",
                does="Move to adjacent systems via RDP/PSExec/WMI using the harvested admin creds.",
                how="Simulated lateral movement (T1021) — RDP/SMB in netflow.",
                outcome="Multi-system compromise; the spread goes wide."),
            GuidedTask(id="la_soc_correlate", role="soc", kind="soc", mitigates="early_detect",
                label="Correlate unusual admin-tool usage",
                does="Track the east-west RDP/SMB pattern across hosts.",
                how="Netflow correlation of admin-tool usage (the weak, correlation-heavy signal).",
                outcome="A signal that requires real work — catch it to scope the spread."),
            GuidedTask(id="la_blue_protocols", role="blue", kind="blue", mitigates="segment",
                label="Disable protocols + segment further",
                does="Restrict RDP/SMB between segments and isolate the hot zones.",
                how="Protocol disable + tighter segmentation.",
                outcome="Slows the widespread compromise before collection."),
        ),
        network_effect={"infect": 20, "state": "propagating"},
    ),
    GuidedPhase(
        id="collection", index=9, name="Data Collection", mitre="T1074", stage_kind="simulated",
        briefing="The crew auto-searches for financial data, PII and IP, staging it in temp folders. This "
                 "is double-extortion: they steal before they encrypt.",
        attacker_goal="Identify and stage valuable data.",
        victim_experience="Network-drive slowdowns from the staging operations.",
        soc_signal="Mass file-access patterns + internal transfer spikes (file-server audit, if enabled). "
                   "Signal: VERY LOW.",
        tasks=(
            GuidedTask(id="co_red_stage", role="red", kind="sim_red",
                label="Discover & stage sensitive data",
                does="Auto-search for financial/PII/IP and stage it in %TEMP%/public folders.",
                how="Simulated findstr/PowerShell collection (T1074).",
                outcome="Hundreds of GB staged for theft."),
            GuidedTask(id="co_soc_access", role="soc", kind="soc", mitigates="early_detect",
                label="Flag mass file-access patterns",
                does="Spot the abnormal volume of file access and internal transfer spikes.",
                how="File-server audit-log review (where enabled).",
                outcome="A chance to revoke access before exfiltration starts."),
            GuidedTask(id="co_blue_revoke", role="blue", kind="blue", mitigates="contain",
                label="Revoke permissions + audit shares",
                does="Pull access to the sensitive shares and audit who touched them.",
                how="Permission revocation + share audit.",
                outcome="Cuts the collection before it can leave the network."),
        ),
        network_effect={},
    ),
    GuidedPhase(
        id="exfil", index=10, name="Data Exfiltration", mitre="T1567", stage_kind="simulated",
        briefing="The staged data is compressed, encrypted and uploaded to cloud storage over HTTPS. "
                 "Large outbound HTTPS to a new cloud domain is the clearest network-only signal you'll get.",
        attacker_goal="Steal the sensitive data.",
        victim_experience="None directly; sustained upload traffic in the background.",
        soc_signal="Large outbound HTTPS to a new cloud destination; sustained uploads. Signal: MEDIUM "
                   "(may trigger DLP).",
        tasks=(
            GuidedTask(id="ex_red_upload", role="red", kind="sim_red",
                label="Exfiltrate to cloud storage",
                does="Compress, encrypt and upload the staged data to cloud storage over HTTPS.",
                how="Simulated large outbound HTTPS to a new cloud domain (T1567).",
                outcome="Data theft complete — double-extortion leverage secured."),
            GuidedTask(id="ex_soc_dlp", role="soc", kind="soc", mitigates="early_detect",
                label="Catch the large outbound HTTPS",
                does="Detect the sustained outbound uploads to a new cloud destination.",
                how="Proxy log analysis + DLP (a Medium signal that may trigger).",
                outcome="The clearest network-only signal — quantify and block the loss."),
            GuidedTask(id="ex_blue_killegress", role="blue", kind="blue", mitigates="contain",
                label="Block the destination / kill egress",
                does="Block the exfil destinations or pull the internet for the affected segment.",
                how="Proxy/egress block / internet kill-switch (DP-5).",
                outcome="Stops further data leaving."),
        ),
        decision_point=DecisionPoint(id="DP-5", prompt="Large data transfer to cloud storage.",
            detect="Proxy/DLP alert", investigate="Quantify data loss",
            contain="Internet kill-switch / block destination", eradicate="—",
            inaction="Data theft completes."),
        network_effect={"state": "propagating"},
    ),
    GuidedPhase(
        id="inhibit", index=11, name="Disable Recovery", mitre="T1490", stage_kind="simulated",
        briefing="Before encrypting, the crew disables VSS via GPO, stops backup services and corrupts "
                 "online backups. Without EDR this is invisible — backup-system alarms are your only warning.",
        attacker_goal="Eliminate recovery options.",
        victim_experience="None visible yet.",
        soc_signal="Nothing from EDR; backup-system's own alerts are the only tell. Signal: critical "
                   "signal lost.",
        tasks=(
            GuidedTask(id="ir_red_backups", role="red", kind="sim_red",
                label="Delete shadow copies & corrupt backups",
                does="Disable VSS via GPO, stop backup services and corrupt online backups.",
                how="Simulated shadow-copy deletion + backup tamper (T1490) — invisible without EDR.",
                outcome="Recovery options eliminated — maximising ransom pressure."),
            GuidedTask(id="ir_soc_backupalarm", role="soc", kind="soc",
                label="Watch the backup-system alerts",
                does="Rely on the backup system's own alarms (no EDR signal exists).",
                how="Backup-system alert monitoring (the only remaining tell).",
                outcome="A narrow window — backup alarms are the last warning before encryption."),
            GuidedTask(id="ir_blue_offline", role="blue", kind="blue", mitigates="backups",
                label="Isolate offline backups",
                does="Disconnect / immutable-lock the backups before they're corrupted.",
                how="Offline backup isolation (DP-6).",
                outcome="Preserves recovery — the difference between rebuild and ruin."),
        ),
        decision_point=DecisionPoint(id="DP-6", prompt="Backup-system alarms / shadow deletion.",
            detect="Backup system alerts", investigate="Verify backup status",
            contain="Offline backup isolation", eradicate="Protect / disconnect backups",
            inaction="Recovery becomes impossible."),
        network_effect={"recovery_disabled": True, "state": "encrypting"},
    ),
    GuidedPhase(
        id="ransom", index=12, name="Ransomware Deployment & Impact", mitre="T1486", stage_kind="simulated",
        briefing="Using domain admin, the crew mass-deploys the encryptor via GPO/PSExec — servers first. "
                 "Systems turn red across the estate; extortion and a data-leak threat follow. It's now "
                 "response and recovery, not prevention.",
        attacker_goal="Encrypt the enterprise and extort payment.",
        victim_experience="Sudden file unavailability; wallpaper changes to a ransom note; complete "
                          "system lockout; employees arrive to chaos.",
        soc_signal="Mass file modifications + CPU/disk spike; backup failures; help-desk surge. Signal: "
                   "HIGH / CRITICAL — too late to prevent.",
        tasks=(
            GuidedTask(id="rn_red_deploy", role="red", kind="sim_red",
                label="Mass-deploy ransomware via GPO",
                does="Push the encryptor domain-wide via GPO/PSExec, servers first.",
                how="Simulated GPO mass encryption (T1486) — mass file modification + CPU/disk spike.",
                outcome="Enterprise-wide encryption; operations halt; extortion + data-leak threats begin."),
            GuidedTask(id="rn_soc_declare", role="soc", kind="soc",
                label="Declare the major incident",
                does="Confirm mass encryption from file-audit events and the help-desk surge.",
                how="File-audit events + backup failures (HIGH, but too late to prevent).",
                outcome="Incident declared — the engagement is now response and recovery."),
            GuidedTask(id="rn_blue_segment", role="blue", kind="blue", mitigates="segment",
                label="Full segmentation to stop the spread",
                does="Segment everything to stop encryption reaching clean systems.",
                how="Emergency network segmentation (DP-7).",
                outcome="Limits the final blast radius to already-hit systems."),
            GuidedTask(id="rn_blue_restore", role="blue", kind="blue", mitigates="restore",
                label="Clean rebuild + restore from backups",
                does="Rebuild impacted systems and restore from the preserved offline backups.",
                how="Clean rebuild + restore (avoid quick-restore reinfection).",
                outcome="The only path back after encryption — possible only if backups were saved."),
        ),
        decision_point=DecisionPoint(id="DP-7", prompt="Mass encryption beginning.",
            detect="Mass file changes", investigate="Assess damage",
            contain="Network segmentation + full isolation", eradicate="Clean rebuild + restore",
            inaction="Enterprise-wide encryption and total operational failure."),
        network_effect={"encrypt_all": True, "state": "impacted"},
    ),
)

C5 = GuidedScenario(
    id="scn-c5-edr",
    name="EDR Outage Exploitation",
    subtitle="Attacking During Blindness",
    summary="A faulty EDR update blinds a 500-host enterprise, and a human-operated crew piggybacks on "
            "the outage: password spray → VPN access → C2 → invisible credential dumping → discovery → "
            "lateral movement → data theft → backup destruction → enterprise ransomware. Run the real "
            "spray + discovery (NetExec/nmap) from Kali; the rest is simulated. The lesson: when your "
            "best sensor goes dark, alternative detection and fast containment are everything.",
    total_hosts=500,
    phases=_C5_PHASES,
    mitre_chain=("T1592", "T1110", "T1078", "T1055", "T1053", "T1562", "T1003",
                 "T1018", "T1021", "T1074", "T1567", "T1490", "T1486"),
)


# ===========================================================================
#  Registry
# ===========================================================================
GUIDED_SCENARIOS: dict[str, GuidedScenario] = {
    W1.id: W1,
    R5.id: R5,
    C5.id: C5,
}


def get_guided(scenario_id: str) -> GuidedScenario | None:
    return GUIDED_SCENARIOS.get(scenario_id)


def list_guided() -> list[dict]:
    return [s.meta() for s in GUIDED_SCENARIOS.values()]
