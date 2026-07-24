"""v2 tests: role lens purity, multi-actor scoring, task events, phase drills, decision gates."""
from __future__ import annotations

import copy

from app.engine.config import RunConfig, WorkflowConfig
from app.engine.enums import Difficulty, EventType, Side
from app.engine.environment import EnvironmentSpec
from app.engine.run import run
from app.engine.scenario import Scenario
from app.scenarios.loader import get_seed_scenario

SID = "operation_black_phoenix"


def _scn() -> Scenario:
    s = get_seed_scenario(SID)
    assert s is not None
    return s


def _env(default: bool = True) -> EnvironmentSpec:
    env = copy.deepcopy(_scn().recommended_topology)
    for c in env.controls:
        c.enabled = default
    return env


def test_focus_role_is_a_pure_lens():
    """Switching the focus role must not change the underlying timeline or scores."""
    s = _scn()
    env = _env(True)
    red_view = run(s, copy.deepcopy(env), RunConfig(difficulty=Difficulty.HARD, readiness=55, focus_role=Side.RED))
    blue_view = run(s, copy.deepcopy(env), RunConfig(difficulty=Difficulty.HARD, readiness=55, focus_role=Side.BLUE))
    assert [e.model_dump() for e in red_view.events] == [e.model_dump() for e in blue_view.events]
    assert red_view.scores == blue_view.scores
    assert red_view.focus_role == "red" and blue_view.focus_role == "blue"


def test_all_teams_score_and_emit_tasks():
    s = _scn()
    r = run(s, _env(True), RunConfig(difficulty=Difficulty.EXPERT, readiness=55, focus_role=Side.BLUE))
    # every team has a score entry; defenders actually score under a strong posture
    for role in ("red", "blue", "soc", "mgmt", "ot"):
        assert role in r.scores
    assert r.scores["soc"] > 0 and r.scores["blue"] > 0
    # task-status events drive the per-role sub-reports
    task_actors = {e.side.value for e in r.events if e.type == EventType.TASK}
    assert {"red", "soc", "blue"}.issubset(task_actors)
    # role_tasks snapshot has SOC steps marked done
    soc_done = [t for t in r.role_tasks["soc"] if t["status"] == "done"]
    assert len(soc_done) >= 2


def test_escalation_decision_and_notify_events():
    s = _scn()
    r = run(s, _env(True), RunConfig(difficulty=Difficulty.EXPERT, readiness=55))
    types = {e.type for e in r.events}
    assert EventType.ESCALATION in types          # SOC classified a P-level
    assert EventType.NOTIFY in types              # management notified
    assert EventType.DECISION in types            # isolate-DC decision gate fired
    # KPIs include the SOC/Blue clock metrics
    for k in ("mtta_s", "mttc_s", "escalation_accuracy", "hunt_success"):
        assert k in r.kpis


def test_phase_range_drill_runs_a_single_phase():
    s = _scn()
    # Phase 3 = Privilege Escalation drill
    r = run(s, _env(True), RunConfig(difficulty=Difficulty.HARD, readiness=60, phase_range=(3, 3)))
    phases = {e.phase for e in r.events if e.type == EventType.PHASE}
    assert phases == {"Privilege Escalation"}
    # priming gave the attacker a foothold so the drill is meaningful
    assert r.summary["succeeded"] >= 1


def test_per_team_scenarios_seeded():
    for sid in ("operation_black_phoenix_red", "operation_black_phoenix_soc",
                "operation_black_phoenix_blue"):
        assert get_seed_scenario(sid) is not None


# --------------------------------------------------------------------------- #
#  Workflow customization mechanically changes outcomes (the core requirement)
# --------------------------------------------------------------------------- #
def _wc(**teams) -> WorkflowConfig:
    return WorkflowConfig(enabled=teams)


