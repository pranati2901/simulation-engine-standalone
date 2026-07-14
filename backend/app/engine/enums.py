"""Core enumerations for the simulation engine.

Domain-agnostic. Domain plugins (aerospace, railway, hospital, ...) may extend these
with their own vocabularies via plugin-registered catalogs, but the engine itself
only ever reasons about the values below.

String-valued enums so they serialise cleanly to JSON for the timeline, API and DB.
"""
from __future__ import annotations

from enum import Enum


class ActorState(str, Enum):
    """Generic lifecycle state of an actor/asset in the world.

    Was GoalCert's SecurityState (safe/suspicious/compromised/contained). Renamed so a
    railway signal, a hospital ward, or an aircraft subsystem can all use it.
    """
    NOMINAL = "nominal"
    AT_RISK = "at_risk"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERED = "recovered"


class Health(str, Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    DOWN = "down"


class Side(str, Enum):
    """Generic participant lens. Domain plugins map their own role names onto these
    via RoleInfo (see workflows.py) — e.g. aerospace might have 'ops'/'maintenance'/
    'safety'/'atc', all still bucketed as PRIMARY/RESPONSE/OVERSIGHT/SYSTEM here so the
    engine's scheduler and scoring stay generic.
    """
    PRIMARY = "primary"      # the actor(s) driving the incident (was RED)
    RESPONSE = "response"    # the actor(s) responding to it (was BLUE)
    MONITOR = "monitor"      # detection/triage layer (was SOC)
    OVERSIGHT = "mgmt"       # management/escalation layer (was MGMT)
    OPERATIONS = "ops"       # domain operations layer (was OT)
    SYSTEM = "system"


FOCUS_ROLES = (Side.PRIMARY, Side.RESPONSE, Side.MONITOR, Side.OVERSIGHT, Side.OPERATIONS)


class PLevel(int, Enum):
    """Generic incident priority. Higher = more severe (P0 is worst)."""
    NONE = 0
    P2 = 2
    P1 = 3
    P0 = 4

    @property
    def label(self) -> str:
        return {0: "P3", 2: "P2", 3: "P1", 4: "P0"}[self.value]


class Difficulty(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    EXPERT = "Expert"

    @property
    def rank(self) -> int:
        return {"Easy": 1, "Medium": 2, "Hard": 3, "Expert": 4}[self.value]

    @property
    def factor(self) -> float:
        return {"Easy": 0.5, "Medium": 1.0, "Hard": 1.5, "Expert": 2.5}[self.value]


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class EventType(str, Enum):
    SYSTEM = "system"        # engine lifecycle / briefing
    PHASE = "phase"          # phase transition
    ACTION = "action"        # a primary-actor action was applied (success) — was ATTACK
    BLOCK = "block"          # action prevented by a control/resource
    FAIL = "fail"            # action failed (preconditions unmet)
    TELEMETRY = "telemetry"  # asset/action log line (feeds the console)
    DETECTION = "detection"  # a control raised an alert (feeds the alert feed)
    RESPONSE = "response"    # response-team action
    INJECT = "inject"        # scripted/manual inject surfaced to the operator
    OBJECTIVE = "objective"  # objective progress
    STATE = "state"          # actor state/health change (drives the world map)
    SCORE = "score"          # score / kpi update
    TASK = "task"            # a role's workflow step changed status
    ESCALATION = "escalation"  # priority / escalation change
    DECISION = "decision"    # a decision-gate outcome (e.g. action requires approval)
    NOTIFY = "notify"        # management notification / external clock
    SCENARIO_SPAWN = "scenario_spawn"  # cascade: this run spawned a child scenario (Dynamic Scenario Graph)


class ActorCategory(str, Enum):
    """Generic actor bucket. Domain plugins register concrete actor types (e.g.
    'aircraft_hydraulic_system', 'ward_hvac', 'signal_block') tagged with one of these.
    """
    EQUIPMENT = "equipment"
    PERSONNEL = "personnel"
    FACILITY = "facility"
    NETWORK = "network"
    CONTROL_SYSTEM = "control_system"
    DATA = "data"
    ENVIRONMENT = "environment"
    EXTERNAL = "external"


class AuthorityScope(str, Enum):
    """Generic replacement for GoalCert's CredScope (credential/authority level an
    actor holds — e.g. how much control-room authority, clearance, or system access).
    """
    NONE = "none"
    LIMITED = "limited"
    ELEVATED = "elevated"
    FULL = "full"

    @property
    def rank(self) -> int:
        return {"none": 0, "limited": 1, "elevated": 2, "full": 3}[self.value]
