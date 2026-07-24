"""Tripwire scenario engine — deterministic state machine for the WannaCry simulation.

States: INIT → BRIEFING → SCENE[0..10] → DEBRIEF → ASSESSMENT → RESULTS → END
Each scene: ENTER → OBSERVE → IDENTIFY → RESPOND → RESOLVE

The engine is the sole authority for state and score. The client is a renderer.
All state changes are recorded as append-only events for replay and audit.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
#  Enums
# ---------------------------------------------------------------------------
class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    COMPLETED = "completed"


class Phase(str, Enum):
    INIT = "init"
    BRIEFING = "briefing"
    SCENE = "scene"
    DEBRIEF = "debrief"
    ASSESSMENT = "assessment"
    RESULTS = "results"
    END = "end"


class SceneSubState(str, Enum):
    ENTER = "enter"
    OBSERVE = "observe"
    IDENTIFY = "identify"
    RESPOND = "respond"
    RESOLVE = "resolve"


class Mode(str, Enum):
    GUIDED = "guided"
    STANDARD = "standard"
    PRESSURE = "pressure"


class ResponseQuality(str, Enum):
    OPTIMAL = "optimal"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


# ---------------------------------------------------------------------------
#  Data models
# ---------------------------------------------------------------------------
@dataclass
class NetworkState:
    """Projected state of the hospital network."""
    containment_index: int = 100
    infected_count: int = 0
    encrypted_count: int = 0
    isolated_count: int = 0
    total_hosts: int = 250
    backup_destroyed: bool = False

    def infected_ratio(self) -> float:
        return self.infected_count / self.total_hosts if self.total_hosts else 0.0

    def snapshot(self) -> dict:
        return {
            "containment_index": self.containment_index,
            "infected": self.infected_count,
            "encrypted": self.encrypted_count,
            "isolated": self.isolated_count,
            "total_hosts": self.total_hosts,
            "backup_destroyed": self.backup_destroyed,
            "infected_ratio": round(self.infected_ratio(), 3),
        }


@dataclass
class SceneDecision:
    """A student's decision for one scene."""
    scene_index: int
    identify_choice: str
    identify_correct: bool
    actions: list[str]
    response_quality: str  # optimal|acceptable|poor
    latency_ms: int = 0
    hints_used: int = 0
    score_delta: dict = field(default_factory=dict)


@dataclass
class Scores:
    """5-dimension scoring accumulator."""
    detection_points: float = 0.0
    detection_max: float = 0.0
    response_points: float = 0.0
    response_max: float = 0.0
    containment: int = 100  # final containment index
    speed_points: float = 0.0
    speed_max: float = 0.0
    knowledge_points: float = 0.0
    knowledge_max: float = 0.0
    hint_penalty: float = 0.0

    def detection_pct(self) -> float:
        return (self.detection_points / self.detection_max * 100) if self.detection_max else 0.0

    def response_pct(self) -> float:
        return (self.response_points / self.response_max * 100) if self.response_max else 0.0

    def speed_pct(self) -> float:
        return (self.speed_points / self.speed_max * 100) if self.speed_max else 0.0

    def knowledge_pct(self) -> float:
        return (self.knowledge_points / self.knowledge_max * 100) if self.knowledge_max else 0.0

    def composite(self, mode: Mode) -> float:
        """Weighted composite score (0-100). Weights from SRS §12.1."""
        det = self.detection_pct()
        resp = self.response_pct()
        cont = float(self.containment)
        spd = self.speed_pct()
        know = self.knowledge_pct()

        if mode == Mode.GUIDED:
            # No timers in guided — redistribute speed weight
            return 0.28 * det + 0.34 * resp + 0.28 * cont + 0.10 * know
        return 0.25 * det + 0.30 * resp + 0.25 * cont + 0.10 * spd + 0.10 * know

    def grade(self, mode: Mode) -> tuple[str, bool]:
        """(grade_label, passed). From SRS §12.4."""
        c = self.composite(mode)
        if c >= 90:
            return "Distinction — Incident Lead", True
        if c >= 75:
            return "Pass — Effective Responder", True
        if c >= 60:
            return "Pass — Developing", True
        return "Not yet — Retake recommended", False

    def dimensions(self, mode: Mode) -> dict:
        return {
            "detection": round(self.detection_pct(), 1),
            "response": round(self.response_pct(), 1),
            "containment": self.containment,
            "speed": round(self.speed_pct(), 1),
            "knowledge": round(self.knowledge_pct(), 1),
            "composite": round(self.composite(mode), 1),
        }


