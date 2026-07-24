"""API + WebSocket integration tests (FastAPI TestClient over a temp SQLite DB)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_catalogs_populated(client):
    assert len(client.get("/api/catalog/assets").json()) >= 10
    assert len(client.get("/api/catalog/controls").json()) >= 8
    assert len(client.get("/api/catalog/techniques").json()) >= 15


def test_scenarios_seeded(client):
    scns = client.get("/api/scenarios").json()
    ids = {s["id"] for s in scns}
    assert "operation_black_phoenix" in ids
    topo = client.get("/api/scenarios/operation_black_phoenix/topology").json()
    assert len(topo["assets"]) == 14
    assert len(topo["controls"]) == 8


def test_create_and_delete_custom_scenario(client):
    payload = {
        "id": "test_delete_me", "name": "Delete Me", "type": "purple",
        "recommended_topology": {"assets": [], "controls": []},
    }
    assert client.post("/api/scenarios", json=payload).status_code == 201
    assert "test_delete_me" in {s["id"] for s in client.get("/api/scenarios").json()}

    r = client.request("DELETE", "/api/scenarios/test_delete_me")
    assert r.status_code == 200 and r.json()["deleted"] is True
    assert "test_delete_me" not in {s["id"] for s in client.get("/api/scenarios").json()}

    # deleting again is a 404; seed scenarios are protected (403)
    assert client.request("DELETE", "/api/scenarios/test_delete_me").status_code == 404
    assert client.request("DELETE", "/api/scenarios/operation_black_phoenix").status_code == 403


def test_launch_run_strong_vs_weak_and_report(client):
    # Strong posture (Easy, all controls on)
    strong = client.post("/api/runs", json={
        "scenario_id": "operation_black_phoenix",
        "config": {"difficulty": "Easy", "readiness": 95, "duration_min": 60},
    }).json()
    assert strong["status"] == "completed"
    assert strong["summary"]["ransomware"] is False

    # Weak posture (Expert, controls disabled)
    topo = client.get("/api/scenarios/operation_black_phoenix/topology").json()
    for c in topo["controls"]:
        c["enabled"] = False
    weak = client.post("/api/runs", json={
        "scenario_id": "operation_black_phoenix",
        "environment_spec": topo,
        "config": {"difficulty": "Expert", "readiness": 15, "duration_min": 60},
        "operator": "Tester",
    }).json()
    assert weak["summary"]["ransomware"] is True
    assert weak["scores"]["red"] > strong["scores"]["red"]

    # events + report
    events = client.get(f"/api/runs/{weak['id']}/events").json()
    assert len(events) > 20
    report = client.get(f"/api/runs/{weak['id']}/report").json()
    assert "exec_summary" in report
    assert report["scorecard"]["winner"] in ("Red", "Blue")
    assert len(report["timeline"]) > 5
    assert report["maturity_score"]["score"] <= 40  # weak posture => low maturity


def test_dashboard_and_leaderboard(client):
    dash = client.get("/api/dashboard").json()
    assert dash["total_runs"] >= 2
    assert "readiness" in dash
    lb = client.get("/api/leaderboard").json()
    assert isinstance(lb, list) and len(lb) >= 1


def test_roles_and_workflows_catalog(client):
    roles = client.get("/api/catalog/roles").json()
    assert {r["role"] for r in roles} == {"red", "soc", "blue", "mgmt", "ot"}
    workflows = client.get("/api/catalog/workflows").json()
    assert len(workflows) == 5
    assert all(len(w["steps"]) >= 4 for w in workflows)


def test_launch_focus_role_and_per_role_report(client):
    run = client.post("/api/runs", json={
        "scenario_id": "operation_black_phoenix",
        "config": {"difficulty": "Expert", "readiness": 60, "duration_min": 90, "focus_role": "soc"},
        "operator": "Lens",
    }).json()
    assert run["focus_role"] == "soc"
    assert set(run["scores"]) == {"red", "blue", "soc", "mgmt", "ot"}
    detail = client.get(f"/api/runs/{run['id']}").json()
    assert len(detail["workflows"]) == 5
    assert "soc" in detail["role_tasks"]
    report = client.get(f"/api/runs/{run['id']}/report").json()
    cards = {c["role"]: c for c in report["role_scorecards"]}
    assert set(cards) == {"red", "blue", "soc", "mgmt", "ot"}
    assert cards["soc"]["tasks_total"] >= 4


def test_websocket_stream_lifecycle(client):
    run = client.post("/api/runs", json={
        "scenario_id": "operation_black_phoenix",
        "config": {"difficulty": "Expert", "readiness": 40, "duration_min": 10},
    }).json()
    got_event = False
    completed = None
    with client.websocket_connect(f"/ws/runs/{run['id']}") as ws:
        init = ws.receive_json()
        assert init["type"] == "init"
        assert len(init["environment"]) == 14
        ws.send_json({"action": "speed", "value": 600})
        for _ in range(3000):
            msg = ws.receive_json()
            if msg["type"] == "event":
                got_event = True
            elif msg["type"] == "complete":
                completed = msg
                break
    assert got_event
    assert completed is not None and "scores" in completed
