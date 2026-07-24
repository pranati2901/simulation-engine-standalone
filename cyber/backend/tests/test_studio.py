"""Scenario Studio API tests (stub mode — no Anthropic key needed)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_catalogue(client):
    domains = client.get("/api/studio/domains").json()["domains"]
    ids = {d["id"] for d in domains}
    assert {"generic", "manufacturing", "rail", "aviation"}.issubset(ids)
    assert len(client.get("/api/studio/faults?domain=rail").json()["faults"]) >= 4
    assert len(client.get("/api/studio/presets?domain=manufacturing").json()["presets"]) >= 2


def test_seed_scenarios_present(client):
    scns = client.get("/api/studio/scenarios").json()["scenarios"]
    assert any(s["is_seed"] for s in scns)
    assert any(s["id"] == "seed-rail-heatwave" for s in scns)


def test_author_and_run_scored(client):
    # author a spec (stub maps to a fault) and save it
    a = client.post("/api/studio/scenarios/author", json={
        "description": "Bearing wear rises during a long endurance run",
        "domain": "aviation", "kind": "fault"}).json()
    assert a["ai_mode"] == "stub"
    assert a["spec"]["fault"] == "bearing_wear"
    sid = a["scenario"]["id"]
    assert sid in {s["id"] for s in client.get("/api/studio/scenarios").json()["scenarios"]}

    # run it → objective KPI-scored result with a timeline
    r = client.post("/api/studio/runs", json={"scenario_id": sid}).json()
    assert r["outcome_band"] in ("Contained", "Degraded", "Severe", "Critical")
    assert len(r["events"]) >= 4
    assert 0 <= r["kpis"]["readiness_score"] <= 100
    assert r["kpis"]["grade"] in ("A", "B", "C", "D", "F")

    # run history + detail
    runs = client.get("/api/studio/runs").json()["runs"]
    assert any(x["id"] == r["id"] for x in runs)
    assert client.get(f"/api/studio/runs/{r['id']}").json()["id"] == r["id"]
    assert len(client.get(f"/api/studio/runs/{r['id']}/events").json()) == len(r["events"])

    # delete the authored scenario; seeds are protected
    assert client.request("DELETE", f"/api/studio/scenarios/{sid}").status_code == 200
    assert client.request("DELETE", "/api/studio/scenarios/seed-rail-heatwave").status_code == 403


def test_adhoc_run_without_saving(client):
    spec = {"name": "Ad-hoc", "domain": "datacenter", "kind": "scenario", "system": "Data Hall",
            "fault": "thermal_runaway", "severity": 0.9, "intensity": 1.0, "horizon_min": 120}
    r = client.post("/api/studio/runs", json={"spec": spec}).json()
    assert r["outcome_band"] == "Critical"      # severity 0.9 → Critical band
    assert r["kpis"]["peak_severity_pct"] == 90


def test_training_procedure_and_authoritative_grade(client):
    proc = client.post("/api/studio/training/procedure", json={
        "domain": "manufacturing", "system": "Assembly Line", "fault": "spindle_bearing",
        "title": "Rush order"}).json()["procedure"]
    step_ids = [s["id"] for s in proc["steps"]]
    assert len(step_ids) >= 4

    # a flawless run (all steps in order) → perfect score, complete
    perfect = [{"step_id": sid, "action": "perform"} for sid in step_ids]
    g = client.post("/api/studio/training/grade", json={"procedure": proc, "actions": perfect}).json()
    assert g["complete"] is True and g["score"] == 100 and g["grade"] == "A"

    # repairing before isolating/diagnosing is a safety/order violation → penalised
    bad = [{"step_id": step_ids[2], "action": "perform"},   # e.g. S3 before S1/S2
           {"step_id": step_ids[0], "action": "perform"},
           {"step_id": step_ids[1], "action": "skip"}]
    gb = client.post("/api/studio/training/grade", json={"procedure": proc, "actions": bad}).json()
    assert gb["violations"] >= 1 and gb["skips"] >= 1 and gb["score"] < 100
    assert gb["complete"] is False


def test_ai_status_is_read_only_from_env(client, monkeypatch):
    # no env key → stub mode, no key exposed
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    st = client.get("/api/studio/settings").json()
    assert st["ai_mode"] == "stub" and st["has_key"] is False and st["source"] == "none"

    # env key present → agent mode, key never returned in full (only a masked preview)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-1234567890ABCD")
    st2 = client.get("/api/studio/settings").json()
    assert st2["ai_mode"] == "agent" and st2["has_key"] is True and st2["source"] == "env"
    assert "1234567890ABCD" not in st2["masked_key"] and "…" in st2["masked_key"]

    # the key cannot be set from the API (no write endpoint)
    assert client.post("/api/studio/settings", json={"api_key": "x"}).status_code == 405
