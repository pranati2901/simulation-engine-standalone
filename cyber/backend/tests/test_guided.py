"""Tests for the guided-walkthrough layer (live/guided.py + live/guided_runtime.py)."""
from __future__ import annotations

import pytest

from app.engine.scenario import Objectives, Scenario
from app.live import guided as G
from app.live import guided_runtime as gr
from app.live import missions as mp
from app.live.manager import manager
from app.lab import live_fire as lf


SID = "scn-wannacry-w1"


def _new_guided(host_role: str = "red"):
    """Spin up a guided W1 session the way the API endpoint does; seat the host on host_role."""
    env = mp.environment_for("ransomware_sim")
    scenario = Scenario(id=SID, name="Operation Tripwire", type="red", label="Guided",
                        description="t", recommended_topology=env, phases=[],
                        objectives=Objectives(red=[], blue=[]))
    session, host = manager.create(scenario, env, "tester")
    session.start()
    gr.attach(session, SID)
    session.claim_role(host.id, host_role)
    session.players[host.id].connected = True   # human seat → not auto
    return session, host


# --------------------------------------------------------------------------- #
#  Scenario data integrity
# --------------------------------------------------------------------------- #
def test_w1_scenario_shape():
    scn = G.get_guided(SID)
    assert scn is not None
    assert len(scn.phases) == 11
    for p in scn.phases:
        # every phase covers all three teams with populated Does/How/Outcome
        for role in ("red", "blue", "soc"):
            assert p.tasks_for(role), f"phase {p.id} missing {role}"
        for t in p.tasks:
            assert t.does and t.how and t.outcome
            if t.kind == "real_tool":
                assert lf.has_spec(t.action_id), f"{t.id} -> no FireSpec for {t.action_id}"


def test_real_tool_tasks_map_to_fire_specs():
    scn = G.get_guided(SID)
    real = [t for p in scn.phases for t in p.tasks if t.kind == "real_tool"]
    assert real and all(lf.has_spec(t.action_id) for t in real)


ALL_SCENARIOS = ["scn-wannacry-w1", "scn-r5-phishing", "scn-c5-edr"]


@pytest.mark.parametrize("sid", ALL_SCENARIOS)
def test_every_scenario_is_well_formed(sid):
    """All three demo scenarios: full Red/Blue/SOC coverage, populated fields, valid real-tool maps."""
    scn = G.get_guided(sid)
    assert scn is not None and scn.phases
    for p in scn.phases:
        for role in ("red", "blue", "soc"):
            assert p.tasks_for(role), f"{sid}/{p.id} missing {role}"
        for t in p.tasks:
            assert t.does and t.how and t.outcome, f"{sid}/{t.id} has an empty field"
            if t.kind == "real_tool":
                assert lf.has_spec(t.action_id), f"{sid}/{t.id} -> no FireSpec for {t.action_id}"


@pytest.mark.parametrize("sid", ALL_SCENARIOS)
def test_every_scenario_drives_to_completion(sid):
    """Auto-defense walks each scenario to a finished, contained outcome (no stalls/exceptions)."""
    env = mp.environment_for("ransomware_sim")
    scenario = Scenario(id=sid, name=G.get_guided(sid).name, type="red", label="Guided",
                        description="t", recommended_topology=env, phases=[],
                        objectives=Objectives(red=[], blue=[]))
    session, _ = manager.create(scenario, env, "tester")
    session.start()
    gr.attach(session, sid)
    guard = 0
    while not session.guided.finished and guard < 400:
        gr.auto_step(session)
        guard += 1
    assert session.guided.finished, f"{sid} stalled"
    assert session.guided.outcome == "Contained"


# --------------------------------------------------------------------------- #
#  Runtime: a full guided run drives to completion
# --------------------------------------------------------------------------- #
def test_guided_run_completes_with_auto_defense():
    session, host = _new_guided("red")
    run = session.guided
    assert run is not None and run.phase_idx == 0
    assert session.live_fire is True            # guided auto-arms real tools

    guard = 0
    while not run.finished and guard < 200:
        phase = run.phase()
        # human Red completes its gating tasks; auto fills SOC/Blue
        for t in phase.tasks_for("red"):
            if not t.optional and t.id not in run.completed:
                ok, reason = gr.complete_task(session, host.id, t.id)
                assert ok, reason
        gr.auto_step(session)
        guard += 1

    assert run.finished, "guided run did not finish"
    assert run.outcome in ("Contained", "Degraded", "Catastrophic")
    # full early defense (auto SOC/Blue act every phase) → should contain the worm
    assert run.outcome == "Contained"
    assert session.status == "completed"
    # real-tool red tasks queued live-fire jobs (no lab in tests, so they just queue)
    assert any(j["action_id"] in lf.FIRE_BY_ACTION for j in session.pending_fire)


def test_guided_snapshot_shape():
    session, _ = _new_guided("soc")
    snap = session.snapshot()
    g = snap["guided"]
    assert g is not None
    assert g["scenario"]["id"] == SID
    assert g["phase"]["name"] == "Network Discovery"
    assert set(g["tasks"]) == {"red", "blue", "soc"}
    assert g["progress"]["total"] == 11
    assert len(g["phases"]) == 11
    assert g["phases"][0]["state"] == "active"


def test_role_gating_rejects_wrong_seat():
    session, host = _new_guided("blue")
    # host is Blue; a red task must be rejected for this seat
    red_task = session.guided.phase().tasks_for("red")[0]
    ok, reason = gr.complete_task(session, host.id, red_task.id)
    assert not ok and "RED" in reason
