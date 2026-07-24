"""Engine tests: determinism, full-scenario coverage, emergence, and asset-selection impact."""
from __future__ import annotations

import copy

from app.engine.config import RunConfig, WorkflowConfig
from app.engine.enums import Difficulty, EventType
from app.engine.environment import EnvironmentSpec
from app.engine.run import run
from app.engine.scenario import Scenario
from app.scenarios.loader import get_seed_scenario

SCENARIO_ID = "operation_black_phoenix"


def _scenario() -> Scenario:
    s = get_seed_scenario(SCENARIO_ID)
    assert s is not None
    return s


def _env_with(enabled: dict[str, bool] | None = None, default: bool = True) -> EnvironmentSpec:
    """Clone the scenario's recommended topology, toggling controls by *type*."""
    enabled = enabled or {}
    env = copy.deepcopy(_scenario().recommended_topology)
    for c in env.controls:
        c.enabled = enabled.get(c.type, default)
    return env


def test_scenario_json_roundtrip():
    s = _scenario()
    restored = Scenario.model_validate_json(s.model_dump_json())
    assert restored.id == s.id
    assert len(restored.playbook) == 16
    assert len(restored.phases) == 8


def test_determinism_identical_inputs_identical_timeline():
    s = _scenario()
    env = _env_with(default=True)
    cfg = RunConfig(difficulty=Difficulty.HARD, readiness=55, duration_min=120)
    r1 = run(s, env, cfg)
    r2 = run(s, copy.deepcopy(env), cfg.model_copy())
    assert r1.model_dump(mode="json") == r2.model_dump(mode="json")
    assert len(r1.events) > 30


def test_all_phases_are_entered():
    s = _scenario()
    # weak posture so every step at least processes
    env = _env_with(default=False)
    r = run(s, env, RunConfig(difficulty=Difficulty.EXPERT, readiness=20))
    phases_seen = {e.phase for e in r.events if e.type == EventType.PHASE}
    assert phases_seen == set(s.phases)


def test_emergence_strong_vs_weak_posture():
    s = _scenario()
    # Strong = controls on + default (competent) team workflows + easy adversary.
    strong = run(s, _env_with(default=True),
                 RunConfig(difficulty=Difficulty.EASY, readiness=95))
    # Weak = controls off + defender workflows stripped + expert adversary.
    weak = run(s, _env_with(default=False),
               RunConfig(difficulty=Difficulty.EXPERT, readiness=15,
                         workflow_config=WorkflowConfig(enabled={"blue": [], "soc": [], "ot": [], "mgmt": []})))

    # Strong posture blocks the kill chain early; weak posture lets it run to impact.
    assert strong.summary["ransomware"] is False
    assert strong.summary["ot_impact"] is False
    assert weak.summary["ransomware"] is True
    assert weak.summary["ot_impact"] is True

    assert weak.summary["assets_compromised"] > strong.summary["assets_compromised"]
    assert weak.scores["red"] > strong.scores["red"]
    assert strong.summary["blocked"] >= 1
    # No detections fire when all controls are disabled.
    assert weak.summary["detected"] == 0


def test_asset_selection_removing_siem_degrades_detection():
    s = _scenario()
    # EDR off in both so SIEM is the dominant detector; compare SIEM on vs off.
    with_siem = run(s, _env_with({"edr": False, "siem": True}),
                    RunConfig(difficulty=Difficulty.EXPERT, readiness=50))
    without_siem = run(s, _env_with({"edr": False, "siem": False}),
                       RunConfig(difficulty=Difficulty.EXPERT, readiness=50))
    assert with_siem.summary["detected"] > without_siem.summary["detected"]


def test_disabling_edr_midrun_cancels_its_pending_detections():
    """The 'disable security tools' technique should suppress later EDR alerts (emergent)."""
    s = _scenario()
    # EDR on, SIEM off, no email_sec block, so the chain runs and EDR is the detector.
    env = _env_with({"siem": False, "email_sec": False, "edr": True})
    r = run(s, env, RunConfig(difficulty=Difficulty.EXPERT, readiness=30))
    # The disable-tools technique must have succeeded for this to be meaningful.
    assert any(e.technique == "T1562.001" and e.type == EventType.ATTACK for e in r.events)
    # Ransomware (post-disable, EDR-detected) should not produce an EDR detection event.
    edr_detections_after = [
        e for e in r.events
        if e.type == EventType.DETECTION and e.data.get("control") == "edr"
        and e.technique == "T1486"
    ]
    assert edr_detections_after == []
