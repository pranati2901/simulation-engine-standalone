"""Core enumerations for the simulation engine.

String-valued enums so they serialise cleanly to JSON for the timeline, API and DB.
"""
from __future__ import annotations

from enum import Enum


class SecurityState(str, Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    COMPROMISED = "compromised"
    CONTAINED = "contained"  # blue isolated/remediated the asset


class Health(str, Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    DOWN = "down"


class Side(str, Enum):
    RED = "red"
    BLUE = "blue"
    SOC = "soc"
    MGMT = "mgmt"
    OT = "ot"
    SYSTEM = "system"


# The roles an operator can pick as the focus "lens" (every role still acts).
FOCUS_ROLES = (Side.RED, Side.BLUE, Side.SOC, Side.MGMT, Side.OT)


class PLevel(int, Enum):
    """SOC incident priority. Higher = more severe (P0 is worst)."""
    NONE = 0   # P3 / informational
    P2 = 2     # confirmed malicious, single host
    P1 = 3     # privileged host / multi-host
    P0 = 4     # domain breach / ransomware / OT impact

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
        """Detection/response latency multiplier — harder = slower defenders."""
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
    ATTACK = "attack"        # red technique applied (success)
    BLOCK = "block"          # technique prevented by a control
    FAIL = "fail"            # technique failed (preconditions unmet)
    TELEMETRY = "telemetry"  # asset/technique log line (feeds the console)
    DETECTION = "detection"  # a control raised an alert (feeds the alert feed)
    RESPONSE = "response"    # blue/soc containment action
    INJECT = "inject"        # scripted/manual inject surfaced to the operator
    OBJECTIVE = "objective"  # objective progress
    STATE = "state"          # asset state/health change (drives the network map)
    SCORE = "score"          # score / kpi update
    TASK = "task"            # a team workflow step changed status (drives per-role sub-reports)
    ESCALATION = "escalation"  # SOC priority / escalation change
    DECISION = "decision"    # a decision-gate outcome (e.g. isolate-DC requires approval)
    NOTIFY = "notify"        # management notification / regulatory clock


class AssetCategory(str, Enum):
    ENDPOINT = "endpoint"
    SERVER = "server"
    IDENTITY = "identity"
    NETWORK = "network"
    SECURITY = "security"
    DATA = "data"
    CLOUD = "cloud"
    OT = "ot"


class CredScope(str, Enum):
    NONE = "none"
    USER = "user"
    PRIVILEGED = "privileged"
    DOMAIN_ADMIN = "domain_admin"

    @property
    def rank(self) -> int:
        return {"none": 0, "user": 1, "privileged": 2, "domain_admin": 3}[self.value]