def test_block_egress_task_stops_exfiltration():
    s = _scn()
    base = dict(difficulty=Difficulty.EXPERT, readiness=50)
    # controls off so only the Blue task decides; SOC off so containment doesn't interfere
    on = run(s, _env(False), RunConfig(**base, workflow_config=_wc(soc=[], blue=["blue.block_egress"], ot=[], mgmt=[])))
    off = run(s, _env(False), RunConfig(**base, workflow_config=_wc(soc=[], blue=[], ot=[], mgmt=[])))
    assert on.summary["exfiltrated"] is False     # egress blocked first
    assert off.summary["exfiltrated"] is True      # no egress control -> data leaves


def test_segmentation_task_protects_ot():
    s = _scn()
    base = dict(difficulty=Difficulty.EXPERT, readiness=50)
    seg = run(s, _env(False), RunConfig(**base, workflow_config=_wc(soc=[], blue=["blue.segmentation"], ot=[], mgmt=[])))
    noseg = run(s, _env(False), RunConfig(**base, workflow_config=_wc(soc=[], blue=[], ot=[], mgmt=[])))
    assert seg.summary["ot_impact"] is False       # IT/OT segmentation blocks the pivot
    assert noseg.summary["ot_impact"] is True


def test_red_evasion_slows_detection():
    s = _scn()
    base = dict(difficulty=Difficulty.HARD, readiness=60)
    core = ["red.recon", "red.access", "red.privesc", "red.persist", "red.lateral", "red.exfil", "red.impact"]
    evade = run(s, _env(True), RunConfig(**base))                                  # red defaults incl evasion
    plain = run(s, _env(True), RunConfig(**base, workflow_config=_wc(red=core)))   # evasion stripped
    assert evade.kpis["mttd_s"] > plain.kpis["mttd_s"]   # evasion increases dwell time


def test_eradication_task_prevents_persistence_reestablish():
    s = _scn()
    base = dict(difficulty=Difficulty.EXPERT, readiness=60)
    blue_no_erad = ["blue.identify", "blue.edr_contain", "blue.lessons"]
    blue_erad = blue_no_erad + ["blue.eradicate", "blue.krbtgt"]
    no_erad = run(s, _env(True), RunConfig(**base, workflow_config=_wc(blue=blue_no_erad)))
    erad = run(s, _env(True), RunConfig(**base, workflow_config=_wc(blue=blue_erad)))
    reestablished = lambda r: any("re-established" in e.message for e in r.events)  # noqa: E731
    assert reestablished(no_erad) is True       # persistence survives containment
    assert reestablished(erad) is False         # eradication defeats it


def test_fallback_technique_activates_when_blocked():
    """When a step's primary technique is blocked and it has a fallback, the engine tries the fallback."""
    s = _scn()
    s_copy = s.model_copy(deep=True)
    for step in s_copy.playbook:
        if step.technique == "exfiltration":
            # Exfiltration is blocked by DLP at Easy/Medium; use recon_osint as fallback
            # (it has no preconditions beyond "start" which is always true)
            step.fallback_technique = "recon_osint"
            break
    env = _env(True)
    r = run(s_copy, env, RunConfig(difficulty=Difficulty.EASY, readiness=80))
    block_events = [e for e in r.events if e.type == EventType.BLOCK and e.technique == "T1567.002"]
    fallback_events = [e for e in r.events if e.type == EventType.ATTACK and e.data.get("fallback_of") == "exfiltration"]
    assert len(block_events) >= 1, "Exfiltration should be blocked at Easy difficulty with DLP"
    assert len(fallback_events) >= 1, "Fallback technique should have been attempted after block"


def test_decision_gates_fire_and_score():
    """All configured decision gates should produce DECISION events and affect scoring."""
    s = _scn()
    # Full controls + strong Blue posture so containment fires + gates evaluated
    blue_full = ["blue.identify", "blue.memory_first", "blue.block_egress", "blue.edr_contain",
                 "blue.disable_accounts", "blue.segmentation", "blue.dc_gate", "blue.eradicate",
                 "blue.krbtgt", "blue.backups", "blue.lessons"]
    r = run(s, _env(True), RunConfig(difficulty=Difficulty.EXPERT, readiness=60,
                                      workflow_config=_wc(blue=blue_full)))
    decision_events = [e for e in r.events if e.type == EventType.DECISION]
    gate_ids = {e.data.get("gate") for e in decision_events}
    # At minimum the DC gate should fire (DC is always in the topology and gets compromised at Expert)
    assert "gate_dc_no_isolate" in gate_ids, f"DC gate should fire; got gates: {gate_ids}"
    # All decision events should have gate data
    for e in decision_events:
        assert "gate" in e.data, f"Decision event missing gate data: {e.title}"
    # Blue score should be positive (gates give score_correct bonuses)
    assert r.scores["blue"] > 0


