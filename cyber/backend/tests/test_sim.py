"""Tests for the dynamic cyber-range sim (live/sim/{topology,tools,engine})."""
from __future__ import annotations

from app.engine.scenario import Objectives, Scenario
from app.live import missions as mp
from app.live.manager import manager
from app.live.sim import topology as T
from app.live.sim import tools as TL
from app.live.sim.engine import ScenarioSim
from app.lab import live_fire as lf

SID = "scn-wannacry-w1"


class _NoAuto:
    """Stub session: every seat is human (no auto), so tick() only propagates."""
    id = "test"
    pending_fire: list = []

    def is_auto(self, role):  # noqa: D401
        return False


def _drive_to_propagate(s: ScenarioSim) -> None:
    s.run_tool("red", "nmap")
    s.run_tool("red", "netexec")
    h = next(x for x in s.topo.hosts.values() if x.vulnerable and x.state == "vulnerable")
    s.run_tool("red", "eternalblue", {"host": h.id})
    s.run_tool("red", "payload", {"host": h.id})
    s.run_tool("red", "dns_killswitch")
    s.run_tool("red", "propagate")


# --------------------------------------------------------------------------- #
#  Topology + catalog
# --------------------------------------------------------------------------- #
def test_w1_topology_shape():
    topo = T.build_w1()
    assert len(topo.hosts) == 23
    assert topo.total_hosts() == 250 and topo.extra_hosts == 227
    pz = topo.hosts["fin-014"]
    assert pz.patient_zero and pz.state == "infected" and pz.revealed
    assert set(topo.vlans) == {"fin", "hr", "srv"}


def test_w1_real_tools_have_firespecs():
    real = [t for t in TL.catalog(SID) if t.kind == "real"]
    assert real and all(lf.has_spec(t.fire_action) for t in real)


def test_unlock_gating():
    s = ScenarioSim(SID); s.session = _NoAuto()
    ok, reason = s.run_tool("red", "eternalblue", {"host": "fin-001"})
    assert not ok and "requires" in reason            # netexec not done yet
    s.run_tool("red", "nmap"); s.run_tool("red", "netexec")
    h = next(x for x in s.topo.hosts.values() if x.vulnerable and x.state == "vulnerable")
    ok, _ = s.run_tool("red", "eternalblue", {"host": h.id})
    assert ok and s.topo.hosts[h.id].state == "exploited"


# --------------------------------------------------------------------------- #
#  Dynamic outcomes (the whole point)
# --------------------------------------------------------------------------- #
def test_no_defense_is_catastrophic():
    s = ScenarioSim(SID); s.session = _NoAuto()
    _drive_to_propagate(s)
    for _ in range(20):
        s.tick()
    assert s.infected_total() > 100
    assert s.outcome_band() == "Catastrophic"
    s.run_tool("red", "shadow_delete"); s.run_tool("red", "ransomware")
    s.tick()
    # human-paced run: detonation opens the aftermath (contain/eradicate/recover) instead of ending
    assert s.impact_complete and not s.finished
    s.conclude()
    assert s.finished and s.outcome == "Catastrophic" and s.impacted_total() > 100


def test_sinkhole_contains():
    s = ScenarioSim(SID); s.session = _NoAuto()
    _drive_to_propagate(s)
    for _ in range(2):
        s.tick()
    ok, _ = s.run_tool("blue", "sinkhole")
    assert ok and s.kill_switch == "tripped" and not s.propagating
    assert s.infected_total() == 0           # everything went dormant
    assert s.outcome_band() == "Contained"


def test_segment_and_patch_collapse_r():
    s = ScenarioSim(SID); s.session = _NoAuto()
    _drive_to_propagate(s)
    s.run_tool("blue", "segment", {"edge": "fin|srv"})
    assert s.segmented and s.r_value < 2.4
    s.run_tool("blue", "wsus")
    assert s.smbv1_patched and s.r_value == 0.0


def test_auto_off_by_default_does_not_finish():
    s = ScenarioSim(SID)                      # auto OFF by default → learner-paced, nothing on a timer
    for _ in range(40):
        s.tick()
    assert not s.finished and not s.pending_intents


def test_auto_vs_auto_resolves_dynamically():
    # Auto defense is now non-deterministic (randomized detect/processing latency), so the outcome
    # varies run to run — but every auto match must still RESOLVE to a valid band, never hang.
    for _ in range(8):
        s = ScenarioSim(SID)
        s.set_auto_enabled(True)
        guard = 0
        while not s.finished and guard < 400:
            s.tick(); guard += 1
        assert s.finished, "auto-vs-auto failed to resolve"
        assert s.outcome in ("Contained", "Degraded", "Catastrophic")


def test_auto_soc_respects_detection_latency():
    # The whole point: the auto-SOC has a mean-time-to-detect — it cannot triage an alert the instant
    # it fires. A low-fidelity signal sits in the queue, unnoticed, while Red keeps working.
    s = ScenarioSim(SID)
    s.set_auto_enabled(True)
    s._alert("test low-fidelity signal", None, "low")
    a = s.alerts[-1]
    assert a["detect_at"] > a["raised_tick"]                 # MTTD exists (latency >= 1 tick)
    while s.tick_n < a["detect_at"] and not s.finished:
        s.tick()
        assert a["status"] == "new", "auto-SOC triaged a signal before its detection time"


def test_auto_action_delays_are_variable():
    # processing/locating time is randomized, not a fixed cadence → telegraphed ETAs should vary
    etas = set()
    for _ in range(12):
        s = ScenarioSim(SID)
        s.set_auto_enabled(True)
        for _ in range(30):
            s.tick()
            etas.update(i.get("eta_ticks", 0) for i in s.pending_intents.values())
            if s.finished:
                break
    assert len(etas - {0}) >= 3, f"auto action ETAs not varied enough: {sorted(etas)}"


def test_telegraph_populates_intents_when_enabled():
    s = ScenarioSim(SID)
    s.set_auto_enabled(True)
    s.tick()
    assert s.pending_intents                  # at least one seat announced intent
    assert all("label" in v for v in s.pending_intents.values())


# --------------------------------------------------------------------------- #
#  AAR persistence through a real session
# --------------------------------------------------------------------------- #
def test_finish_persists_aar():
    from app.db.base import init_db, SessionLocal
    from app.db.models import Run as RunRow, Report as ReportRow
    init_db()
    env = mp.environment_for("ransomware_sim")
    scenario = Scenario(id=SID, name="Operation Tripwire", type="red", label="Guided",
                        description="t", recommended_topology=env, phases=[],
                        objectives=Objectives(red=[], blue=[]))
    session, _ = manager.create(scenario, env, "tester")
    session.sim = ScenarioSim(SID)
    session.sim.session = session
    session.sim.conclude()
    assert session.report is not None and session.report["scenario"]["id"] == SID
    db = SessionLocal()
    try:
        assert db.get(RunRow, session.id) is not None
        assert db.query(ReportRow).filter(ReportRow.run_id == session.id).first() is not None
    finally:
        db.close()
    # snapshot carries the sim block
    snap = session.snapshot()
    assert snap["sim"]["finished"] and snap["sim"]["topology"]["total_hosts"] == 250