# ---------------------------------------------------------------------------
#  Session — the main state machine
# ---------------------------------------------------------------------------
class TripwireSession:
    """One student's run of the WannaCry scenario."""

    HARD_FAIL_THRESHOLD = 0.80  # infected ratio that triggers hard-fail

    def __init__(self, learner_name: str, mode: str = "standard", scenario_id: str = "scn-wannacry-w1"):
        self.id: str = uuid.uuid4().hex[:12]
        self.learner_name: str = learner_name
        self.scenario_id: str = scenario_id
        self.mode: Mode = Mode(mode)
        self.status: SessionStatus = SessionStatus.IN_PROGRESS
        self.phase: Phase = Phase.INIT
        self.scene_index: int = -1  # -1 = not in a scene yet
        self.scene_sub: SceneSubState | None = None

        # Load scenario to get total hosts
        from .scenarios import get_scenario
        scn = get_scenario(scenario_id)
        total = scn["meta"].get("total_hosts", 250)
        self.HARD_FAIL_THRESHOLD = scn["meta"].get("hard_fail_threshold", 0.80)
        self.total_scenes = len(scn["scenes"])

        self.network: NetworkState = NetworkState(total_hosts=total)
        self.scores: Scores = Scores()
        self.decisions: list[SceneDecision] = []
        self.quiz_answers: list[dict] = []
        self.certificate: dict | None = None
        self.attempt_number: int = 1
        self.confidence: list[int] = []  # per-scene confidence (1-5)
        self.events: list[dict] = []
        self._seq: int = 0
        self.created_at: float = time.time()
        self.completed_at: float | None = None

        self._emit("session_created", {"learner": learner_name, "mode": mode})

    # ---- event logging ----
    def _emit(self, event_type: str, payload: dict | None = None) -> dict:
        self._seq += 1
        ev = {
            "seq": self._seq,
            "type": event_type,
            "payload": payload or {},
            "ts": time.time(),
        }
        self.events.append(ev)
        return ev

    # ---- state transitions ----
    def start_briefing(self) -> dict:
        """INIT → BRIEFING."""
        if self.phase != Phase.INIT:
            raise ValueError(f"Cannot start briefing from {self.phase}")
        self.phase = Phase.BRIEFING
        return self._emit("phase_changed", {"phase": "briefing"})

    def start_scene(self, scene_index: int) -> dict:
        """BRIEFING/SCENE → SCENE[n].ENTER."""
        if self.phase == Phase.BRIEFING and scene_index == 0:
            pass  # first scene after briefing
        elif self.phase == Phase.SCENE and scene_index == self.scene_index + 1:
            pass  # advancing to next scene
        else:
            raise ValueError(f"Cannot start scene {scene_index} from phase={self.phase}, current_scene={self.scene_index}")

        self.phase = Phase.SCENE
        self.scene_index = scene_index
        self.scene_sub = SceneSubState.ENTER
        return self._emit("scene_entered", {"scene_index": scene_index})

    def advance_sub(self, to: str) -> dict:
        """Advance scene sub-state: ENTER→OBSERVE→IDENTIFY→RESPOND→RESOLVE."""
        if self.phase != Phase.SCENE:
            raise ValueError(f"Not in a scene (phase={self.phase})")

        valid_transitions = {
            SceneSubState.ENTER: SceneSubState.OBSERVE,
            SceneSubState.OBSERVE: SceneSubState.IDENTIFY,
            SceneSubState.IDENTIFY: SceneSubState.RESPOND,
            SceneSubState.RESPOND: SceneSubState.RESOLVE,
        }
        target = SceneSubState(to)
        expected = valid_transitions.get(self.scene_sub)
        if expected != target:
            raise ValueError(f"Invalid sub-state transition: {self.scene_sub} → {to} (expected {expected})")

        self.scene_sub = target
        return self._emit("sub_state_changed", {"scene_index": self.scene_index, "sub_state": to})

    def submit_decision(self, scene_def: dict, identify_choice: str,
                        actions: list[str], latency_ms: int = 0,
                        hints_used: int = 0) -> dict:
        """Score a student's decision for the current scene. Transitions RESPOND → RESOLVE."""
        if self.phase != Phase.SCENE or self.scene_sub != SceneSubState.RESPOND:
            raise ValueError(f"Cannot submit decision in phase={self.phase}, sub={self.scene_sub}")

        from .scoring import score_decision
        result = score_decision(self, scene_def, identify_choice, actions, latency_ms, hints_used)

        self.scene_sub = SceneSubState.RESOLVE
        self.decisions.append(result["decision"])

        # Apply network effects
        effects = result["effects"]
        self.network.containment_index = max(0, min(100,
            self.network.containment_index + effects.get("containment_delta", 0)))
        self.network.infected_count = max(0, min(self.network.total_hosts,
            self.network.infected_count + effects.get("infected_delta", 0)))
        if effects.get("encrypted_delta", 0) > 0:
            self.network.encrypted_count += effects["encrypted_delta"]
        if effects.get("backup_destroyed", False):
            self.network.backup_destroyed = True
        if effects.get("isolated_delta", 0) > 0:
            self.network.isolated_count += effects["isolated_delta"]

        # Check hard-fail threshold
        hard_fail = self.network.infected_ratio() >= self.HARD_FAIL_THRESHOLD

        self._emit("decision_submitted", {
            "scene_index": self.scene_index,
            "identify_correct": result["decision"].identify_correct,
            "response_quality": result["decision"].response_quality,
            "score_delta": result["decision"].score_delta,
            "network": self.network.snapshot(),
            "hard_fail": hard_fail,
        })

        if hard_fail:
            self.network.containment_index = min(self.network.containment_index, 20)
            self.status = SessionStatus.FAILED
            self._emit("hard_fail", {"infected_ratio": self.network.infected_ratio()})

        return {
            "identify_correct": result["decision"].identify_correct,
            "response_quality": result["decision"].response_quality,
            "score_delta": result["decision"].score_delta,
            "feedback": result["feedback"],
            "network": self.network.snapshot(),
            "hard_fail": hard_fail,
        }

    def finish_scene(self) -> dict:
        """RESOLVE → ready for next scene or debrief."""
        if self.scene_sub != SceneSubState.RESOLVE:
            raise ValueError(f"Scene not resolved yet (sub={self.scene_sub})")

        if self.status == SessionStatus.FAILED:
            # Hard-fail: jump to debrief
            self.phase = Phase.DEBRIEF
            self.scene_sub = None
            return self._emit("phase_changed", {"phase": "debrief", "reason": "hard_fail"})

        if self.scene_index >= self.total_scenes - 1:
            # Last scene done → debrief
            self.phase = Phase.DEBRIEF
            self.scene_sub = None
            return self._emit("phase_changed", {"phase": "debrief"})

        # Ready for next scene
        self.scene_sub = None
        return self._emit("scene_resolved", {"scene_index": self.scene_index, "ready_for": self.scene_index + 1})

    def start_assessment(self) -> dict:
        """DEBRIEF → ASSESSMENT."""
        if self.phase != Phase.DEBRIEF:
            raise ValueError(f"Cannot start assessment from {self.phase}")
        self.phase = Phase.ASSESSMENT
        return self._emit("phase_changed", {"phase": "assessment"})

    def submit_quiz(self, quiz_bank: list[dict], answers: list[dict]) -> dict:
        """Score the quiz and transition ASSESSMENT → RESULTS."""
        if self.phase != Phase.ASSESSMENT:
            raise ValueError(f"Cannot submit quiz from {self.phase}")

        from .scoring import score_quiz
        quiz_result = score_quiz(self, quiz_bank, answers)
        self.quiz_answers = quiz_result["answers"]
        self.phase = Phase.RESULTS

        # Finalize scores
        self.scores.containment = self.network.containment_index
        if self.network.backup_destroyed:
            self.scores.containment = min(self.scores.containment, 60)

        self.status = SessionStatus.COMPLETED
        self.completed_at = time.time()

        grade_label, passed = self.scores.grade(self.mode)

        # Issue certificate if passed
        if passed:
            from .certificate import generate_certificate
            from .scenarios import get_scenario
            title = get_scenario(self.scenario_id)["meta"]["title"]
            self.certificate = generate_certificate(
                self.id, self.learner_name, title,
                self.scores.composite(self.mode), grade_label,
            )

        self._emit("session_completed", {
            "composite": round(self.scores.composite(self.mode), 1),
            "grade": grade_label,
            "passed": passed,
            "dimensions": self.scores.dimensions(self.mode),
        })

        return {
            "composite": round(self.scores.composite(self.mode), 1),
            "grade": grade_label,
            "passed": passed,
            "dimensions": self.scores.dimensions(self.mode),
            "quiz_correct": sum(1 for a in self.quiz_answers if a.get("correct")),
            "quiz_total": len(self.quiz_answers),
            "outcome": self._outcome_label(),
            "network": self.network.snapshot(),
            "certificate": self.certificate,
        }

    def _outcome_label(self) -> str:
        ci = self.network.containment_index
        bu = not self.network.backup_destroyed
        if ci >= 85 and bu:
            return "Contained"
        if 60 <= ci < 85 and bu:
            return "Recovered"
        if 40 <= ci < 60 or not bu:
            return "Costly recovery"
        return "Catastrophic"

    # ---- state snapshot ----
    def snapshot(self) -> dict:
        grade_label, passed = self.scores.grade(self.mode)
        return {
            "session_id": self.id,
            "learner_name": self.learner_name,
            "scenario_id": self.scenario_id,
            "mode": self.mode.value,
            "status": self.status.value,
            "phase": self.phase.value,
            "scene_index": self.scene_index,
            "scene_sub": self.scene_sub.value if self.scene_sub else None,
            "network": self.network.snapshot(),
            "scores": self.scores.dimensions(self.mode),
            "decisions_count": len(self.decisions),
            "outcome": self._outcome_label() if self.status == SessionStatus.COMPLETED else None,
            "grade": grade_label if self.status == SessionStatus.COMPLETED else None,
            "passed": passed if self.status == SessionStatus.COMPLETED else None,
        }
