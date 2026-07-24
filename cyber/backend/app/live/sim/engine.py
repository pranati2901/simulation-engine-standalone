"""ScenarioSim — the dynamic, tick-based cyber-range engine behind the immersive workspaces.

Rides on a LiveSession (multi-user + WS + manager ticker + live-fire). It owns a `Topology`, per-team
state, an alert queue, and worm flags; teams act through `run_tool`; the worm spreads on `tick`;
auto-driven seats are **telegraphed** (announce intent + countdown so a human can pre-empt); the
outcome **emerges** from how fast the worm spreads vs. how fast SOC detects and Blue contains.

Real Red tools queue a live-fire job (real nmap/NetExec/… against the Docker lab) and ALSO apply their
topology effect; simulated tools only apply the effect + print synthetic terminal output. Nothing
dangerous (worm spread, encryption, shadow deletion) ever touches the lab.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import topology as T
from . import tools as TL

if TYPE_CHECKING:
    from ..session import LiveSession

AUTO_EVERY = 3                  # legacy fallback reaction window (ticks); real delays are now per-action
ROLES = ("soc", "blue", "red")  # defenders telegraph/act before Red each cycle

# --------------------------------------------------------------------------- #
#  Realistic, *non-deterministic* defender timing (each tick ≈ 3s).
#
#  Two delays make auto defenders lag Red instead of shadowing him in lockstep:
#   1) DETECT_LATENCY — mean-time-to-detect: how long before the auto-SOC even *notices* a queued
#      alert (and can start triaging it). High-fidelity signals are seen fast; low-fidelity ones take
#      a long time and are often missed entirely. This is the "you have time before they detect you".
#   2) ACTION_LATENCY — processing / locating time once a seat decides to act (triaging, locating the
#      compromised host to isolate, finding the clean backup to restore, pushing a fleet-wide change…).
#
#  Both are sampled as inclusive (min,max) tick ranges per run, so no two matches play out the same.
# --------------------------------------------------------------------------- #
DETECT_LATENCY: dict[str, tuple[int, int]] = {
    "critical": (2, 5), "high": (4, 8), "medium": (7, 13), "low": (12, 20), "info": (15, 24),
}
ACTION_LATENCY: dict[str, tuple[int, int]] = {
    # Balanced so no team feels disproportionately slow (auto seats share Red's ~initiative band).
    # SOC
    "triage": (3, 5), "escalate": (3, 5), "hunt": (4, 6), "view": (3, 5),
    # Blue
    "isolate": (3, 5), "segment": (3, 5), "sinkhole": (3, 5), "block_c2": (3, 5), "block_egress": (3, 5),
    "patch_all": (4, 6), "patch_hosts": (3, 5), "reset_creds": (4, 6), "disable_cred": (3, 5),
    "protect_backup": (3, 5), "alt_detect": (3, 5), "declare_ir": (3, 5), "restore": (4, 6),
}
RED_ACTION_LATENCY = (3, 5)     # attacker has the initiative, but auto seats now move at a similar pace

# How long a *human-typed* tool takes to actually run (ticks ≈ 3s each), by effect. This lets the
# learner take their time: you type the command, it runs for a few seconds, and only when it
# *completes* does its effect land and its telemetry fire — so detection starts after the command
# finishes, not the instant it's clicked.
#
# TIMING IS DELIBERATELY EQUALISED ACROSS TEAMS (≈12–18s) so Red is no longer the odd one out (it
# used to take ~30s while SOC took ~9s). Every command sits in one tight band; only a handful of
# genuinely heavy jobs (bulk exfiltration, fleet-wide encryption/restore) run a little longer.
_FAST = (3, 5)      # ~9–15s  — quick queries / single-host moves
_STD = (4, 6)       # ~12–18s — the common band most tools use
_HEAVY = (5, 7)     # ~15–21s — bulk / fleet-wide / data-heavy jobs
EXEC_LATENCY: dict[str, tuple[int, int]] = {
    # Red — same band as the defenders now; only bulk exfil / encryption are "heavy"
    "reveal_hosts": _STD, "mark_vulnerable": _STD, "spray": _STD, "deliver_phish": _STD,
    "exploit": _STD, "infect": _STD, "c2_establish": _STD, "cred_dump": _STD,
    "persist": _STD, "killswitch_check": _FAST, "start_propagation": _STD, "cred_propagation": _STD,
    "exfiltrate": _HEAVY, "disable_recovery": _STD, "encrypt": _HEAVY,
    # Blue — containment/eradication in the common band; fleet-wide recovery is heavy
    "isolate": _STD, "segment": _STD, "sinkhole": _STD, "block_c2": _STD, "block_egress": _STD,
    "patch_all": _STD, "patch_hosts": _STD, "reset_creds": _STD, "disable_cred": _STD,
    "protect_backup": _STD, "alt_detect": _STD, "declare_ir": _FAST, "restore": _HEAVY,
    # SOC — queries are quick; a hunt sits in the common band
    "view": _FAST, "triage": _FAST, "escalate": _FAST, "hunt": _STD,
}

# Per-scenario narration for the *dynamic* spread tick (the only narration the engine still owns —
# every other SOC signal is data-driven from the tool's `alert`/`telemetry` fields). Keeps each
# scenario reading as its own story instead of "WannaCry SMB worm" everywhere.
SCENARIO_NARRATION: dict[str, dict] = {
    "scn-wannacry-w1": {
        "spread_title": "Worm spread",
        "spread_text": "{n} hosts infected (R≈{r}) — self-propagating over SMBv1/445",
        "spread_channel": "spread",
        "lateral_alert": ("Lateral movement (multi-source)", "high", "T1021.002"),
    },
    "scn-r5-phishing": {
        "spread_title": "Hands-on-keyboard lateral movement",
        "spread_text": "{n} hosts reached (R≈{r}) — RDP/SMB with the stolen svc_backup account",
        "spread_channel": "network",
        "lateral_alert": ("Anomalous RDP from service account", "high", "T1021.001"),
    },
    "scn-c5-edr": {
        "spread_title": "Mass lateral movement (EDR blind)",
        "spread_text": "{n} hosts reached (R≈{r}) — PsExec with Domain Admin, no EDR to stop it",
        "spread_channel": "network",
        "lateral_alert": ("PsExec service install across many hosts", "high", "T1021.002"),
    },
}


@dataclass
class TeamState:
    score: int = 0
    done: set[str] = field(default_factory=set)     # tool ids ever used (unlock + once gating)


class ScenarioSim:
    def __init__(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id
        _builders = {"scn-wannacry-w1": T.build_w1, "scn-r5-phishing": T.build_r5, "scn-c5-edr": T.build_c5}
        self.topo: T.Topology = _builders.get(scenario_id, T.build_w1)()
        self.tools: dict[str, TL.Tool] = TL.by_id(scenario_id)
        self.teams = {"red": TeamState(), "blue": TeamState(), "soc": TeamState()}
        self.events: list[dict] = []
        self.seq = 0
        self.started_at = time.time()
        self.tick_n = 0
        self.alerts: list[dict] = []
        self.alert_seq = 0
        self.incident_declared: set[str] = set()
        # worm / attack flags
        self.propagating = False
        self.kill_switch: str | None = None           # None | "armed" | "tripped"
        self.segmented = False
        self.smbv1_patched = False
        self.backups_safe = True
        self.r_value = 2.4
        # Generalised kill-chain levers (used by R5/C5; harmless defaults for W1).
        # When propagation is credential-driven (human-operated lateral movement) rather than a
        # vuln-worm, the spread ignores the SMBv1 gate — and Blue can revoke it by resetting creds.
        self.cred_mode = False                         # spread uses valid creds, not a vuln
        self.creds_pwned = False                       # Red holds valid domain creds (gates cred tools)
        self.c2_live = False                           # a Red C2 channel is up (gates C2-dependent tools)
        self.c2_blocked = False                        # Blue cut the C2 channel
        self.exfiltrated = False                       # data exfiltration completed (impact, non-encrypt)
        self.egress_blocked = False                    # Blue blocked the exfil channel (file-sharing sites)
        self._backup_air_gapped = False                # Blue air-gapped backups (they survive encryption)
        self.narr = SCENARIO_NARRATION.get(scenario_id, SCENARIO_NARRATION["scn-wannacry-w1"])
        # the unnamed remainder of the 250-host fleet — tracked as aggregates so the worm can reach
        # real scale (Degraded/Catastrophic) without drawing 250 nodes
        self.extra_infected = 0
        self.extra_impacted = 0
        self.extra_dormant = 0
        self.pending_intents: dict[str, dict] = {}     # role -> {tool_id, params, label, ticks_left}
        self.rng = random.Random()                     # per-session entropy → every match times out differently
        self.inflight: list[dict] = []                 # human tools mid-execution (running…), complete on a tick
        self.impact_complete = False                   # Red detonated — aftermath/recovery phase is open
        # Auto-driven seats act ONLY when the host enables this. Off by default so a learner can read,
        # explore tools and act at their own pace — nothing happens on a clock until they make it happen.
        self.auto_enabled = False
        # Mode determines which seats are *functional* vs *narrated*:
        #   "teach"    — only the chosen team is functional; the rest are narrated (the Red attack spine
        #                still auto-advances so a defender has a live threat to work). Live Scenario.
        #   "practice" — every non-chosen team is functional (auto-plays for real). Scenario Library.
        self.mode = "teach"
        self.human_role: str | None = None             # the seat the learner is driving
        self.finished = False
        self.outcome: str | None = None
        self.report: dict | None = None
        self.session: "LiveSession | None" = None      # set on attach
        self._emit("g_phase", "system", "Operation Tripwire — you are the worm",
                   "Patient zero FIN-WS-014 is infected. Discover the network, spread before the "
                   "defenders stop you. Switch tabs to watch SOC and Blue react.", sev="high")

    # ---- time / events -------------------------------------------------------
    def _t(self) -> int:
        return int(time.time() - self.started_at)

    def _emit(self, kind: str, role: str, title: str, message: str, *, sev: str = "info",
              data: dict | None = None, notify: bool = False) -> dict:
        ev = {"seq": self.seq, "t": self._t(), "kind": kind, "role": role, "title": title,
              "message": message, "severity": sev, "data": data or {}, "notify": notify}
        self.seq += 1
        self.events.append(ev)
        return ev

    def _alert(self, label: str, host: T.Host | None, sev: str, mitre: str = "") -> None:
        # MTTD: the alert is queued now, but won't be *noticed* (auto-triageable) until detect_at.
        lo, hi = DETECT_LATENCY.get(sev, (4, 9))
        a = {"id": f"al{self.alert_seq}", "t": self._t(), "label": label, "mitre": mitre,
             "severity": sev, "host_id": host.id if host else None,
             "host_name": host.name if host else None, "status": "new",
             "raised_tick": self.tick_n, "detect_at": self.tick_n + self.rng.randint(lo, hi)}
        self.alert_seq += 1
        self.alerts.append(a)
        self._emit("alert", "soc", f"ALERT: {label}",
                   (f"on {host.name} " if host else "") + "— awaiting SOC triage",
                   sev=sev, data={"alert_id": a["id"]}, notify=True)

    # ---- host filters --------------------------------------------------------
    def _hosts_for(self, flt: str) -> list[T.Host]:
        hs = self.topo.hosts.values()
        if flt == "exploitable":
            return [h for h in hs if h.vulnerable and h.revealed and h.state in ("healthy", "vulnerable")]
        if flt == "exploited":
            return [h for h in hs if h.state == "exploited"]
        if flt == "vulnerable":
            return [h for h in hs if h.vulnerable and h.state in ("healthy", "vulnerable")]
        if flt == "containable":
            return [h for h in hs if h.state in T.LIVE_INFECTED or h.state == "exploited"]
        if flt == "impacted":
            return [h for h in hs if h.state == "impacted"]
        return list(hs)

    # ---- availability / unlocks ---------------------------------------------
    def _available(self, tool: TL.Tool) -> tuple[bool, str]:
        ts = self.teams[tool.team]
        if tool.once and tool.id in ts.done:
            return False, "already done"
        for req in tool.unlocks_after:
            if req not in ts.done:
                return False, f"requires {self.tools[req].name if req in self.tools else req}"
        # target availability for host-targeted tools
        for f in tool.schema:
            if f.type in ("host", "hosts") and not self._hosts_for(f.filter):
                return False, f"no {f.filter} host yet"
            if f.type == "alert":
                pool = [a for a in self.alerts if a["status"] == ("new" if f.filter == "new" else "triaged")]
                if not pool:
                    return False, f"no {f.filter} alert"
        # Red kill-chain gates the defenders can revoke (this is what makes containment *partial* and
        # timing-dependent: cut C2 / reset creds early and Red stalls; too late and the foothold persists).
        if tool.needs_c2 and (not self.c2_live or self.c2_blocked):
            return False, "C2 channel is down — re-establish a beacon first"
        if tool.needs_creds and not self.creds_pwned:
            return False, "stolen credentials were reset — re-harvest them first"
        if tool.effect == "exfiltrate" and self.egress_blocked:
            return False, "egress to file-sharing sites is blocked"
        if tool.effect == "sinkhole" and self.kill_switch != "armed":
            return False, "no kill-switch callback observed yet"
        if tool.effect == "restore" and not self.backups_safe:
            return False, "backups were not preserved"
        return True, ""

    def unlocked(self, team: str) -> list[dict]:
        out = []
        for t in self.tools.values():
            if t.team != team:
                continue
            ok, reason = self._available(t)
            out.append(t.public(ok, reason))
        return out

    # ====================================================================== #
    #  run_tool — the single entry point for every team action
    # ====================================================================== #
    def run_tool(self, team: str, tool_id: str, params: dict | None = None,
                 by_auto: bool = False) -> tuple[bool, str]:
        if self.finished:
            return False, "scenario complete"
        tool = self.tools.get(tool_id)
        if tool is None:
            return False, "unknown tool"
        # ONE common console for every team: the tool's own team is authoritative, so whichever seat
        # the operator is driving they can run any command (no "unknown tool for this team" lockout —
        # this is what lets you keep working any role's tools after the attack, in recovery/review).
        team = tool.team
        ok, reason = self._available(tool)
        if not ok:
            return False, reason
        params = params or {}
        msg = self._apply(tool, params)
        self.teams[team].done.add(tool.id)
        self.teams[team].score += 12 if team == "red" else 15
        # Tag the action with the host it targeted (if any) so the AAR can reconstruct the per-asset
        # attack path. `host` is the single-target field used by exploit/infect/isolate/restore.
        thost = self.topo.hosts.get(params.get("host", "")) if params.get("host") else None
        tgt = {"asset_id": thost.id, "asset_label": thost.name} if thost else {}
        # Guide data attached to every tool execution event
        guide_data = {"consequence": tool.consequence, "next_hint": tool.next_hint,
                      "teaching_note": tool.teaching_note, "guide_text": tool.guide_text}
        # real tools also fire the real command against the lab (streamed back by the manager)
        if tool.kind == "real" and tool.fire_action and self.session is not None:
            from app.lab import live_fire as lf
            ev = self._emit("action", "red", tool.name, f"{tool.fire_action}: real tool",
                            sev="medium", data={"tool_id": tool.id, "kind": "real",
                                                "live_fire": lf.queued_view(tool.fire_action),
                                                **guide_data, **tgt}, notify=True)
            self.session.pending_fire.append({"seq": ev["seq"], "action_id": tool.fire_action,
                                              "target_id": thost.id if thost else None})
        else:
            result = msg or tool.outcome
            self._emit("action" if team == "red" else "response", team, tool.name,
                       (tool.command_hint + "  ·  " if tool.command_hint else "") + result,
                       sev="high" if team != "red" else "medium",
                       data={"tool_id": tool.id, "kind": tool.kind,
                             "command": tool.command_hint, "result": result, "mitigates": tool.mitigates,
                             **guide_data, **tgt}, notify=True)
        # Data-driven SOC signals: every scenario narrates its own detections via the tool's
        # `alert`/`telemetry` fields (the engine no longer hardcodes WannaCry strings).
        self._raise_signals(tool, thost)
        self._check_finish()
        return True, ""

    # ====================================================================== #
    #  begin_tool — the human entry point: the tool *runs for a while* before it lands
    # ====================================================================== #
    def begin_tool(self, team: str, tool_id: str, params: dict | None = None) -> tuple[bool, str]:
        """Start a human-initiated tool. Unlike the instant `run_tool` (used by tests + auto seats),
        this models real execution time: the command goes 'running…' for a randomized number of ticks
        and only *completes* (effect + telemetry) later, on `_advance_inflight`. Lets the learner take
        their time and ties the defenders' detection clock to when Red's command actually finishes."""
        if self.finished:
            return False, "scenario complete"
        tool = self.tools.get(tool_id)
        if tool is None:
            return False, "unknown tool"
        team = tool.team   # common console: the tool's team is authoritative (see run_tool)
        if any(f["team"] == team for f in self.inflight):
            return False, "a tool is already running — let it finish first"
        ok, reason = self._available(tool)
        if not ok:
            return False, reason
        delay = self._exec_delay(tool)
        if delay <= 0:
            return self.run_tool(team, tool_id, params)
        self.inflight.append({
            "team": team, "tool_id": tool.id, "params": params or {},
            "label": tool.name, "command": tool.command_hint or tool.name,
            "started_tick": self.tick_n, "done_at": self.tick_n + delay, "total": delay,
        })
        # a lightweight "running" marker in the timeline (the live output lands on completion)
        self._emit("running", team, tool.name, f"{tool.command_hint or tool.name} — running…",
                   sev="info", data={"tool_id": tool.id, "command": tool.command_hint, "running": True})
        return True, ""

    def _exec_delay(self, tool: TL.Tool) -> int:
        lo, hi = EXEC_LATENCY.get(tool.effect, (2, 3))
        return self.rng.randint(lo, hi)

    def _advance_inflight(self) -> bool:
        """Complete any human tools whose run time has elapsed (their effect + telemetry land now)."""
        ready = [f for f in self.inflight if f["done_at"] <= self.tick_n]
        if not ready:
            return False
        for f in ready:
            self.inflight.remove(f)
            if self.tools.get(f["tool_id"]) is not None:
                self.run_tool(f["team"], f["tool_id"], f["params"])   # instant apply — the wait already happened
        return True

    def _raise_signals(self, tool: TL.Tool, host: T.Host | None) -> None:
        """Emit the SOC alert + investigation-lens telemetry this tool declares (data-driven)."""
        if tool.telemetry:
            ch, title, text, *rest = (*tool.telemetry, "")
            sev = rest[0] if rest and rest[0] else "low"
            self._emit("g_telemetry", "soc", title, text, sev=sev, data={"telemetry": ch})
        if tool.alert:
            label, sev, *rest = (*tool.alert, "")
            mitre = rest[0] if rest else ""
            self._alert(label, host, sev or "medium", mitre)

    def _patient_zero(self) -> T.Host | None:
        return next((h for h in self.topo.hosts.values() if h.patient_zero), None)

    def _backup_protected(self) -> bool:
        return self._backup_air_gapped

    def _seed_cred_foothold(self) -> None:
        """Human-operated lateral movement plants a foothold on a reachable high-value server using
        valid creds (no vuln needed). Backup/file/DC first — that's what a ransomware crew goes for."""
        sources = [h for h in self.topo.hosts.values() if h.state in T.LIVE_INFECTED]
        reach: set[str] = set()
        for s in sources:
            reach |= self.topo.reachable_vlans(s.vlan)
        priority = ("backup", "fileserver", "domain_controller", "database", "appserver")
        cands = [h for h in self.topo.hosts.values()
                 if h.vlan in reach and h.revealed and h.state in ("healthy", "vulnerable")
                 and not h.patient_zero]
        cands.sort(key=lambda h: priority.index(h.role) if h.role in priority else 99)
        if cands:
            cands[0].state = "infected"

    def _apply(self, tool: TL.Tool, params: dict) -> str:
        eff = tool.effect
        topo = self.topo
        # ---- RED ----
        if eff == "reveal_hosts":
            # nmap-style passes range=subnet (local only); AD-enum tools (no schema) reveal everything.
            pz = self._patient_zero()
            rng = params.get("range", "all")
            for h in topo.hosts.values():
                if rng == "all" or (pz and h.vlan == pz.vlan):
                    h.revealed = True
            return f"{sum(1 for h in topo.hosts.values() if h.revealed)} hosts discovered"
        if eff == "mark_vulnerable":
            n = 0
            for h in topo.hosts.values():
                h.revealed = True
                if h.vulnerable and h.state == "healthy":
                    h.state = "vulnerable"
                    n += 1
            return f"{n} vulnerable hosts identified"
        if eff == "deliver_phish":
            pz = self._patient_zero()
            if pz is None:
                return "no target user"
            pz.revealed = True
            pz.flags.add("phish_delivered")
            return f"weaponised email delivered to {pz.name} — awaiting the click"
        if eff == "spray":
            # password spray = initial credential compromise (gates the VPN foothold via unlocks_after)
            return "5 of 200 accounts compromised — valid VPN credentials obtained"
        if eff == "exploit":
            # host-targeted (W1 EternalBlue) OR auto-targets patient zero (R5 macro / C5 vpn foothold)
            h = topo.hosts.get(params.get("host", "")) or self._patient_zero()
            if h is None or h not in self._hosts_for("exploitable"):
                return "select a valid vulnerable host"
            h.state = "exploited"
            return f"{h.name} exploited"
        if eff == "infect":
            h = (topo.hosts.get(params.get("host", ""))
                 or next((x for x in topo.hosts.values() if x.state == "exploited"), None))
            if h is None or h.state != "exploited":
                return "select an exploited host"
            h.state = "infected"
            return f"{h.name} infected"
        if eff == "c2_establish":
            self.c2_live = True
            self.c2_blocked = False
            # the beacon turns the exploited foothold into a live, hands-on-keyboard infection
            promoted = 0
            for h in topo.hosts.values():
                if h.state == "exploited":
                    h.state = "infected"
                    promoted += 1
            return "C2 beacon established — hands-on-keyboard access" + (
                f" on {promoted} host(s)" if promoted else "")
        if eff == "cred_dump":
            self.creds_pwned = True
            return "domain credentials harvested from LSASS memory"
        if eff == "persist":
            n = 0
            for h in topo.hosts.values():
                if h.state in T.LIVE_INFECTED or h.state == "exploited":
                    h.flags.add("persistent"); n += 1
            return f"persistence established on {n} host(s)"
        if eff == "killswitch_check":
            self.kill_switch = "armed"
            return "kill-switch domain unreachable — worm proceeds"
        if eff == "start_propagation":
            self.propagating = True
            return "worm propagation started"
        if eff == "cred_propagation":
            # human-operated lateral movement: spread uses *valid creds*, not a vuln, so it ignores the
            # SMBv1 gate (Blue stops it by resetting creds, not patching). Seed one server foothold now.
            self.propagating = True
            self.cred_mode = True
            self._seed_cred_foothold()
            return "lateral movement underway with the stolen account"
        if eff == "exfiltrate":
            self.exfiltrated = True
            return "sensitive data staged and uploaded to the attacker's cloud"
        if eff == "disable_recovery":
            for h in topo.hosts.values():
                if h.state in T.LIVE_INFECTED:
                    h.flags.add("recovery_disabled")
            # backups only truly die if the backup host itself was reached and isn't air-gapped
            if not self._backup_protected() and any(
                    h.role == "backup" and h.state in (T.LIVE_INFECTED | {"impacted"})
                    for h in topo.hosts.values()):
                self.backups_safe = False
            return "local recovery disabled on compromised hosts"
        if eff == "encrypt":
            n = 0
            for h in topo.hosts.values():
                if h.state in T.LIVE_INFECTED:
                    h.state = "impacted"
                    h.flags.add("encrypted")
                    n += 1
            self.extra_impacted += self.extra_infected
            n += self.extra_infected
            self.extra_infected = 0
            self.propagating = False           # detonation ends the spread phase
            return f"{n} hosts encrypted"
        # ---- BLUE (every lever is *partial* — it bends the curve, it doesn't end the game) ----
        if eff == "isolate":
            h = topo.hosts.get(params.get("host", ""))
            if h is None or h not in self._hosts_for("containable"):
                return "select a compromised host"
            h.state = "contained"
            h.flags.discard("persistent")
            bonus = " (on a SOC-escalated incident)" if h.id in self.incident_declared else ""
            self.teams["blue"].score += 10 if h.id in self.incident_declared else 5
            return f"{h.name} isolated{bonus} — it can no longer spread"
        if eff == "patch_hosts":
            ids = [x for x in params.get("hosts", "").split(",") if x]
            n = 0
            for hid in ids:
                h = topo.hosts.get(hid)
                if h and h.vulnerable:
                    h.vulnerable = False
                    if h.state == "vulnerable":
                        h.state = "healthy"
                    n += 1
            return f"vulnerable service disabled on {n} host(s)"
        if eff == "segment":
            a, b = (params.get("edge", "fin|srv").split("|") + ["fin", "srv"])[:2]
            topo.cut_edge(a, b)
            self.segmented = True
            self._recompute_r()
            return f"severed {a.upper()} ↔ {b.upper()} — the blast radius across that boundary is capped"
        if eff == "disable_cred" or eff == "reset_creds":
            # Revoke the attacker's valid credentials → cred-driven lateral movement stalls. Hosts
            # already compromised stay compromised (this bends the curve, it doesn't undo the breach).
            self.creds_pwned = False
            if self.cred_mode:
                self.propagating = False
                self._recompute_r()
            verb = "reset" if eff == "reset_creds" else "disabled"
            return f"compromised accounts {verb} — stolen credentials are now worthless"
        if eff == "block_c2":
            self.c2_blocked = True
            self.c2_live = False
            return "C2 domain sinkholed at the proxy — the beacon is cut off"
        if eff == "block_egress":
            self.egress_blocked = True
            return "file-sharing sites blocked at the proxy/firewall — the exfiltration channel is cut"
        if eff == "declare_ir":
            n = 0
            for h in topo.hosts.values():
                if h.state in T.LIVE_INFECTED or h.state == "exploited":
                    self.incident_declared.add(h.id); n += 1
            self.teams["blue"].score += 8
            return f"P1 incident declared — {n} compromised host(s) scoped; containment now coordinated"
        if eff == "protect_backup":
            self.backups_safe = True
            self._backup_air_gapped = True
            return "backup infrastructure air-gapped — it survives even if everything else encrypts"
        if eff == "alt_detect":
            # compensating monitoring during the EDR outage: surfaces footholds that didn't alert
            n = 0
            for h in topo.hosts.values():
                if h.state in T.LIVE_INFECTED and not any(al["host_id"] == h.id for al in self.alerts):
                    self._alert("Sysmon: compensating-monitoring hit", h, "medium")
                    n += 1
            return f"alternate monitoring online — surfaced {n} foothold(s) the dead EDR missed"
        if eff == "sinkhole":
            if self.kill_switch != "armed":
                return "no kill-switch callback to sinkhole"
            self.kill_switch = "tripped"
            for h in topo.hosts.values():
                if h.state in T.LIVE_INFECTED:
                    h.state = "dormant"
            self.extra_dormant += self.extra_infected
            self.extra_infected = 0
            self.propagating = False
            self.r_value = 0.0
            return "kill-switch tripped — infected hosts went dormant fleet-wide"
        if eff == "patch_all":
            for h in topo.hosts.values():
                if h.vulnerable:
                    h.vulnerable = False
                    if h.state == "vulnerable":
                        h.state = "healthy"
            self.smbv1_patched = True
            if not self.cred_mode:
                self.r_value = 0.0          # closes the vuln vector (cred-driven spread is unaffected)
            return "vulnerable service patched fleet-wide — the exploit vector is gone"
        if eff == "restore":
            h = topo.hosts.get(params.get("host", ""))
            if h is None or h.state != "impacted":
                return "select an impacted host"
            h.state = "recovered"
            h.flags.discard("encrypted")
            return f"{h.name} restored from clean backup"
        # ---- SOC ----
        if eff == "view":
            chans = set(tool.lens)
            hits = [e for e in self.events
                    if e["kind"] == "g_telemetry" and e["data"].get("telemetry") in chans]
            if not hits:
                return "0 results — no matching telemetry in the index yet"
            rows = [f"[{e['t']:>3}s] {e['title']} — {e['message']}" for e in hits[-6:]]
            return f"{len(hits)} matching event(s):\n" + "\n".join(rows)
        if eff == "hunt":
            n = 0
            for h in topo.hosts.values():
                if h.state in T.LIVE_INFECTED and not any(al["host_id"] == h.id for al in self.alerts):
                    self._alert(f"Hunt: undetected foothold", h, "high")
                    n += 1
            return f"surfaced {n} undetected foothold(s)"
        if eff == "triage":
            a = next((x for x in self.alerts if x["id"] == params.get("alert") and x["status"] == "new"), None)
            if a is None:
                return "select a new alert"
            a["status"] = "triaged"
            return f"triaged {a['label']}"
        if eff == "escalate":
            a = next((x for x in self.alerts if x["id"] == params.get("alert") and x["status"] == "triaged"), None)
            if a is None:
                return "select a triaged alert"
            a["status"] = "escalated"
            if a["host_id"]:
                self.incident_declared.add(a["host_id"])
            self.teams["soc"].score += 10
            return f"escalated — incident declared" + (f" on {a['host_name']}" if a["host_name"] else "")
        return ""

    def _recompute_r(self) -> None:
        r = 2.4
        if self.segmented:
            r *= 0.4
        if self.kill_switch == "tripped":
            r = 0.0
        elif self.cred_mode:
            if not self.creds_pwned:        # creds reset → credential-driven spread halts
                r = 0.0
        elif self.smbv1_patched:            # vuln-worm patched → exploit vector closed
            r = 0.0
        self.r_value = round(r, 2)

    # ====================================================================== #
    #  tick — worm propagation + telegraphed auto + outcome
    # ====================================================================== #
    def tick(self) -> bool:
        if self.finished:
            return False
        self.tick_n += 1
        changed = self._advance_inflight()          # complete any human tools whose run time elapsed
        changed = self._propagate() or changed
        changed = self._auto_step() or changed
        if self._check_finish():
            changed = True
        return changed

    def _propagate(self) -> bool:
        # A vuln-worm is stopped by patching; credential-driven lateral movement is stopped by
        # resetting creds (which clears self.propagating). Sinkhole / segment / zero-R stop both.
        if (not self.propagating or self.kill_switch == "tripped" or self.r_value <= 0
                or (self.smbv1_patched and not self.cred_mode)):
            return False
        sources = [h for h in self.topo.hosts.values() if h.state in T.LIVE_INFECTED]
        named_live = len(sources)
        if named_live == 0 and self.extra_infected == 0:
            return False
        for h in sources:
            if h.state == "infected":
                h.state = "propagating"
        changed = False
        # spread among the named, drawn hosts (reachability-gated; vuln-gated unless cred-driven)
        pool, seen = [], set()
        for s in sources:
            for t in self._lateral_targets(s):
                if t.id not in seen:
                    seen.add(t.id)
                    pool.append(t)
        if pool:
            n = min(len(pool), max(1, round(self.r_value * 0.5 * max(1, named_live))), 5)
            for t in pool[:n]:
                t.state = "infected"
            changed = True
        # spread into the unnamed remainder of the fleet (the rest of the org) — geometric in R
        total_live = named_live + self.extra_infected
        remaining = self.topo.extra_hosts - self.extra_infected - self.extra_impacted - self.extra_dormant
        if remaining > 0 and total_live > 0:
            grow = min(remaining, max(1, round(self.r_value * 0.4 * total_live)), 30)
            self.extra_infected += grow
            changed = True
        if changed:
            nr = self.narr
            self._emit("g_telemetry", "soc", nr["spread_title"],
                       nr["spread_text"].format(n=self.infected_total(), r=self.r_value),
                       sev="high", data={"telemetry": nr["spread_channel"]}, notify=True)
            la = nr["lateral_alert"]
            if not any(al["label"] == la[0] for al in self.alerts[-4:]):
                self._alert(la[0], None, la[1], la[2] if len(la) > 2 else "")
        return changed

    def _lateral_targets(self, src: T.Host) -> list[T.Host]:
        """Hosts the attack can reach from `src`: vuln-gated for a worm; any reachable revealed host
        when the attacker moves with valid stolen credentials (cred_mode = human-operated lateral)."""
        if not self.cred_mode:
            return self.topo.spread_targets(src)
        reach = self.topo.reachable_vlans(src.vlan)
        return [h for h in self.topo.hosts.values()
                if h.vlan in reach and h.revealed and h.state in ("healthy", "vulnerable")
                and not h.patient_zero]

    # ---- mode: which seats are functional vs narrated -----------------------
    def configure_mode(self, mode: str, human_role: str | None) -> None:
        """Set teach/practice + the human's seat, and derive whether any seat auto-runs."""
        self.mode = mode if mode in ("teach", "practice") else "teach"
        self.human_role = human_role if human_role in ("red", "blue", "soc") else None
        self.auto_enabled = any(self._auto_active(r) for r in ("red", "blue", "soc"))

    def set_human_role(self, role: str | None) -> None:
        self.configure_mode(self.mode, role)

    def _auto_active(self, role: str) -> bool:
        """Does this seat act for real (auto-driven)? The human's own seat never auto-runs."""
        if self.human_role and role == self.human_role:
            return False
        if self.mode == "practice":
            # every other seat is functional; in a multi-human room defer to seat occupancy
            return self.session.is_auto(role) if self.session is not None else True
        # teach: only the Red attack spine auto-advances (when the human is a defender);
        # the defender seats are NARRATED, never functional, so Red completes its goal.
        return role == "red" and self.human_role != "red"

    def _is_narrated(self, role: str) -> bool:
        """A team shown educationally (what they *would* do) but not actually acting — teach mode only."""
        return self.mode == "teach" and role != self.human_role and not self._auto_active(role)

    # ---- telegraphed auto-drivers -------------------------------------------
    def _is_auto(self, role: str) -> bool:
        if self.session is None:
            return True
        return self.session.is_auto(role)

    def _auto_step(self) -> bool:
        if not self.auto_enabled:               # learner-paced: no seat acts on a timer
            if self.pending_intents:
                self.pending_intents.clear()
            return False
        changed = False
        for role in ROLES:
            if not self._auto_active(role):     # human seat + (teach) narrated defenders don't auto-run
                self.pending_intents.pop(role, None)
                continue
            intent = self.pending_intents.get(role)
            if intent is None:
                intent = self._plan(role)
                if intent is not None:
                    delay = self._action_delay(role, intent)   # realistic, randomized processing time
                    intent["ticks_left"] = delay
                    intent["eta_ticks"] = delay
                    self.pending_intents[role] = intent
                    self._emit("g_intent", role, f"{role.upper()} will {intent['label']}",
                               f"in ~{delay * 3}s — act first to change the outcome",
                               sev="medium", data={"role": role, "eta_ticks": delay})
                continue
            intent["ticks_left"] -= 1
            if intent["ticks_left"] <= 0:
                ok, _ = self.run_tool(role, intent["tool_id"], intent.get("params"), by_auto=True)
                self.pending_intents.pop(role, None)
                changed = changed or ok
        return changed

    def _action_delay(self, role: str, intent: dict) -> int:
        """How many ticks this auto action takes to complete — sampled per action so defenders lag Red
        by a realistic, variable amount (identification + processing + locating the target/data)."""
        if role == "red":
            return self.rng.randint(*RED_ACTION_LATENCY)
        tool = self.tools.get(intent.get("tool_id", ""))
        lo, hi = ACTION_LATENCY.get(tool.effect if tool else "", (2, 4))
        return self.rng.randint(lo, hi)

    def _avail_effect(self, team: str, effect: str) -> TL.Tool | None:
        return next((t for t in self.tools.values()
                     if t.team == team and t.effect == effect and self._available(t)[0]), None)

    def _blue_engaged(self) -> bool:
        """IR isn't standing over the attacker's shoulder — the auto-Blue seat stays idle until the
        incident is actually *known*: the SOC has noticed an alert, escalated an incident, or Blue has
        already started responding. This is the window where Red gets to work undetected."""
        if self.incident_declared or self.teams["blue"].done:
            return True
        return any(self.tick_n >= a.get("detect_at", 0) for a in self.alerts)

    def _intent_for(self, t: TL.Tool) -> dict | None:
        """Build {tool_id, params, label} for an auto seat — auto-fills the tool's first target."""
        params: dict = {}
        for f in t.schema:
            if f.type == "host":
                hs = self._hosts_for(f.filter)
                if not hs:
                    return None
                pick = (next((h for h in hs if h.id in self.incident_declared), hs[0])
                        if f.filter == "containable" else hs[0])
                params[f.key] = pick.id
            elif f.type == "hosts":
                hs = self._hosts_for(f.filter)
                if not hs:
                    return None
                params[f.key] = ",".join(h.id for h in hs[:5])
            elif f.type == "alert":
                want = "new" if f.filter == "new" else "triaged"
                pool = [x for x in self.alerts if x["status"] == want]
                if want == "new":   # auto-SOC can only triage alerts it has actually *noticed* (MTTD)
                    pool = [x for x in pool if self.tick_n >= x.get("detect_at", 0)]
                if not pool:
                    return None
                params[f.key] = pool[0]["id"]
            elif f.default:
                params[f.key] = f.default
        label = t.name
        tgt = self.topo.hosts.get(params.get("host", ""))
        if tgt:
            label = f"{t.name} → {tgt.name}"
        return {"tool_id": t.id, "params": params, "label": label}

    def _plan(self, role: str) -> dict | None:
        """Pick an auto seat's next intended tool. Scenario-agnostic: chosen by *effect* + live state,
        not hardcoded tool ids, so the same competent driver works for W1/R5/C5."""
        if role == "red":
            # walk the kill chain in catalog order — first available step not already taken (recon
            # tools aren't flagged `once`, so without the done-check the driver would loop on nmap)
            for t in TL.catalog(self.scenario_id):
                if (t.team == "red" and t.id not in self.teams["red"].done
                        and self._available(t)[0]):
                    intent = self._intent_for(t)
                    if intent:
                        return intent
            return None
        if role == "soc":
            # validate then escalate — but only alerts the analyst has *noticed* (detect_at); an
            # alert can sit in the queue, unnoticed, while Red keeps working (intent may be None).
            for eff in ("triage", "escalate"):
                t = self._avail_effect("soc", eff)
                if t:
                    intent = self._intent_for(t)
                    if intent:
                        return intent
            # hunt only when there's an undetected live foothold to find
            if any(h.state in T.LIVE_INFECTED and not any(al["host_id"] == h.id for al in self.alerts)
                   for h in self.topo.hosts.values()):
                t = self._avail_effect("soc", "hunt")
                if t:
                    intent = self._intent_for(t)
                    if intent:
                        return intent
            for t in TL.catalog(self.scenario_id):       # otherwise keep an investigation lens warm
                if (t.team == "soc" and t.effect == "view" and t.id not in self.teams["soc"].done
                        and self._available(t)[0]):
                    intent = self._intent_for(t)
                    if intent:
                        return intent
            return None
        if role == "blue":
            if not self._blue_engaged():   # IR not yet dispatched — Red still operating undetected
                return None
            # decisive containment first (by effect + state), then eradication, then recovery
            order: list[str] = []
            if self.kill_switch == "armed":
                order.append("sinkhole")
            if self.c2_live and not self.c2_blocked:
                order.append("block_c2")
            if self.propagating and not self.segmented:
                order.append("segment")
            if self.cred_mode and self.creds_pwned:
                order += ["reset_creds", "disable_cred"]
            if self._hosts_for("containable"):
                order.append("isolate")
            order += ["patch_all", "protect_backup", "declare_ir", "patch_hosts"]
            if self._hosts_for("impacted"):
                order.append("restore")
            for eff in order:
                t = self._avail_effect("blue", eff)
                if t:
                    intent = self._intent_for(t)
                    if intent:
                        return intent
            return None
        return None

    # ---- outcome -------------------------------------------------------------
    def infected_total(self) -> int:
        return self.topo.infected_count() + self.extra_infected

    def impacted_total(self) -> int:
        return self.topo.impacted_count() + self.extra_impacted

    def outcome_band(self) -> str:
        total = self.topo.total_hosts()
        hit = self.infected_total() + self.impacted_total()
        ratio = hit / total if total else 0.0
        if ratio < 0.10 and self.backups_safe:
            return "Contained"
        if ratio < 0.45:
            return "Degraded"
        return "Catastrophic"

    def financial_loss(self) -> int:
        # encryption impact per host + a flat data-breach cost if data was exfiltrated (double extortion)
        return int(self.impacted_total() * (85.0 + 750.0) + (1_200_000 if self.exfiltrated else 0))

    def _live_threats(self) -> int:
        return sum(1 for h in self.topo.hosts.values()
                   if h.state in T.LIVE_INFECTED or h.state == "exploited")

    def _red_has_moves(self) -> bool:
        # a "move" = a kill-chain step Red hasn't taken yet that's currently available (re-running
        # already-done recon doesn't count as progress, so a fully-contained Red is correctly "dead")
        return any(t.team == "red" and t.id not in self.teams["red"].done and self._available(t)[0]
                   for t in self.tools.values())

    def _check_finish(self) -> bool:
        if self.finished:
            return False
        # Red's terminal move: impact detonated (encryption) and the spread has settled.
        impact_done = any(self.tools[t].effect == "encrypt"
                          for t in self.teams["red"].done if t in self.tools)
        if impact_done and not self.propagating:
            # In an auto match, conclude. For a human-paced run, DON'T end here — open the aftermath:
            # the attack succeeded, now let the defenders learn containment / eradication / recovery
            # before they Conclude. (See snapshot.impact_complete → the "what happens next" trigger.)
            if self.auto_enabled:
                self._finish()
                return True
            if not self.impact_complete:
                self.impact_complete = True
                self._emit("g_phase", "system", "Red's mission complete — now respond",
                           "Files are encrypted and the attack succeeded. This is where real defenders "
                           "earn their pay: contain the spread, eradicate the foothold, and recover from "
                           "backups. Switch to Blue and work the recovery — then Conclude for the report.",
                           sev="critical", notify=True, data={"aftermath": True})
                return True
            return False
        # Checkmate: only in a *running auto* match, auto-conclude once Red is fully neutralised and
        # out of moves (and the defenders actually did something). A solo learner is never auto-ended
        # here — they explore freely and hit Conclude when ready.
        if self.auto_enabled:
            red_dead = (self._live_threats() == 0 and self.extra_infected == 0
                        and not self._red_has_moves())
            if red_dead and any(self.teams[r].done for r in ("blue", "soc")):
                self._finish()
                return True
        return False

    def set_auto_enabled(self, on: bool) -> None:
        # Legacy/test entry: turning auto on means a full all-seats match → practice mode.
        if on:
            self.mode = "practice"
        self.auto_enabled = bool(on)
        if not on:
            self.pending_intents.clear()

    # ---- scoring (narrated teams get a competent-baseline estimate, never a misleading 0) -----
    def team_score(self, role: str) -> int:
        return self._estimate_score(role) if self._is_narrated(role) else self.teams[role].score

    def _estimate_score(self, role: str) -> int:
        """What a competent team WOULD have scored against this run, from the opportunities it had —
        so a narrated (non-functional) team reads as a real assessment, not zero."""
        if role == "soc":
            severe = sum(1 for a in self.alerts if a["severity"] in ("high", "critical"))
            return 20 + len(self.alerts) * 12 + severe * 10          # monitor + triage all + escalate severe
        if role == "blue":
            opportunities = min(6, self._live_threats() + self.impacted_total())
            vector = 30 if (self.smbv1_patched or self.kill_switch == "tripped" or self.cred_mode) else 0
            return 30 + opportunities * 15 + vector                  # contain footholds + close the vector
        return self.teams[role].score

    def conclude(self) -> None:
        if not self.finished:
            self._finish()

    def _finish(self) -> None:
        self.finished = True
        self.outcome = self.outcome_band()
        from . import report_adapter
        self.report = report_adapter.build(self)
        self._emit("g_result", "system", f"Scenario complete — {self.outcome}",
                   f"{self.infected_total()} infected, {self.impacted_total()} impacted, "
                   f"est. loss ${self.financial_loss():,}.", sev="critical",
                   data={"outcome": self.outcome}, notify=True)
        # Save the AAR (Reports & AAR) — reuse the guided persistence (compatible report shape).
        if self.session is not None:
            try:
                self.session.report = self.report
                self.session.status = "completed"
                self.session.match_result = "guided"
                from ..guided_runtime import _persist_guided_report
                _persist_guided_report(self.session)
            except Exception:  # noqa: BLE001 — persistence must never break conclusion
                pass

    # ---- AAR -----------------------------------------------------------------
    _SCN_META = {
        "scn-wannacry-w1": ("Operation Tripwire", "WannaCry-Style SMB Worm"),
        "scn-r5-phishing": ("Phishing to Encrypt", "Human-Operated Ransomware Campaign"),
        "scn-c5-edr": ("EDR Outage Exploitation", "Attacking During Blindness"),
    }

    def _build_report(self) -> dict:
        band = self.outcome or self.outcome_band()
        result = {"Contained": "blue", "Degraded": "draw", "Catastrophic": "red"}.get(band, "draw")
        scn_name, scn_sub = self._SCN_META.get(self.scenario_id, ("Operation Tripwire", "Immersive cyber-range"))
        counts = self.topo.counts()
        teams = {}
        for role in ("red", "soc", "blue"):
            tl = [{"t": e["t"], "label": e["title"]} for e in self.events
                  if e["role"] == role and e["kind"] in ("action", "response", "soc")]
            teams[role] = {"score": self.team_score(role), "timeline": tl,
                           "kpis": {"actions": len(tl)}, "narrated": self._is_narrated(role)}
        teams["soc"]["kpis"]["alerts"] = len(self.alerts)
        teams["soc"]["kpis"]["escalated"] = sum(1 for a in self.alerts if a["status"] == "escalated")
        recs = []
        if band != "Contained":
            recs.append("Act earlier — segment / patch / isolate before propagation outruns you.")
        if not self.smbv1_patched:
            recs.append("Disable SMBv1 fleet-wide; it is the worm's entire vector.")
        if band == "Contained":
            recs.append("Strong run — early detection + containment held the blast radius down.")
        return {
            "session_id": self.session.id if self.session else "", "guided": True,
            "mode": self.mode, "human_role": self.human_role,
            "scenario": {"id": self.scenario_id, "name": scn_name, "subtitle": scn_sub},
            "result": result, "outcome_band": band,
            "verdict": {"Contained": "Contained — minimal impact.", "Degraded": "Degraded — partial impact.",
                        "Catastrophic": "Catastrophic — fleet-wide encryption."}.get(band, "Concluded."),
            "duration_s": self._t(), "teams": teams,
            "outcome": {"outcome_band": band, "infected": self.infected_total(),
                        "impacted": self.impacted_total(), "total_hosts": self.topo.total_hosts(),
                        "financial_loss": self.financial_loss(), **counts},
            "recommendations": recs[:6],
            "note": "Immersive cyber-range AAR — saved to Reports & AAR.",
        }

    # ---- snapshot ------------------------------------------------------------
    def _compute_guide(self) -> dict:
        """Compute guide state: current phase, next suggested tool per role, progress.

        The narrative spine is Red's kill chain — the phases are Red's tool stages, in order — so the
        story panel reads coherently no matter which role is acting (a SOC query or Blue containment
        doesn't yank the storyline to a defender 'stage')."""
        all_tools = TL.catalog(self.scenario_id)
        red_tools = [t for t in all_tools if t.team == "red"]
        stages_seen: list[str] = []
        for t in red_tools:
            if t.stage not in stages_seen:
                stages_seen.append(t.stage)

        # Current phase = the furthest kill-chain stage Red has reached
        red_done = self.teams["red"].done
        current_stage = stages_seen[0] if stages_seen else ""
        for t in red_tools:
            if t.id in red_done:
                current_stage = t.stage

        phase_idx = stages_seen.index(current_stage) if current_stage in stages_seen else 0

        # Find next suggested tool per role
        next_tools: dict[str, dict | None] = {}
        for role in ("red", "soc", "blue"):
            unlocked = self.unlocked(role)
            unlocked_ids = {t["id"] for t in unlocked if t["available"]}
            done_ids = self.teams[role].done
            # First available tool not yet done
            for t in all_tools:
                if t.team == role and t.id in unlocked_ids and t.id not in done_ids:
                    next_tools[role] = {"id": t.id, "name": t.name, "stage": t.stage,
                                        "guide_text": t.guide_text, "summary": t.summary}
                    break
            else:
                next_tools[role] = None

        return {
            "phase": current_stage,
            "phase_index": phase_idx,
            "total_phases": len(stages_seen),
            "phases": stages_seen,
            "completed_phases": stages_seen[:phase_idx],
            "next_tools": next_tools,
            "progress": {"done": sum(len(self.teams[r].done) for r in ("red", "soc", "blue")),
                         "total": len(all_tools)},
        }

    def snapshot(self) -> dict:
        return {
            "scenario_id": self.scenario_id, "tick": self.tick_n, "finished": self.finished,
            "outcome": self.outcome, "auto_enabled": self.auto_enabled, "topology": self.topo.public(),
            "impact_complete": self.impact_complete,
            "inflight": [{"team": f["team"], "tool_id": f["tool_id"], "label": f["label"],
                          "command": f["command"], "eta_ticks": max(0, f["done_at"] - self.tick_n),
                          "total": f["total"]} for f in self.inflight],
            "worm": {"r_value": self.r_value, "propagating": self.propagating,
                     "kill_switch": self.kill_switch, "segmented": self.segmented,
                     "smbv1_patched": self.smbv1_patched, "backups_safe": self.backups_safe,
                     "infected": self.infected_total(), "impacted": self.impacted_total(),
                     "extra_infected": self.extra_infected, "extra_impacted": self.extra_impacted,
                     "financial_loss": self.financial_loss(), "outcome_band": self.outcome_band()},
            "mode": self.mode, "human_role": self.human_role,
            # per-team: functional (acts for real) vs narrated (shown educationally, doesn't act)
            "team_status": {r: ("you" if r == self.human_role
                                 else "functional" if self._auto_active(r)
                                 else "narrated") for r in ("red", "soc", "blue")},
            "teams": {r: {"score": self.teams[r].score, "tools": self.unlocked(r)} for r in ("red", "soc", "blue")},
            # `noticed` = the auto-SOC's mean-time-to-detect has elapsed (a human can triage anytime);
            # `detect_in` = ticks until the auto-SOC would notice a still-unnoticed alert.
            "alerts": [{**a, "noticed": self.tick_n >= a.get("detect_at", 0),
                        "detect_in": max(0, a.get("detect_at", 0) - self.tick_n)} for a in self.alerts],
            "incident_declared": sorted(self.incident_declared),
            "pending_intents": {r: {"label": i["label"], "ticks_left": i.get("ticks_left", 0)}
                                for r, i in self.pending_intents.items()},
            "events": self.events,
            "report": self.report,
            "guide": self._compute_guide(),
        }
