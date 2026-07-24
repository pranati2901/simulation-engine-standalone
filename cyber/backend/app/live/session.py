"""Live session state + Red/Blue/SOC live action resolution on one shared World.

A LiveSession holds a shared, mutable World plus players and the three team states: Red
OperatorState (attack), SOC SocState (detect/triage/escalate), Blue DefenderState (contain/
eradicate/recover). Humans drive roles in real time (purple/full-transparency mode); any
unoccupied seat is driven deterministically by the auto-drivers (live/auto.py) — no AI, just the
masterclass playbooks walked sensibly. The match is a race: Red wins by proving its objective;
Blue wins by fully evicting Red first.

Pipeline: Red acts → emits telemetry → coverage (env controls + SOC/Blue monitoring) raises an
ALERT → SOC triages + escalates (declares an incident) → Blue contains/eradicates/recovers, which
mutates the world to hinder Red.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from app.engine.enums import CredScope, Health, SecurityState
from app.engine.environment import EnvironmentSpec, build_world
from app.engine.scenario import Scenario
from app.engine.world import AssetInstance, World
from app.lab import live_fire as lf

from . import blue_playbook as bp
from . import live_report
from . import missions as mp
from . import red_playbook as rp
from . import soc_playbook as sp

# Roles a player may claim. Red/Blue/SOC are interactive (human or auto); the rest are spectator seats.
SELECTABLE_ROLES = ["red", "blue", "soc", "mgmt", "ot", "observer"]
INTERACTIVE_ROLES = {"red", "blue", "soc"}
AUTO_ROLES = ("red", "soc", "blue")  # order the auto-driver ticks them each cycle


def _pid() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Player:
    id: str
    name: str
    role: str | None = None
    is_host: bool = False
    connected: bool = False

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "role": self.role,
                "is_host": self.is_host, "connected": self.connected}


@dataclass
class OperatorState:
    profile: str = rp.DEFAULT_PROFILE
    budget: int = 200
    noise_spent: int = 0
    score: int = 0
    noise_multiplier: float = 1.0
    flags: set[str] = field(default_factory=set)
    revealed: set[str] = field(default_factory=set)
    intel: list[dict] = field(default_factory=list)
    done_actions: set[str] = field(default_factory=set)
    objectives: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    concluded: bool = False
    final: dict | None = None

    @property
    def exposure_pct(self) -> int:
        if self.budget <= 0:
            return 100
        return min(100, round(100 * self.noise_spent / self.budget))


@dataclass
class SocState:
    score: int = 0
    monitoring: set[str] = field(default_factory=set)
    capabilities: set[str] = field(default_factory=set)
    done_actions: set[str] = field(default_factory=set)
    history: list[dict] = field(default_factory=list)
    triaged: int = 0
    escalated: int = 0
    mtta_samples: list[int] = field(default_factory=list)
    concluded: bool = False
    final: dict | None = None


@dataclass
class DefenderState:
    score: int = 0
    monitoring: set[str] = field(default_factory=set)
    capabilities: set[str] = field(default_factory=set)
    done_actions: set[str] = field(default_factory=set)
    history: list[dict] = field(default_factory=list)
    contained_assets: set[str] = field(default_factory=set)
    mttc_samples: list[int] = field(default_factory=list)
    prevented: set[str] = field(default_factory=set)
    eradicated: bool = False
    concluded: bool = False
    final: dict | None = None


class LiveSession:
    def __init__(self, scenario: Scenario, env: EnvironmentSpec, host: Player) -> None:
        self.id = uuid.uuid4().hex[:8]
        self.scenario = scenario
        self.scenario_name = scenario.name
        self.env = env
        self.host_id = host.id
        self.players: dict[str, Player] = {host.id: host}
        self.status = "lobby"
        self.world: World | None = None
        self.mission: str = mp.DEFAULT_MISSION
        self.mission_locked: bool = False   # True for dedicated-mission launches (mission can't be changed)
        self.stealth_weight: float = 1.0
        self.operator: OperatorState | None = None
        self.soc: SocState | None = None
        self.defender: DefenderState | None = None
        self.events: list[dict] = []
        self.seq = 0
        self.created_at = time.time()
        self.started_at: float | None = None
        # shared interaction bookkeeping
        self.defense_flags: set[str] = set()
        self.shared_scoped: bool = False
        self.compromise_t: dict[str, int] = {}
        self.red_ever_foothold: bool = False
        self.impact_occurred: bool = False
        self.match_result: str | None = None
        self.report: dict | None = None     # all-teams AAR, built on conclude
        self._last_state_changes: list[str] = []
        # detection / alert queue (SOC-owned coverage)
        self.detected_actions: int = 0
        self.detectable_actions: int = 0
        self.alerts: list[dict] = []
        self.alert_seq: int = 0
        self.incident_declared: set[str] = set()
        # automation: explicit per-role overrides (else auto when seat is unoccupied)
        self.auto_override: dict[str, bool] = {}
        # live-fire: when armed (host) + lab up, Red actions also run REAL tools against the lab.
        # Off by default → the deterministic simulation is unchanged.
        self.live_fire: bool = False
        self.pending_fire: list[dict] = []   # queued real-tool jobs awaiting async execution
        # guided walkthrough (W1/R5/C5): a GuidedRun when this session is a scripted tutorial, else None
        self.guided = None  # type: ignore[var-annotated]
        # immersive cyber-range sim (sim/engine.ScenarioSim) when this is a dynamic workspace, else None
        self.sim = None  # type: ignore[var-annotated]

    # ---- time / events -------------------------------------------------------
    def _t(self) -> int:
        return int(time.time() - self.started_at) if self.started_at else 0

    def _emit(self, kind: str, title: str, message: str, *, role: str = "red",
              severity: str = "info", asset_id: str | None = None,
              asset_label: str | None = None, data: dict | None = None) -> dict:
        ev = {"seq": self.seq, "t": self._t(), "kind": kind, "role": role, "title": title,
              "message": message, "severity": severity, "asset_id": asset_id,
              "asset_label": asset_label, "data": data or {}}
        self.seq += 1
        self.events.append(ev)
        return ev

    @property
    def coverage_pct(self) -> int:
        if self.detectable_actions == 0:
            return 0
        return round(100 * self.detected_actions / self.detectable_actions)

    def _monitoring_union(self) -> set[str]:
        m: set[str] = set()
        if self.soc:
            m |= self.soc.monitoring
        if self.defender:
            m |= self.defender.monitoring
        return m

    # ---- automation ----------------------------------------------------------
    def is_auto(self, role: str) -> bool:
        if role in self.auto_override:
            return self.auto_override[role]
        return not any(p.role == role and p.connected for p in self.players.values())

    def set_auto(self, role: str, value: bool | None) -> None:
        if role not in INTERACTIVE_ROLES:
            return
        if value is None:
            self.auto_override.pop(role, None)
        else:
            self.auto_override[role] = bool(value)

    # ---- live-fire (real tools) ----------------------------------------------
    def arm_live_fire(self, on: bool) -> None:
        """Host toggle: when on, mapped Red actions also execute real tools against the lab."""
        self.live_fire = bool(on)

    def drain_pending_fire(self) -> list[dict]:
        """Return and clear queued real-tool jobs (the async caller runs them off-thread)."""
        jobs, self.pending_fire = self.pending_fire, []
        return jobs

    def apply_fire_result(self, seq: int, result: dict) -> None:
        """Attach a completed real-tool result to its action event (matched by event seq)."""
        for ev in reversed(self.events):
            if ev.get("seq") == seq:
                ev["data"]["live_fire"] = result
                if result.get("detected") and ev["data"].get("detected") is False:
                    # real evidence corroborated an action the model thought went unseen
                    ev["data"]["detected"] = True
                break

    # ---- lobby ---------------------------------------------------------------
    def add_player(self, name: str) -> Player:
        p = Player(id=_pid(), name=(name or "operator").strip()[:40] or "operator")
        self.players[p.id] = p
        return p

    def claim_role(self, player_id: str, role: str) -> bool:
        p = self.players.get(player_id)
        if p is None or role not in SELECTABLE_ROLES:
            return False
        p.role = role
        return True

    def set_profile(self, profile_id: str) -> None:
        if self.operator and not self.operator.concluded and profile_id in rp.PROFILE_BY_ID:
            self._configure_profile(profile_id)

    def _configure_profile(self, profile_id: str) -> None:
        assert self.operator is not None
        prof = rp.PROFILE_BY_ID.get(profile_id, rp.PROFILE_BY_ID[rp.DEFAULT_PROFILE])
        self.operator.profile = prof.id
        self.operator.budget = prof.budget

    def set_mission(self, mission_id: str) -> None:
        if self.status == "lobby" and not self.mission_locked and mission_id in mp.MISSION_BY_ID:
            self.mission = mission_id

    # ---- start ---------------------------------------------------------------
    def start(self, profile_id: str | None = None, mission_id: str | None = None) -> bool:
        if self.status != "lobby":
            return False
        if not self.mission_locked and mission_id in mp.MISSION_BY_ID:
            self.mission = mission_id  # type: ignore[assignment]
        mission = mp.MISSION_BY_ID.get(self.mission, mp.MISSION_BY_ID[mp.DEFAULT_MISSION])
        self.stealth_weight = mission.stealth_weight

        self.world = build_world(self.env)
        self.operator = OperatorState(objectives=self._mission_objectives(mission))
        self.soc = SocState()
        self.defender = DefenderState()
        # the mission may force the adversary character (insider / ransomware)
        self._configure_profile(mission.forced_profile or profile_id or rp.DEFAULT_PROFILE)
        self.status = "active"
        self.started_at = time.time()
        prof = rp.PROFILE_BY_ID[self.operator.profile]

        if prof.assumed_breach:
            eps = self.world.by_role("primary_endpoint") or self.world.by_type("endpoint")
            self.operator.flags.update({"planned", "recon_done", "foothold", "internal_recon_done"})
            self.world.attacker.flags["c2"] = True
            self.world.attacker.raise_creds(CredScope.USER)
            if eps:
                eps[0].security_state = SecurityState.COMPROMISED
                self.world.attacker.add_foothold(eps[0].id)
                self.compromise_t[eps[0].id] = 0
                self.red_ever_foothold = True
            self._reveal("internal")

        self._emit("system", f"Mission: {mission.name}",
                   f"{mission.briefing}  (profile: {prof.name})", severity="info",
                   data={"mission": mission.id})
        primary = next((o for o in self.operator.objectives if o["primary"]), None)
        if primary:
            self._emit("objective", "Red mission objective", primary["label"], severity="high",
                       data={"objective": primary["key"]})
        return True

    def _mission_objectives(self, mission: mp.MissionType) -> list[dict]:
        """Topology-derived objectives, re-pointed at the mission's goal."""
        objs = rp.derive_objectives(self.world)  # type: ignore[arg-type]
        pk = mission.primary_objective
        if pk:
            if not any(o["key"] == pk for o in objs):
                objs.insert(0, {"key": pk, "label": rp.objective_label(pk), "met": False, "primary": False})
            for o in objs:
                o["primary"] = (o["key"] == pk)
        for ek in mission.extra_objectives:
            if not any(o["key"] == ek for o in objs):
                objs.append({"key": ek, "label": rp.objective_label(ek), "met": False, "primary": False})
        return objs

    def _obj_met(self, key: str) -> bool:
        """Objective completion incl. op-state keys the world alone can't answer."""
        op = self.operator
        if key == "recon_surface":
            return bool(op and ("surface" in op.flags or "recon_done" in op.flags))
        if key == "initial_foothold":
            return self.red_ever_foothold
        return rp.objective_is_met(key, self.world)  # type: ignore[arg-type]

    # ---- fog of war (Red only) ----------------------------------------------
    def _reveal(self, spec: str) -> None:
        assert self.world is not None and self.operator is not None
        rev = self.operator.revealed
        if spec == "external":
            for a in self.world.all_assets():
                if a.zone in ("perimeter", "dmz", "cloud") or a.type_key in ("email_server", "cloud"):
                    rev.add(a.id)
            eps = self.world.by_role("primary_endpoint") or self.world.by_type("endpoint")
            if eps:
                rev.add(eps[0].id)
        elif spec == "internal":
            for a in self.world.all_assets():
                rev.add(a.id)
        elif spec == "foothold":
            for a in self.world.foothold_assets():
                rev.add(a.id)
        elif spec.startswith("type:"):
            wanted = {t.strip() for t in spec.split(":", 1)[1].split(",")}
            for a in self.world.all_assets():
                if a.type_key in wanted:
                    rev.add(a.id)
        elif spec.startswith("zone:"):
            wanted = {z.strip() for z in spec.split(":", 1)[1].split(",")}
            for a in self.world.all_assets():
                if a.zone in wanted:
                    rev.add(a.id)

    # ====================================================================== #
    #  RED
    # ====================================================================== #
    def execute_red_action(self, player_id: str, action_id: str,
                           target_id: str | None, by_auto: bool = False) -> tuple[bool, str]:
        if self.status != "active" or self.world is None or self.operator is None:
            return False, "operation is not active"
        op, world = self.operator, self.world
        if op.concluded:
            return False, "operation already concluded"
        if not by_auto:
            player = self.players.get(player_id)
            if player is None or player.role != "red":
                return False, "only the Red operator can act"
        action = rp.ACTIONS_BY_ID.get(action_id)
        if action is None:
            return False, "unknown action"
        ok, reason = rp.is_available(action, op, world)
        if not ok:
            return False, reason

        target: AssetInstance | None = None
        if action.target_mode == "select":
            target = world.get(target_id) if target_id else None
            if target is None or target not in rp.valid_targets(action, op, world):
                return False, "select a valid target"
        elif action.target_mode == "auto":
            target = rp.auto_target(action, world)
            if target is None:
                return False, "no suitable target"

        # Blue's standing containment can block Red outright
        if action.id in ("exfil.cloud", "exfil.dns") and "egress_blocked" in self.defense_flags:
            if self.defender:
                self.defender.prevented.add("exfil")
            self._emit("defense", "Exfiltration blocked",
                       f"{action.label} failed — Blue blocked egress / sinkholed DNS first",
                       role="blue", severity="high")
            return True, ""
        if action.id in ("lateral.move", "lateral.pivot_ot") and "segmentation_active" in self.defense_flags \
                and target is not None and target.zone not in world.foothold_zones():
            if self.defender and action.id == "lateral.pivot_ot":
                self.defender.prevented.add("ot_impact")
            self._emit("defense", "Movement blocked",
                       f"{action.label} → {target.name} failed — Blue's emergency segmentation held",
                       role="blue", severity="high", asset_id=target.id, asset_label=target.name)
            return True, ""

        eff_noise = rp.effective_noise(action, op.noise_multiplier, world, target)
        op.noise_spent += eff_noise

        primary_met = any(o["met"] for o in op.objectives if o["primary"])
        overreach = (primary_met and action.objective is None and action.stage == "impact"
                     and action.id != "objective.capture_proof")

        affected = self._apply_effects(action, target)
        op.score += action.score
        if action.once:
            op.done_actions.add(action.id)

        for aid in affected:
            a = world.get(aid)
            if a and a.security_state == SecurityState.COMPROMISED and aid not in self.compromise_t:
                self.compromise_t[aid] = self._t()
                self.red_ever_foothold = True
        if any(world.get(a) and world.get(a).health.value == "down" for a in affected):
            self.impact_occurred = True

        tlabel = target.name if target else None
        sev = "critical" if action.noise >= 9 else "high" if action.noise >= 6 else "medium" if action.noise >= 3 else "low"

        detected = self._record_detection(action, target, sev)
        action_ev = self._emit("action", action.label,
                   action.label + (f" → {tlabel}" if tlabel else "") + f"  ·  noise +{eff_noise}",
                   role="red", severity=sev, asset_id=target.id if target else None,
                   asset_label=tlabel,
                   data={"action_id": action.id, "mitre": action.mitre, "tactic": action.tactic,
                         "noise": eff_noise, "stage": action.stage, "detected": detected})
        # live-fire: if armed and this action maps to a real tool, queue it for async execution
        if self.live_fire and lf.has_spec(action.id):
            action_ev["data"]["live_fire"] = lf.queued_view(action.id)
            self.pending_fire.append({"seq": action_ev["seq"], "action_id": action.id,
                                      "target_id": target.id if target else None})

        if action.intel:
            op.intel.append({"t": self._t(), "text": action.intel})
            self._emit("intel", "Intel", action.intel, role="red", severity="info")
        for aid in affected:
            a = world.get(aid)
            if a:
                self._emit("state", "State change",
                           f"{a.name}: {a.security_state.value} / {a.health.value}", role="red",
                           asset_id=aid, asset_label=a.name,
                           data={"security_state": a.security_state.value, "health": a.health.value})
        op.history.append({"t": self._t(), "action_id": action.id, "label": action.label,
                           "target": tlabel, "noise": eff_noise, "score": action.score})

        self._refresh_objectives()

        if op.noise_spent > op.budget:
            self._emit("opsec", "Detection-risk budget exceeded",
                       f"Noise {op.noise_spent}/{op.budget} — exposure {op.exposure_pct}%.",
                       role="red", severity="high")
        if overreach:
            self._emit("opsec", "Over-reach",
                       "Objective already proven — extra actions add risk for zero gain (§18.3).",
                       role="red", severity="medium")
        self._emit("score", "score", "", role="red", severity="info",
                   data={"red": op.score, "exposure": op.exposure_pct})

        if "conclude" in action.effects:
            self._conclude_red(via_proof=True)
        self._check_match_end()
        return True, ""

    def _record_detection(self, action: rp.RedAction, target: AssetInstance | None, sev: str) -> bool:
        detectable = bool(action.watched_by) or action.tactic in bp.IDENTITY_TACTICS
        if not detectable:
            return False
        self.detectable_actions += 1
        watch_target = target if target is not None else (
            self.world.foothold_assets()[0] if self.world and self.world.foothold_assets() else None)
        cov = bp.detects(action.watched_by, action.tactic, self.world, watch_target, self._monitoring_union())  # type: ignore[arg-type]
        stealthy = self.operator is not None and self.operator.noise_multiplier <= 0.7 and action.noise <= 4
        detected = cov and not stealthy
        if detected:
            self.detected_actions += 1
            self._create_alert(action, target, sev)
        elif action.watched_by:
            self._emit("miss", f"Uncovered: {action.label}",
                       "No detection coverage — this behaviour went unseen", role="soc",
                       severity="medium", data={"action_id": action.id})
        return detected

    def _create_alert(self, action: rp.RedAction, target: AssetInstance | None, sev: str) -> None:
        p_label, p_rank = self._alert_plevel(action)
        alert = {
            "id": f"al{self.alert_seq}", "t": self._t(), "action_id": action.id,
            "label": action.label, "mitre": action.mitre, "tactic": action.tactic, "severity": sev,
            "asset_id": target.id if target else None,
            "asset_label": target.name if target else None,
            "status": "new", "p_label": p_label, "p_rank": p_rank,
        }
        self.alert_seq += 1
        self.alerts.append(alert)
        self._emit("alert", f"ALERT: {action.label}",
                   f"Detected {action.mitre or action.tactic}"
                   + (f" on {target.name}" if target else "") + " — awaiting SOC triage",
                   role="soc", severity=sev, asset_id=target.id if target else None,
                   asset_label=target.name if target else None,
                   data={"alert_id": alert["id"], "action_id": action.id})

    @staticmethod
    def _alert_plevel(action: rp.RedAction) -> tuple[str, int]:
        if action.objective is not None or action.id in ("cred.dcsync", "impact.ransomware", "impact.ot_modify"):
            return "P0", 4
        if action.stage in ("privilege", "lateral"):
            return "P1", 3
        if action.stage in ("initial_access", "persistence", "impact"):
            return "P2", 2
        return "P3", 0

    def _apply_effects(self, action: rp.RedAction, target: AssetInstance | None) -> list[str]:
        assert self.world is not None and self.operator is not None
        world, op = self.world, self.operator
        affected: list[str] = []
        for eff in action.effects:
            if eff == "compromise":
                if target is not None:
                    target.security_state = SecurityState.COMPROMISED
                    world.attacker.add_foothold(target.id)
                    op.revealed.add(target.id)
                    affected.append(target.id)
            elif eff == "suspicious":
                if target is not None and target.security_state == SecurityState.SAFE:
                    target.security_state = SecurityState.SUSPICIOUS
                    affected.append(target.id)
            elif eff == "down":
                if target is not None:
                    target.health = Health.DOWN
                    target.security_state = SecurityState.COMPROMISED
                    affected.append(target.id)
            elif eff == "degrade":
                if target is not None:
                    target.health = Health.DEGRADED
                    affected.append(target.id)
            elif eff == "exfiltrate":
                world.attacker.flags["exfiltrated"] = True
                if target is not None:
                    target.props["exfiltrated"] = True
            elif eff.startswith("creds:"):
                world.attacker.raise_creds(CredScope(eff.split(":", 1)[1]))
            elif eff.startswith("flag:"):
                world.attacker.flags[eff.split(":", 1)[1]] = True
            elif eff.startswith("progress:"):
                op.flags.add(eff.split(":", 1)[1])
            elif eff.startswith("reveal:"):
                self._reveal(eff.split(":", 1)[1])
            elif eff.startswith("disable_control:"):
                ct = eff.split(":", 1)[1]
                if ct not in world.attacker.disabled_control_types:
                    world.attacker.disabled_control_types.append(ct)
            elif eff.startswith("evasion:"):
                op.noise_multiplier = max(0.5, op.noise_multiplier - float(eff.split(":", 1)[1]))
            elif eff == "resilience":
                world.attacker.flags["c2_resilient"] = True
        return affected

    def _refresh_objectives(self) -> None:
        assert self.world is not None and self.operator is not None
        for o in self.operator.objectives:
            if not o["met"] and self._obj_met(o["key"]):
                o["met"] = True
                bonus = 200 if o["primary"] else 75
                self.operator.score += bonus
                self._emit("objective", "Objective achieved",
                           f"{o['label']}  (+{bonus})", role="red", severity="critical",
                           data={"objective": o["key"], "primary": o["primary"]})

    def _conclude_red(self, via_proof: bool) -> None:
        assert self.operator is not None
        op = self.operator
        if op.concluded:
            return
        prof = rp.PROFILE_BY_ID[op.profile]
        primary_met = any(o["met"] for o in op.objectives if o["primary"])
        any_met = any(o["met"] for o in op.objectives)
        secondary_met = sum(1 for o in op.objectives if o["met"] and not o["primary"])
        remaining = max(0, op.budget - op.noise_spent)
        overspend = max(0, op.noise_spent - op.budget)
        # Mission stealth weight: 0 => stealth irrelevant (pen test/purple/BAS); >1 => stealth paramount.
        stealth_bonus = round(remaining * self.stealth_weight)
        overspend_penalty = round(overspend * prof.overspend_penalty * self.stealth_weight)
        discipline_bonus = 60 if (via_proof and any_met and op.exposure_pct <= 80) else 0
        total = op.score + stealth_bonus + discipline_bonus - overspend_penalty
        op.concluded = True
        op.final = {
            "objective_met": primary_met, "any_objective_met": any_met, "secondary_met": secondary_met,
            "action_score": op.score, "stealth_bonus": stealth_bonus,
            "discipline_bonus": discipline_bonus, "overspend_penalty": overspend_penalty,
            "total_score": total, "noise_spent": op.noise_spent, "budget": op.budget,
            "exposure_pct": op.exposure_pct, "actions_taken": len(op.history),
            "objectives": [dict(o) for o in op.objectives],
        }

    def conclude_manual(self, player_id: str) -> bool:
        p = self.players.get(player_id)
        if p is None or p.role not in INTERACTIVE_ROLES:
            return False
        if self.status != "active":
            return False
        self._finish(self.match_result or "draw")
        return True

    # ====================================================================== #
    #  SOC
    # ====================================================================== #
    def execute_soc_action(self, player_id: str, action_id: str,
                           target_id: str | None, by_auto: bool = False) -> tuple[bool, str]:
        if self.status != "active" or self.world is None or self.soc is None:
            return False, "operation is not active"
        ss, world = self.soc, self.world
        if ss.concluded:
            return False, "soc concluded"
        if not by_auto:
            player = self.players.get(player_id)
            if player is None or player.role != "soc":
                return False, "only the SOC analyst can act"
        action = sp.SOC_ACTIONS_BY_ID.get(action_id)
        if action is None:
            return False, "unknown action"
        ok, reason = sp.is_available(action, ss, world)
        if not ok:
            return False, reason

        # per-alert actions
        alert = None
        if action.target_mode == "alert":
            alert = next((a for a in self.alerts if a["id"] == target_id), None)
            want = "new" if action.alert_filter == "new" else "triaged"
            if alert is None or alert["status"] != want:
                return False, "select a valid alert"

        msg = self._apply_soc_effects(action, alert, ss)
        ss.score += action.score
        if action.once:
            ss.done_actions.add(action.id)
        self._emit("soc", action.label, action.label + (f"  ·  {msg}" if msg else ""),
                   role="soc", severity="info",
                   data={"action_id": action.id, "ref": action.ref})
        ss.history.append({"t": self._t(), "action_id": action.id, "label": action.label, "score": action.score})
        self._emit("score", "score", "", role="soc", severity="info", data={"soc": ss.score})
        self._check_match_end()
        return True, ""

    def _apply_soc_effects(self, action: sp.SocAction, alert: dict | None, ss: SocState) -> str:
        assert self.world is not None
        notes: list[str] = []
        for eff in action.effects:
            if eff.startswith("monitor:"):
                ss.monitoring.add(eff.split(":", 1)[1])
                notes.append("coverage up")
            elif eff.startswith("cap:"):
                cap = eff.split(":", 1)[1]
                ss.capabilities.add(cap)
                if cap == "scoped":
                    self.shared_scoped = True
                    notes.append("intrusion scoped")
                elif cap == "hunted":
                    notes.append("hunt complete")
            elif eff == "triage" and alert is not None:
                alert["status"] = "triaged"
                ss.triaged += 1
                ss.mtta_samples.append(self._t() - alert["t"])
                notes.append(f"classified {alert['p_label']}")
            elif eff == "escalate" and alert is not None:
                alert["status"] = "escalated"
                ss.escalated += 1
                if alert["asset_id"]:
                    self.incident_declared.add(alert["asset_id"])
                if alert["p_rank"] >= 3:
                    ss.score += 10  # correctly escalated a genuinely severe alert
                self._emit("escalation", f"Incident declared ({alert['p_label']})",
                           f"{alert['label']}" + (f" on {alert['asset_label']}" if alert['asset_label'] else "")
                           + " — handed to IR", role="soc", severity=alert["severity"],
                           asset_id=alert["asset_id"], asset_label=alert["asset_label"],
                           data={"alert_id": alert["id"], "p_label": alert["p_label"]})
                notes.append("escalated to IR")
        return "; ".join(notes)

    def _conclude_soc(self) -> None:
        if self.soc is None or self.soc.concluded:
            return
        ss = self.soc
        mtta = round(sum(ss.mtta_samples) / len(ss.mtta_samples)) if ss.mtta_samples else 0
        open_alerts = sum(1 for a in self.alerts if a["status"] == "new")
        total = ss.score
        ss.concluded = True
        ss.final = {
            "coverage_pct": self.coverage_pct, "detected": self.detected_actions,
            "detectable": self.detectable_actions, "triaged": ss.triaged, "escalated": ss.escalated,
            "mtta_s": mtta, "open_alerts": open_alerts, "action_score": ss.score,
            "total_score": total, "actions_taken": len(ss.history),
        }

    # ====================================================================== #
    #  BLUE
    # ====================================================================== #
    def execute_blue_action(self, player_id: str, action_id: str,
                            target_id: str | None, by_auto: bool = False) -> tuple[bool, str]:
        if self.status != "active" or self.world is None or self.defender is None:
            return False, "operation is not active"
        bs, world = self.defender, self.world
        if bs.concluded:
            return False, "defense already concluded"
        if not by_auto:
            player = self.players.get(player_id)
            if player is None or player.role != "blue":
                return False, "only the Blue defender can act"
        action = bp.BLUE_ACTIONS_BY_ID.get(action_id)
        if action is None:
            return False, "unknown action"
        ok, reason = bp.is_available(action, bs, world)
        if not ok:
            return False, reason

        target: AssetInstance | None = None
        if action.target_mode == "select":
            target = world.get(target_id) if target_id else None
            if target is None or target not in bp.valid_targets(action, bs, world):
                return False, "select a valid target"

        msgs = self._apply_blue_effects(action, target, bs, world)
        bs.score += action.score
        if action.once:
            bs.done_actions.add(action.id)

        tlabel = target.name if target else None
        self._emit("response", action.label,
                   action.label + (f" → {tlabel}" if tlabel else "") + (f"  ·  {msgs}" if msgs else ""),
                   role="blue", severity="high", asset_id=target.id if target else None,
                   asset_label=tlabel, data={"action_id": action.id, "framework": action.framework})
        for aid in self._last_state_changes:
            a = world.get(aid)
            if a:
                self._emit("state", "State change",
                           f"{a.name}: {a.security_state.value} / {a.health.value}", role="blue",
                           asset_id=aid, asset_label=a.name,
                           data={"security_state": a.security_state.value, "health": a.health.value})
        bs.history.append({"t": self._t(), "action_id": action.id, "label": action.label,
                           "target": tlabel, "score": action.score})
        self._emit("score", "score", "", role="blue", severity="info", data={"blue": bs.score})

        if "conclude" in action.effects:
            self._finish(self.match_result or "draw")
        self._check_match_end()
        return True, ""

    def _apply_blue_effects(self, action: bp.BlueAction, target: AssetInstance | None,
                            bs: DefenderState, world: World) -> str:
        self._last_state_changes = []
        notes: list[str] = []
        a = world.attacker
        scoped = "scoped" in bs.capabilities or self.shared_scoped
        for eff in action.effects:
            if eff.startswith("cap:"):
                cap = eff.split(":", 1)[1]
                bs.capabilities.add(cap)
                if cap == "scoped":
                    self.shared_scoped = True
            elif eff.startswith("monitor:"):
                bs.monitoring.add(eff.split(":", 1)[1])
            elif eff.startswith("flag:"):
                fl = eff.split(":", 1)[1]
                self.defense_flags.add(fl)
                if fl == "egress_blocked" and a.flags.get("staged") and not a.flags.get("exfiltrated"):
                    bs.prevented.add("exfil")
                    notes.append("staged exfil cut off")
                else:
                    notes.append("active")
            elif eff == "isolate" and target is not None:
                is_dc = target.type_key == "domain_controller"
                if is_dc and "dc_gate" not in bs.capabilities:
                    bs.score -= 15
                    notes.append("DC isolated without approval — auth disrupted (−15)")
                others = [f for f in a.footholds if f != target.id]
                if others and not scoped:
                    bs.score -= 5
                    notes.append(f"partial — {len(others)} foothold(s) still unscoped")
                else:
                    bs.score += 10
                if target.id in self.incident_declared:
                    bs.score += 5
                    notes.append("on a SOC-escalated incident")
                target.security_state = SecurityState.CONTAINED
                if target.id in a.footholds:
                    a.footholds.remove(target.id)
                bs.contained_assets.add(target.id)
                if target.id in self.compromise_t:
                    bs.mttc_samples.append(self._t() - self.compromise_t[target.id])
                self._last_state_changes.append(target.id)
            elif eff == "creds_reset":
                if a.flags.get("persistence_strong") and "domain_eradicated" not in self.defense_flags:
                    notes.append("reset ineffective — Golden Ticket persists (needs krbtgt ×2)")
                else:
                    a.cred_scope = CredScope.USER
                    notes.append("stolen privilege revoked")
            elif eff == "eradicate_persistence":
                removed = [k for k in ("persistence", "cloud_persistence") if a.flags.get(k)]
                for k in removed:
                    a.flags[k] = False
                bs.eradicated = True
                notes.append(f"removed {len(removed)} persistence mechanism(s)" if removed else "no persistence found")
            elif eff == "eradicate_domain":
                a.flags["persistence_strong"] = False
                self.defense_flags.add("domain_eradicated")
                if a.cred_scope.rank >= CredScope.PRIVILEGED.rank:
                    a.cred_scope = CredScope.USER
                bs.eradicated = True
                notes.append("krbtgt reset ×2 — Golden Tickets invalidated")
            elif eff == "reimage" and target is not None:
                target.security_state = SecurityState.CONTAINED
                target.health = Health.NOMINAL
                self._last_state_changes.append(target.id)
                notes.append("rebuilt from clean baseline")
            elif eff == "restore" and target is not None:
                was_down = target.health.value == "down"
                target.health = Health.NOMINAL
                target.security_state = SecurityState.SAFE
                if target.id in a.footholds:
                    a.footholds.remove(target.id)
                self._last_state_changes.append(target.id)
                if was_down:
                    if a.flags.get("ransomware"):
                        bs.prevented.add("ransomware")
                    if a.flags.get("ot_impact"):
                        bs.prevented.add("ot_impact")
                notes.append("restored from clean backup")
        return "; ".join(notes)

    def _conclude_blue(self) -> None:
        assert self.defender is not None and self.world is not None
        bs = self.defender
        if bs.concluded:
            return
        evicted = self._eviction_complete()
        mttc = round(sum(bs.mttc_samples) / len(bs.mttc_samples)) if bs.mttc_samples else 0
        eviction_bonus = 200 if evicted else 0
        prevention_bonus = 75 * len(bs.prevented)
        total = bs.score + eviction_bonus + prevention_bonus
        bs.concluded = True
        bs.final = {
            "eviction_complete": evicted, "coverage_pct": self.coverage_pct,
            "detected": self.detected_actions, "detectable": self.detectable_actions,
            "mttc_s": mttc, "contained": len(bs.contained_assets), "footholds_total": len(self.compromise_t),
            "prevented": sorted(bs.prevented), "action_score": bs.score,
            "eviction_bonus": eviction_bonus, "prevention_bonus": prevention_bonus,
            "total_score": total, "actions_taken": len(bs.history),
        }

    # ---- match resolution ----------------------------------------------------
    def _eviction_complete(self) -> bool:
        if self.world is None or not self.red_ever_foothold:
            return False
        a = self.world.attacker
        no_persist = not any(a.flags.get(k) for k in ("persistence", "persistence_strong", "cloud_persistence"))
        return not a.has_foothold() and no_persist

    def _check_match_end(self) -> None:
        if self.status != "active" or self.operator is None:
            return
        if any(o["met"] for o in self.operator.objectives if o["primary"]):
            self._finish("red")
        elif self._eviction_complete():
            self._finish("blue")

    def _finish(self, result: str) -> None:
        if self.status == "completed":
            return
        self.match_result = result
        self._conclude_red(via_proof=any(o["met"] for o in (self.operator.objectives if self.operator else [])))
        self._conclude_soc()
        self._conclude_blue()
        self.status = "completed"
        verdict = {"red": "Red achieved the objective — attacker wins.",
                   "blue": "Blue fully evicted the adversary — defender wins.",
                   "draw": "Operation concluded."}.get(result, "Operation concluded.")
        self._emit("system", "Match concluded", verdict, role="system", severity="critical",
                   data={"result": result})
        # Build the all-teams After-Action Report (the live mission report).
        try:
            self.report = live_report.build_report(self)
        except Exception:  # a report failure must never break match conclusion
            self.report = None
        # Persist report to DB so it survives restart and shows in Reports page.
        if self.report is not None:
            try:
                from app.db.base import SessionLocal
                from app.db.models import Report as ReportRow, Run as RunRow
                db = SessionLocal()
                try:
                    if db.get(RunRow, self.id) is None:
                        teams = self.report.get("teams", {})
                        scores = {role: t.get("score", 0) for role, t in teams.items()}
                        outcome = self.report.get("outcome", {})
                        run_row = RunRow(
                            id=self.id, scenario_id=self.scenario.id if self.scenario else "live",
                            scenario_name=f"[LIVE] {self.scenario_name}",
                            operator=self.players[self.host_id].name if self.host_id in self.players else "live",
                            status="completed", focus_role="blue", config={}, environment_spec={},
                            duration_s=self.report.get("duration_s", 0), scores=scores,
                            kpis={}, summary={"live_session": True, "result": result,
                                              "verdict": verdict, "mission": self.mission,
                                              "objective_met": outcome.get("objective_met", False)},
                            objectives={}, events=self.events[-50:], final_assets=[],
                        )
                        report_row = ReportRow(run_id=self.id, content=self.report)
                        db.add(run_row)
                        db.add(report_row)
                        db.commit()
                finally:
                    db.close()
            except Exception as exc:
                import sys, traceback
                print(f"[LIVE] DB persist failed: {exc}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    # ---- snapshots -----------------------------------------------------------
    def list_summary(self) -> dict:
        roles: dict[str, int] = {}
        for p in self.players.values():
            if p.role:
                roles[p.role] = roles.get(p.role, 0) + 1
        guided = getattr(self, "guided", None)
        return {"id": self.id, "scenario_name": self.scenario_name, "status": self.status,
                "players": sum(1 for p in self.players.values() if p.connected) or len(self.players),
                "player_count": len(self.players), "roles": roles, "created_at": self.created_at,
                "guided": guided is not None,
                "scenario_id": guided.scenario_id if guided is not None else None}

    def _asset_public(self) -> list[dict]:
        if self.world is None:
            return []
        revealed = self.operator.revealed if self.operator else set()
        return [{
            "id": a.id, "type": a.type_key, "zone": a.zone, "criticality": a.criticality,
            "role": a.role, "revealed": a.id in revealed, "name": a.name,
            "security_state": a.security_state.value, "health": a.health.value,
            "is_foothold": a.id in self.world.attacker.footholds,
            "incident": a.id in self.incident_declared,
        } for a in self.world.all_assets()]

    def _operator_public(self) -> dict | None:
        if self.operator is None or self.world is None:
            return None
        op, world = self.operator, self.world
        actions = []
        for act in rp.RED_ACTIONS:
            avail, reason = rp.is_available(act, op, world)
            if avail and act.id in ("exfil.cloud", "exfil.dns") and "egress_blocked" in self.defense_flags:
                avail, reason = False, "egress blocked by Blue"
            targets = [{"id": t.id, "name": t.name, "type": t.type_key, "zone": t.zone}
                       for t in rp.valid_targets(act, op, world)]
            eff = rp.effective_noise(act, op.noise_multiplier, world,
                                     rp.auto_target(act, world) if act.target_mode == "auto" else None)
            actions.append({
                "id": act.id, "stage": act.stage, "label": act.label, "description": act.description,
                "tactic": act.tactic, "mitre": act.mitre, "base_noise": act.noise, "noise": eff,
                "score": act.score, "available": avail, "reason": reason,
                "done": act.id in op.done_actions, "target_mode": act.target_mode,
                "target_type": act.target_type, "targets": targets, "watched_by": list(act.watched_by),
                "objective": act.objective, "opsec": act.opsec,
            })
        return {
            "profile": op.profile, "budget": op.budget, "noise_spent": op.noise_spent,
            "exposure_pct": op.exposure_pct, "noise_multiplier": round(op.noise_multiplier, 2),
            "score": op.score, "concluded": op.concluded, "final": op.final,
            "cred_scope": world.attacker.cred_scope.value, "footholds": list(world.attacker.footholds),
            "objectives": [dict(o) for o in op.objectives], "intel": op.intel, "history": op.history,
            "flags": sorted(op.flags),
            "world_flags": sorted(k for k, v in world.attacker.flags.items() if v),
            "actions": actions,
        }

    def _soc_objectives(self) -> list[dict]:
        ss = self.soc
        assert ss is not None
        open_alerts = sum(1 for a in self.alerts if a["status"] == "new")
        return [
            {"key": "monitor", "label": "Establish detection coverage", "met": bool(ss.monitoring)},
            {"key": "triage", "label": "Triage incoming alerts", "met": ss.triaged > 0 and open_alerts == 0},
            {"key": "escalate", "label": "Escalate confirmed incidents", "met": ss.escalated > 0},
            {"key": "hunt", "label": "Hunt for what didn't alert", "met": "hunted" in ss.capabilities},
        ]

    def _soc_public(self) -> dict | None:
        if self.soc is None or self.world is None:
            return None
        ss, world = self.soc, self.world
        new_alerts = [a for a in self.alerts if a["status"] == "new"]
        triaged_alerts = [a for a in self.alerts if a["status"] == "triaged"]
        actions = []
        for act in sp.SOC_ACTIONS:
            avail, reason = sp.is_available(act, ss, world)
            targets: list[dict] = []
            if act.target_mode == "alert":
                pool = new_alerts if act.alert_filter == "new" else triaged_alerts
                targets = [{"id": al["id"], "name": f"{al['label']}"
                            + (f" · {al['asset_label']}" if al["asset_label"] else "")
                            + f" ({al['p_label']})"} for al in pool]
                if not targets:
                    avail, reason = False, ("no new alerts" if act.alert_filter == "new" else "no triaged alerts")
            actions.append({
                "id": act.id, "stage": act.stage, "label": act.label, "description": act.description,
                "ref": act.ref, "score": act.score, "available": avail, "reason": reason,
                "done": act.id in ss.done_actions, "target_mode": act.target_mode,
                "note": act.note, "targets": targets,
            })
        mtta = round(sum(ss.mtta_samples) / len(ss.mtta_samples)) if ss.mtta_samples else 0
        return {
            "score": ss.score, "concluded": ss.concluded, "final": ss.final,
            "monitoring": sorted(ss.monitoring), "capabilities": sorted(ss.capabilities),
            "coverage_pct": self.coverage_pct, "detected": self.detected_actions,
            "detectable": self.detectable_actions, "triaged": ss.triaged, "escalated": ss.escalated,
            "mtta_s": mtta, "objectives": self._soc_objectives(), "history": ss.history,
            "alerts": list(self.alerts), "actions": actions,
        }

    def _blue_objectives(self) -> list[dict]:
        assert self.world is not None and self.defender is not None
        a = self.world.attacker
        no_persist = not any(a.flags.get(k) for k in ("persistence", "persistence_strong", "cloud_persistence"))
        recovered = self.impact_occurred and not any(x.health.value == "down" for x in self.world.all_assets())
        return [
            {"key": "detect", "label": "Detect the intrusion", "met": self.detected_actions > 0},
            {"key": "contain", "label": "Contain compromised hosts", "met": len(self.defender.contained_assets) > 0},
            {"key": "eradicate", "label": "Eradicate persistence & stolen creds",
             "met": self.red_ever_foothold and no_persist and self.defender.eradicated},
            {"key": "recover", "label": "Recover impacted systems", "met": recovered},
            {"key": "evict", "label": "Fully evict the adversary", "met": self._eviction_complete()},
        ]

    def _defender_public(self) -> dict | None:
        if self.defender is None or self.world is None:
            return None
        bs, world = self.defender, self.world
        actions = []
        for act in bp.BLUE_ACTIONS:
            avail, reason = bp.is_available(act, bs, world)
            targets = [{"id": t.id, "name": t.name, "type": t.type_key, "zone": t.zone}
                       for t in bp.valid_targets(act, bs, world)]
            actions.append({
                "id": act.id, "stage": act.stage, "label": act.label, "description": act.description,
                "framework": act.framework, "score": act.score, "available": avail, "reason": reason,
                "done": act.id in bs.done_actions, "target_mode": act.target_mode,
                "target_type": act.target_type, "note": act.note, "targets": targets,
            })
        mttc = round(sum(bs.mttc_samples) / len(bs.mttc_samples)) if bs.mttc_samples else 0
        return {
            "score": bs.score, "concluded": bs.concluded, "final": bs.final,
            "monitoring": sorted(bs.monitoring), "capabilities": sorted(bs.capabilities),
            "coverage_pct": self.coverage_pct, "detected": self.detected_actions,
            "detectable": self.detectable_actions, "mttc_s": mttc,
            "contained": len(bs.contained_assets), "footholds_total": len(self.compromise_t),
            "prevented": sorted(bs.prevented), "defense_flags": sorted(self.defense_flags),
            "objectives": self._blue_objectives(), "history": bs.history, "actions": actions,
        }

    def snapshot(self) -> dict:
        from . import guided_runtime
        return {
            "type": "snapshot",
            "guided": guided_runtime.snapshot(self),
            "sim": self.sim.snapshot() if self.sim else None,
            "session": {"id": self.id, "scenario_name": self.scenario_name,
                        "status": self.status, "host_id": self.host_id,
                        "match_result": self.match_result, "mission": self.mission,
                        "mission_locked": self.mission_locked, "live_fire": self.live_fire},
            "missions": [mp.public(m) for m in mp.MISSIONS],
            "mission": mp.public(mp.MISSION_BY_ID[self.mission]),
            "scenario": {"name": self.scenario.name, "description": self.scenario.description,
                         "type": self.scenario.type, "label": self.scenario.label,
                         "phases": self.scenario.phases,
                         "objectives": self.scenario.objectives.model_dump()},
            "players": [p.public() for p in self.players.values()],
            "stages": [{"id": s.id, "name": s.name, "summary": s.summary, "ref": s.ref} for s in rp.RED_STAGES],
            "blue_stages": [{"id": s.id, "name": s.name, "summary": s.summary, "ref": s.ref} for s in bp.BLUE_STAGES],
            "soc_stages": [{"id": s.id, "name": s.name, "summary": s.summary, "ref": s.ref} for s in sp.SOC_STAGES],
            "profiles": [{"id": p.id, "name": p.name, "description": p.description,
                          "budget": p.budget, "traits": list(p.traits),
                          "assumed_breach": p.assumed_breach} for p in rp.ADVERSARY_PROFILES],
            "roles": [{"id": r, "interactive": r in INTERACTIVE_ROLES} for r in SELECTABLE_ROLES],
            "auto": {r: self.is_auto(r) for r in INTERACTIVE_ROLES},
            "operator": self._operator_public(),
            "soc": self._soc_public(),
            "defender": self._defender_public(),
            "assets": self._asset_public(),
            "events": self.events,
            "report": self.report,
        }