def test_regulatory_frameworks_produce_framework_specific_notifications():
    """Scenario with regulatory frameworks + controls on should produce framework-specific notifications."""
    s = _scn()
    s_copy = s.model_copy(deep=True)
    s_copy.regulatory_frameworks = ["ndb", "apra_cps234", "critical_infra"]
    # Controls ON so SOC detects -> escalates -> P0 -> mgmt -> regulatory
    # Expert difficulty so the attack succeeds (ransomware deploys) to trigger frameworks
    r = run(s_copy, _env(True), RunConfig(difficulty=Difficulty.EXPERT, readiness=60))
    notify_events = [e for e in r.events if e.type == EventType.NOTIFY]
    framework_ids = {e.data.get("framework_id") for e in notify_events if e.data.get("framework_id")}
    # At least one framework should be triggered (critical_infra fires on ransomware)
    assert len(framework_ids) >= 1, \
        f"Expected framework-specific notifications; got: {framework_ids}"
    # Each framework notification should have deadline data
    for e in notify_events:
        if e.data.get("framework_id"):
            assert "deadline_hours" in e.data
            assert "penalty" in e.data


def test_persistence_planted_tracked_in_summary():
    """Successful persistence techniques should be tracked with type and asset info."""
    s = _scn()
    # Expert + controls off + no eradication tasks = persistence survives
    blue_no_erad = ["blue.identify", "blue.edr_contain", "blue.lessons"]
    r = run(s, _env(False), RunConfig(difficulty=Difficulty.EXPERT, readiness=50,
                                       workflow_config=_wc(blue=blue_no_erad)))
    planted = r.summary.get("persistence_planted", [])
    assert len(planted) >= 1, f"Expected persistence to be planted; got: {planted}"
    for p in planted:
        assert "type" in p
        assert "technique" in p
        assert "t" in p
    # Without eradication tasks, persistence should survive
    assert r.summary.get("persistence_eradicated") is False


def test_persistence_eradicated_when_blue_tasks_on():
    """With eradication workflow tasks enabled, persistence should be marked eradicated."""
    s = _scn()
    blue_erad = ["blue.identify", "blue.edr_contain", "blue.eradicate", "blue.krbtgt", "blue.lessons"]
    r = run(s, _env(True), RunConfig(difficulty=Difficulty.EXPERT, readiness=60,
                                      workflow_config=_wc(blue=blue_erad)))
    if r.summary.get("contained", 0) > 0:
        assert r.summary.get("persistence_eradicated") is True


def test_workflow_config_filters_tasks_and_is_deterministic():
    s = _scn()
    env = _env(True)
    cfg = RunConfig(difficulty=Difficulty.HARD, readiness=55,
                    workflow_config=_wc(blue=["blue.identify", "blue.edr_contain", "blue.lessons"]))
    r1 = run(s, copy.deepcopy(env), cfg)
    r2 = run(s, copy.deepcopy(env), cfg.model_copy(deep=True))
    assert [e.model_dump() for e in r1.events] == [e.model_dump() for e in r2.events]
    blue_wf = next(w for w in r1.workflows if w["actor"] == "blue")
    assert {st["id"] for st in blue_wf["steps"]} == {"blue.identify", "blue.edr_contain", "blue.lessons"}
    assert {t["id"] for t in r1.role_tasks["blue"]} == {"blue.identify", "blue.edr_contain", "blue.lessons"}


