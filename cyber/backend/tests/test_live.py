"""Live multiplayer (human-driven Red) tests — REST lobby + WebSocket play."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _create(client) -> dict:
    r = client.post("/api/live/sessions",
                    json={"scenario_id": "operation_black_phoenix", "host_name": "Alice"})
    assert r.status_code == 201
    return r.json()


def test_create_join_and_list(client):
    created = _create(client)
    sid = created["session_id"]
    assert created["status"] == "lobby" and created["player_id"]

    # appears in the open list
    open_sessions = client.get("/api/live/sessions").json()
    assert any(s["id"] == sid for s in open_sessions)

    # a second player joins
    joined = client.post(f"/api/live/sessions/{sid}/join", json={"name": "Bob"}).json()
    assert joined["player_id"] != created["player_id"]

    detail = client.get(f"/api/live/sessions/{sid}").json()
    assert detail["player_count"] == 2


def test_red_lifecycle_over_ws(client):
    created = _create(client)
    sid, host = created["session_id"], created["player_id"]

    with client.websocket_connect(f"/ws/live/{sid}?player_id={host}") as ws:
        assert ws.receive_json()["type"] == "welcome"
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["session"]["status"] == "lobby"

        # claim red + start as ransomware (fast profile, smaller budget)
        ws.send_json({"action": "claim_role", "role": "red"})
        ws.receive_json()
        ws.send_json({"action": "start", "profile": "ransomware"})
        snap = ws.receive_json()
        assert snap["session"]["status"] == "active"
        op = snap["operator"]
        assert op["budget"] == 95
        # only planning is available at the very start
        avail = {a["id"] for a in op["actions"] if a["available"]}
        assert avail == {"plan.review"}

        def do(action_id, target=None):
            ws.send_json({"action": "red_action", "action_id": action_id, "target_id": target})
            return ws.receive_json()

        def target_for(s, action_id):
            for a in s["operator"]["actions"]:
                if a["id"] == action_id and a["targets"]:
                    return a["targets"][0]["id"]
            return None

        s = do("plan.review")
        s = do("recon.osint")
        s = do("infra.c2")
        s = do("infra.lure")
        s = do("access.phish")
        assert s["operator"]["footholds"]                      # foothold established
        s = do("cred.lsass")
        assert s["operator"]["cred_scope"] == "privileged"
        s = do("intrecon.identity_graph")                      # reveal the internal terrain (fog of war)
        # drive the canonical OT primary objective: pivot IT->OT, then modify the PLC
        s = do("lateral.pivot_ot", target_for(s, "lateral.pivot_ot"))
        assert s["operator"]["world_flags"].count("in_ot") == 1
        s = do("impact.ot_modify", target_for(s, "impact.ot_modify"))
        op = s["operator"]
        assert any(o["key"] == "ot_impact" and o["primary"] and o["met"] for o in op["objectives"])

        # reaching the primary objective auto-ends the match as a Red win (race semantics)
        assert s["session"]["status"] == "completed"
        assert s["session"]["match_result"] == "red"
        final = op["final"]
        assert final["objective_met"] is True
        assert final["total_score"] > 0


def test_red_vs_blue_eviction_win(client):
    """Red + Blue on one shared world: Blue detects, eradicates persistence, then evicts Red.

    Driven through the in-process session (REST registers it) to avoid WS broadcast-ordering noise.
    """
    from app.live.manager import manager

    created = _create(client)
    sid, host = created["session_id"], created["player_id"]
    blue = client.post(f"/api/live/sessions/{sid}/join", json={"name": "Blue"}).json()["player_id"]

    sess = manager.get(sid)
    assert sess.claim_role(host, "red") and sess.claim_role(blue, "blue")
    sess.start("ransomware")

    def btarget(aid):
        for a in sess._defender_public()["actions"]:
            if a["id"] == aid and a["targets"]:
                return a["targets"][0]["id"]
        return None

    # Blue turns on visibility; Red breaks in and plants persistence
    for a in ("see.edr", "see.identity"):
        assert sess.execute_blue_action(blue, a, None)[0]
    for a in ("plan.review", "recon.osint", "infra.c2", "infra.lure", "access.phish"):
        assert sess.execute_red_action(host, a, None)[0]
    assert sess.detected_actions >= 1                    # phishing was detectable
    assert sess.execute_red_action(host, "persist.task", None)[0]

    # Blue scopes, eradicates persistence, then contains -> full eviction
    assert sess.execute_blue_action(blue, "investigate.scope", None)[0]
    assert sess.execute_blue_action(blue, "hunt.persistence", None)[0]
    assert sess.execute_blue_action(blue, "eradicate.persistence", None)[0]
    sess.execute_blue_action(blue, "contain.isolate", btarget("contain.isolate"))

    assert sess.status == "completed"
    assert sess.match_result == "blue"
    assert sess.defender.final["eviction_complete"] is True


def test_blue_egress_block_stops_exfil(client):
    """Blue blocking egress prevents Red's staged exfiltration (containment mutates Red's world)."""
    from app.live.manager import manager

    created = _create(client)
    sid, host = created["session_id"], created["player_id"]
    blue = client.post(f"/api/live/sessions/{sid}/join", json={"name": "Blue"}).json()["player_id"]
    sess = manager.get(sid)
    sess.claim_role(host, "red"); sess.claim_role(blue, "blue")
    sess.start("nation_state")

    for a in ("plan.review", "recon.osint", "infra.c2", "infra.lure", "access.phish",
              "cred.lsass", "intrecon.identity_graph"):
        sess.execute_red_action(host, a, None)
    # stage data on a file share
    stage_t = next((t["id"] for x in sess._operator_public()["actions"]
                    if x["id"] == "collect.stage" for t in x["targets"]), None)
    assert stage_t and sess.execute_red_action(host, "collect.stage", stage_t)[0]
    # Blue blocks egress -> staged exfil is cut off
    sess.execute_blue_action(blue, "contain.block_egress", None)
    assert "exfil" in sess.defender.prevented
    # exfil.cloud is now unavailable to Red
    assert not next(a["available"] for a in sess._operator_public()["actions"] if a["id"] == "exfil.cloud")


def test_soc_triage_escalate_pipeline(client):
    """Red telemetry -> alert queue -> SOC triages + escalates -> incident declared on the asset."""
    from app.live.manager import manager

    created = _create(client)
    sid, host = created["session_id"], created["player_id"]
    soc = client.post(f"/api/live/sessions/{sid}/join", json={"name": "SOC"}).json()["player_id"]
    sess = manager.get(sid)
    sess.claim_role(host, "red"); sess.claim_role(soc, "soc")
    # keep blue/soc auto off so the human SOC owns the queue deterministically
    sess.set_auto("blue", False); sess.set_auto("soc", False)
    sess.start("nation_state")

    # SOC stands up detection; Red breaks in
    for a in ("soc.edr_monitoring", "soc.identity_monitoring"):
        assert sess.execute_soc_action(soc, a, None)[0]
    for a in ("plan.review", "recon.osint", "infra.c2", "infra.lure", "access.phish"):
        sess.execute_red_action(host, a, None)

    new_alerts = [a for a in sess.alerts if a["status"] == "new"]
    assert new_alerts, "Red's phishing should have raised an alert"
    alert_id = new_alerts[0]["id"]

    assert sess.execute_soc_action(soc, "soc.triage", alert_id)[0]
    assert next(a for a in sess.alerts if a["id"] == alert_id)["status"] == "triaged"
    assert sess.execute_soc_action(soc, "soc.escalate", alert_id)[0]
    escalated = next(a for a in sess.alerts if a["id"] == alert_id)
    assert escalated["status"] == "escalated"
    assert escalated["asset_id"] in sess.incident_declared
    assert sess.soc.triaged >= 1 and sess.soc.escalated >= 1


def test_auto_drivers_run_unoccupied_seats(client):
    """With no operators claimed, all three seats auto-operate and the match resolves."""
    from app.live.manager import manager
    from app.live import auto

    created = _create(client)
    sid, host = created["session_id"], created["player_id"]
    sess = manager.get(sid)
    sess.claim_role(host, "observer")                    # nobody on red/blue/soc -> all auto
    assert sess.is_auto("red") and sess.is_auto("blue") and sess.is_auto("soc")
    sess.start("ransomware")

    for _ in range(80):
        auto.tick(sess)
        if sess.status == "completed":
            break
    assert sess.status == "completed"
    assert sess.match_result in ("red", "blue")
    # SOC auto-built coverage and worked the queue
    assert sess.soc.final["coverage_pct"] >= 0
    assert sess.operator.final is not None and sess.defender.final is not None and sess.soc.final is not None


def test_missions_are_standalone_not_black_phoenix(client):
    """A dedicated mission launches with its OWN environment — independent of Black Phoenix."""
    from app.live.manager import manager

    missions = client.get("/api/live/missions").json()
    assert len(missions) == 12

    # launch the Cloud Security Assessment directly (no scenario_id)
    r = client.post("/api/live/sessions",
                    json={"mission_id": "cloud_assessment", "host_name": "H"})
    assert r.status_code == 201
    sid = r.json()["session_id"]
    sess = manager.get(sid)
    assert sess.mission == "cloud_assessment" and sess.mission_locked is True
    assert sess.scenario.id == "mission::cloud_assessment"     # synthetic, not Black Phoenix
    assert "black" not in sess.scenario_name.lower()
    # its env is tailored (cloud present, OT absent for this mission)
    types = {a.type for a in sess.env.assets}
    assert "cloud" in types and "ot_plc" not in types

    # a dedicated mission's goal can't be swapped in the lobby
    sess.set_mission("ransomware_sim")
    assert sess.mission == "cloud_assessment"


def test_black_phoenix_still_launchable_as_live_scenario(client):
    """Black Phoenix remains a separate, pre-built live scenario (mission chosen in lobby)."""
    from app.live.manager import manager

    r = client.post("/api/live/sessions",
                    json={"scenario_id": "operation_black_phoenix", "host_name": "H"})
    assert r.status_code == 201
    sess = manager.get(r.json()["session_id"])
    assert sess.mission_locked is False                        # mission selectable in lobby
    assert "black phoenix" in sess.scenario_name.lower()
    sess.set_mission("identity_assessment")                    # host can pick a mission
    assert sess.mission == "identity_assessment"


def test_create_requires_mission_or_scenario(client):
    assert client.post("/api/live/sessions", json={"host_name": "H"}).status_code == 422


def test_mission_drives_goal_and_scoring(client):
    """The chosen mission re-points the objective, forces character, and reweights stealth."""
    from app.live.manager import manager

    # Identity Security Assessment -> primary objective becomes Domain Admin
    r = _create(client); sid = r["session_id"]
    sess = manager.get(sid)
    sess.claim_role(r["player_id"], "observer")
    sess.start("nation_state", "identity_assessment")
    primary = next(o for o in sess.operator.objectives if o["primary"])
    assert primary["key"] == "domain_admin"

    # Insider sim forces the insider (assumed-breach) profile and an exfil goal
    r2 = _create(client); s2 = manager.get(r2["session_id"])
    s2.claim_role(r2["player_id"], "observer")
    s2.start("nation_state", "insider_sim")
    assert s2.operator.profile == "insider"                 # mission forced the character
    assert s2.world.attacker.has_foothold()                 # assumed-breach start
    assert next(o for o in s2.operator.objectives if o["primary"])["key"] == "exfil"

    # Pen test weights stealth at 0 -> no stealth bonus / no overspend penalty
    r3 = _create(client); s3 = manager.get(r3["session_id"])
    assert s3.stealth_weight == 1.0
    s3.claim_role(r3["player_id"], "observer")
    s3.start("ransomware", "pen_test")
    assert s3.stealth_weight == 0.0


def test_live_mission_report(client):
    """A concluded live mission produces an all-teams After-Action Report (REST + structure)."""
    from app.live.manager import manager
    from app.live import auto

    r = client.post("/api/live/sessions", json={"mission_id": "identity_assessment", "host_name": "H"})
    sid = r.json()["session_id"]
    sess = manager.get(sid)
    sess.claim_role(r.json()["player_id"], "observer")

    # report not ready before the mission concludes
    assert client.get(f"/api/live/sessions/{sid}/report").status_code == 409

    sess.start()
    for _ in range(120):
        auto.tick(sess)
        if sess.status == "completed":
            break
    assert sess.status == "completed"

    rep = client.get(f"/api/live/sessions/{sid}/report")
    assert rep.status_code == 200
    data = rep.json()
    assert data["result"] in ("red", "blue", "draw")
    assert set(data["teams"]) == {"red", "soc", "blue"}
    for team in ("red", "soc", "blue"):
        t = data["teams"][team]
        assert "score" in t and "kpis" in t and "findings" in t and "timeline" in t
    assert isinstance(data["mitre"], list) and isinstance(data["recommendations"], list)
    assert data["mission"]["name"] == "Identity Security Assessment"


def test_non_red_cannot_act(client):
    created = _create(client)
    sid, host = created["session_id"], created["player_id"]
    other = client.post(f"/api/live/sessions/{sid}/join", json={"name": "Eve"}).json()["player_id"]

    with client.websocket_connect(f"/ws/live/{sid}?player_id={host}") as host_ws:
        host_ws.receive_json(); host_ws.receive_json()
        host_ws.send_json({"action": "start", "profile": "nation_state"})
        host_ws.receive_json()

        with client.websocket_connect(f"/ws/live/{sid}?player_id={other}") as eve_ws:
            eve_ws.receive_json(); eve_ws.receive_json()
            eve_ws.send_json({"action": "red_action", "action_id": "plan.review"})
            # next message should be an error (Eve has no red role)
            msg = eve_ws.receive_json()
            assert msg["type"] == "error"