# --------------------------------------------------------------------------- #
#  Builder-created scenarios (role-less assets) must run the whole kill chain
#  and engage EVERY team — regression for the "only Blue scores" bug where
#  role-targeted steps (primary_endpoint / sensitive_share) failed with no_target.
# --------------------------------------------------------------------------- #
def _builder_scenario() -> Scenario:
    """A scenario shaped exactly like the frontend Builder saves it: assets carry only a `type`
    (NO role), and the playbook targets roles like primary_endpoint / sensitive_share."""
    types = ["endpoint", "domain_controller", "email_server", "file_share", "erp",
             "mes", "ot_plc", "cloud", "siem_platform", "edr_platform", "firewall"]
    steps = [
        ("recon_osint", "Reconnaissance", 1, "type", ""),
        ("phishing", "Initial Compromise", 4, "role", "primary_endpoint"),
        ("c2_beacon", "Initial Compromise", 6, "role", "primary_endpoint"),
        ("credential_dump", "Privilege Escalation", 9, "role", "primary_endpoint"),
        ("dcsync_domain_admin", "Privilege Escalation", 14, "type", "domain_controller"),
        ("lateral_movement", "Lateral Movement", 17, "role", "sensitive_share"),
        ("collection_staging", "Data Exfiltration", 24, "role", "sensitive_share"),
        ("exfiltration", "Data Exfiltration", 30, "role", "sensitive_share"),
        ("ransomware", "Ransomware", 40, "type", "erp"),
        ("ot_pivot", "OT Attack", 48, "type", "mes"),
        ("ot_plc_modify", "OT Attack", 54, "type", "ot_plc"),
    ]
    return Scenario.model_validate({
        "schema_version": 1, "id": "builder_regression", "name": "Builder Regression",
        "type": "purple", "industry": "generic", "nominal_duration_min": 90,
        "phases": ["Reconnaissance", "Initial Compromise", "Privilege Escalation",
                   "Lateral Movement", "Data Exfiltration", "Ransomware", "OT Attack"],
        "recommended_topology": {
            "assets": [{"id": f"{t}-1", "type": t, "name": t} for t in types],  # NO role
            "controls": [{"id": f"c-{c}", "type": c, "enabled": True} for c in ("edr", "siem", "firewall_ids")],
        },
        "playbook": [{"id": f"s{i}", "technique": tc, "phase": ph, "at_min": at,
                      "target": {"by": by, "value": v} if v else None}
                     for i, (tc, ph, at, by, v) in enumerate(steps)],
        "objectives": {"red": ["Gain foothold", "Domain admin", "Exfiltrate", "Ransomware", "OT impact"],
                       "blue": ["Detect", "Contain", "Recover"]},
    })


def test_builder_scenario_runs_full_chain_all_teams_engage():
    """Weak defence: Red should progress the whole chain and Mgmt + OT must engage (not stay at 0)."""
    s = _builder_scenario()
    r = run(s, s.recommended_topology,
            RunConfig(difficulty=Difficulty.EXPERT, readiness=10,
                      workflow_config=_wc(blue=[], soc=[])))
    # Red actually lands attacks (previously every role-targeted step failed with no_target)
    assert r.summary["succeeded"] >= 6
    assert r.summary["ransomware"] and r.summary["exfiltrated"] and r.summary["ot_impact"]
    # Management is pulled in by the material impact even with SOC disabled; OT switches to manual ops
    assert r.scores["mgmt"] > 0
    assert r.scores["ot"] > 0
    # Red objectives read from the peak (foothold survives being reported even if later contained)
    assert all(o.met for o in r.objectives["red"])


def test_builder_scenario_early_containment_beats_red():
    """Strong defence: Blue contains early, stops the chain, and outscores Red."""
    s = _builder_scenario()
    r = run(s, s.recommended_topology, RunConfig(difficulty=Difficulty.MEDIUM, readiness=75))
    assert r.scores["blue"] > 0 and r.scores["soc"] > 0
    assert r.summary["contained"] >= 1
    assert r.scores["blue"] >= r.scores["red"]      # early containment wins
    assert not r.summary["ransomware"]              # Red never detonated
