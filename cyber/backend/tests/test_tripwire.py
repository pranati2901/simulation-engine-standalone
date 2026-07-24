"""Tests for Operation Tripwire — scene engine, scoring, API."""
from __future__ import annotations

import pytest

from app.tripwire.engine import Mode, Phase, SceneSubState, SessionStatus, TripwireSession
from app.tripwire.scenario import QUIZ_BANK, SCENES, get_scene


# ---------------------------------------------------------------------------
#  Engine tests
# ---------------------------------------------------------------------------
class TestEngine:
    def _session(self, mode: str = "standard") -> TripwireSession:
        return TripwireSession(learner_name="test-student", mode=mode)

    def test_initial_state(self):
        s = self._session()
        assert s.phase == Phase.INIT
        assert s.status == SessionStatus.IN_PROGRESS
        assert s.scene_index == -1
        assert s.network.containment_index == 100
        assert s.network.infected_count == 0
        assert len(s.events) == 1  # session_created event

    def test_briefing_transition(self):
        s = self._session()
        s.start_briefing()
        assert s.phase == Phase.BRIEFING

    def test_cannot_skip_briefing(self):
        s = self._session()
        with pytest.raises(ValueError):
            s.start_scene(0)  # must go through briefing first

    def test_scene_progression(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        assert s.phase == Phase.SCENE
        assert s.scene_index == 0
        assert s.scene_sub == SceneSubState.ENTER

    def test_scene_sub_state_transitions(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        s.advance_sub("observe")
        assert s.scene_sub == SceneSubState.OBSERVE
        s.advance_sub("identify")
        assert s.scene_sub == SceneSubState.IDENTIFY
        s.advance_sub("respond")
        assert s.scene_sub == SceneSubState.RESPOND

    def test_invalid_sub_transition(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        with pytest.raises(ValueError):
            s.advance_sub("respond")  # can't skip observe and identify

    def test_cannot_skip_scenes(self):
        s = self._session()
        s.start_briefing()
        with pytest.raises(ValueError):
            s.start_scene(5)  # must start at 0

    def test_submit_decision_correct(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        s.advance_sub("observe")
        s.advance_sub("identify")
        s.advance_sub("respond")

        scene_def = get_scene(0)
        result = s.submit_decision(scene_def, "b", ["alert"], 5000, 0)

        assert result["identify_correct"] is True
        assert result["response_quality"] == "optimal"
        assert s.scene_sub == SceneSubState.RESOLVE
        assert s.scores.detection_points > 0
        assert s.scores.response_points > 0
        assert len(s.decisions) == 1

    def test_submit_decision_wrong(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        s.advance_sub("observe")
        s.advance_sub("identify")
        s.advance_sub("respond")

        scene_def = get_scene(0)
        result = s.submit_decision(scene_def, "a", ["ignore"], 5000, 0)

        assert result["identify_correct"] is False
        assert result["response_quality"] == "poor"
        assert s.scores.detection_points == 0

    def test_network_effects_applied(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        s.advance_sub("observe")
        s.advance_sub("identify")
        s.advance_sub("respond")

        scene_def = get_scene(0)
        s.submit_decision(scene_def, "b", ["alert"], 5000, 0)

        # Optimal response for scene 0: containment_delta=0, infected_delta=1
        assert s.network.infected_count == 1

    def test_finish_scene_advances(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        s.advance_sub("observe")
        s.advance_sub("identify")
        s.advance_sub("respond")
        scene_def = get_scene(0)
        s.submit_decision(scene_def, "b", ["alert"], 5000, 0)
        s.finish_scene()
        assert s.scene_sub is None  # ready for next scene

    def test_full_11_scene_run(self):
        """Run all 11 scenes with correct answers and verify completion."""
        s = self._session()
        s.start_briefing()

        for i in range(11):
            scene_def = get_scene(i)
            s.start_scene(i)
            s.advance_sub("observe")
            s.advance_sub("identify")
            s.advance_sub("respond")

            # Find correct identify answer
            correct = next(o["id"] for o in scene_def["identify"]["options"] if o.get("correct"))
            # Find optimal action
            optimal_actions = [a["id"] for a in scene_def["respond"]["actions"] if a["quality"] == "optimal"]

            s.submit_decision(scene_def, correct, optimal_actions, 5000, 0)
            s.finish_scene()

        assert s.phase == Phase.DEBRIEF
        assert len(s.decisions) == 11

    def test_hard_fail_threshold(self):
        """Poor responses should cause significant network damage and low containment."""
        s = self._session()
        s.start_briefing()

        for i in range(11):
            scene_def = get_scene(i)
            s.start_scene(i)
            s.advance_sub("observe")
            s.advance_sub("identify")
            s.advance_sub("respond")

            # Always wrong + poor response
            poor_actions = [a["id"] for a in scene_def["respond"]["actions"] if a["quality"] == "poor"]
            s.submit_decision(scene_def, "z", poor_actions[:1] or ["wait"], 30000, 0)

            if s.status == SessionStatus.FAILED:
                break
            s.finish_scene()

        # Poor play: either hard-fail triggered or containment is very low
        if s.status == SessionStatus.FAILED:
            assert s.network.containment_index <= 20
        else:
            # Even without hard-fail, containment should be badly damaged
            assert s.network.containment_index < 30
            assert s.network.infected_count > 50

    def test_quiz_scoring(self):
        """Run a full session through quiz."""
        s = self._session()
        s.start_briefing()

        # Run all scenes with correct answers
        for i in range(11):
            scene_def = get_scene(i)
            s.start_scene(i)
            s.advance_sub("observe")
            s.advance_sub("identify")
            s.advance_sub("respond")
            correct = next(o["id"] for o in scene_def["identify"]["options"] if o.get("correct"))
            optimal = [a["id"] for a in scene_def["respond"]["actions"] if a["quality"] == "optimal"]
            s.submit_decision(scene_def, correct, optimal, 5000, 0)
            s.finish_scene()

        s.start_assessment()
        assert s.phase == Phase.ASSESSMENT

        # Submit all correct quiz answers
        answers = [{"item_id": q["id"], "response": q["correct_id"]} for q in QUIZ_BANK]
        result = s.submit_quiz(QUIZ_BANK, answers)

        assert s.status == SessionStatus.COMPLETED
        assert result["passed"] is True
        assert result["composite"] >= 75
        assert result["quiz_correct"] == 15

    def test_backup_destroyed_caps_containment(self):
        """If backup is destroyed (scene 8 poor response), containment is capped at 60."""
        s = self._session()
        s.start_briefing()

        for i in range(11):
            scene_def = get_scene(i)
            s.start_scene(i)
            s.advance_sub("observe")
            s.advance_sub("identify")
            s.advance_sub("respond")

            if i == 8:
                # Scene 8 (Disable Recovery): poor response destroys backup
                poor = [a["id"] for a in scene_def["respond"]["actions"] if a["quality"] == "poor"]
                s.submit_decision(scene_def, "b", poor[:1], 5000, 0)
            else:
                correct = next(o["id"] for o in scene_def["identify"]["options"] if o.get("correct"))
                optimal = [a["id"] for a in scene_def["respond"]["actions"] if a["quality"] == "optimal"]
                s.submit_decision(scene_def, correct, optimal, 5000, 0)

            if s.status == SessionStatus.FAILED:
                break
            s.finish_scene()

        if s.status != SessionStatus.FAILED:
            assert s.network.backup_destroyed is True

    def test_guided_mode_no_speed_scoring(self):
        s = self._session("guided")
        s.start_briefing()
        s.start_scene(0)
        s.advance_sub("observe")
        s.advance_sub("identify")
        s.advance_sub("respond")
        scene_def = get_scene(0)
        s.submit_decision(scene_def, "b", ["alert"], 5000, 0)
        assert s.scores.speed_max == 0  # no speed scoring in guided mode

    def test_hint_penalty(self):
        s = self._session()
        s.start_briefing()
        s.start_scene(0)
        s.advance_sub("observe")
        s.advance_sub("identify")
        s.advance_sub("respond")
        scene_def = get_scene(0)

        # Use 2 hints: should reduce detection score by 20 (2 * 10)
        s.submit_decision(scene_def, "b", ["alert"], 5000, hints_used=2)
        assert s.scores.detection_points == 80  # 100 - 20 penalty

    def test_snapshot_structure(self):
        s = self._session()
        snap = s.snapshot()
        assert "session_id" in snap
        assert "network" in snap
        assert "scores" in snap
        assert snap["mode"] == "standard"

    def test_events_are_append_only(self):
        s = self._session()
        initial_count = len(s.events)
        s.start_briefing()
        assert len(s.events) > initial_count
        # Events should have sequential seq numbers
        seqs = [e["seq"] for e in s.events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)  # all unique


# ---------------------------------------------------------------------------
#  Scenario data tests
# ---------------------------------------------------------------------------
class TestScenario:
    def test_11_scenes_exist(self):
        assert len(SCENES) == 11

    def test_scenes_have_required_fields(self):
        for scene in SCENES:
            assert "index" in scene
            assert "title" in scene
            assert "story" in scene
            assert "telemetry" in scene
            assert "identify" in scene
            assert "respond" in scene
            assert "scoring" in scene
            assert "effects" in scene

    def test_each_scene_has_correct_answer(self):
        for scene in SCENES:
            options = scene["identify"]["options"]
            correct = [o for o in options if o.get("correct")]
            assert len(correct) == 1, f"Scene {scene['index']} must have exactly 1 correct identify option"

    def test_each_scene_has_optimal_response(self):
        for scene in SCENES:
            actions = scene["respond"]["actions"]
            optimal = [a for a in actions if a["quality"] == "optimal"]
            assert len(optimal) >= 1, f"Scene {scene['index']} must have at least 1 optimal response"

    def test_effects_cover_all_qualities(self):
        for scene in SCENES:
            effects = scene["effects"]
            assert "optimal" in effects, f"Scene {scene['index']} missing optimal effects"
            assert "poor" in effects, f"Scene {scene['index']} missing poor effects"

    def test_15_quiz_items_exist(self):
        assert len(QUIZ_BANK) == 15

    def test_quiz_items_have_correct_answers(self):
        for q in QUIZ_BANK:
            assert "correct_id" in q
            option_ids = [o["id"] for o in q["options"]]
            assert q["correct_id"] in option_ids, f"Quiz {q['id']} correct_id not in options"

    def test_scene_indices_sequential(self):
        for i, scene in enumerate(SCENES):
            assert scene["index"] == i


# ---------------------------------------------------------------------------
#  API tests
# ---------------------------------------------------------------------------
class TestAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_list_scenarios(self, client):
        resp = client.get("/api/tripwire/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        ids = [s["scenario_id"] for s in data]
        assert "scn-wannacry-w1" in ids
        assert "scn-r5-phish2enc" in ids
        assert "scn-c5-edr-outage" in ids

    def test_get_scenario(self, client):
        resp = client.get("/api/tripwire/scenarios/scn-wannacry-w1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] == "scn-wannacry-w1"
        assert data["scenes_count"] == 11

    def test_create_session(self, client):
        resp = client.post("/api/tripwire/sessions", json={"learner_name": "alice", "mode": "standard"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["phase"] == "briefing"
        assert data["learner_name"] == "alice"
        assert "session_id" in data

    def test_full_api_flow(self, client):
        # 1. Create session
        resp = client.post("/api/tripwire/sessions", json={"learner_name": "bob"})
        assert resp.status_code == 201
        sid = resp.json()["session_id"]

        # 2. Start scene 0
        resp = client.post(f"/api/tripwire/sessions/{sid}/start-scene?scene_index=0")
        assert resp.status_code == 200
        scene_data = resp.json()["scene"]
        assert scene_data["title"] == "Network Discovery"

        # 3. Submit decision for scene 0
        resp = client.post(f"/api/tripwire/sessions/{sid}/decision", json={
            "scene_index": 0,
            "identify_choice": "b",
            "actions": ["alert"],
            "latency_ms": 5000,
        })
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["identify_correct"] is True
        assert result["response_quality"] == "optimal"

        # 4. Finish scene
        resp = client.post(f"/api/tripwire/sessions/{sid}/finish-scene")
        assert resp.status_code == 200

        # 5. Start scene 1
        resp = client.post(f"/api/tripwire/sessions/{sid}/start-scene?scene_index=1")
        assert resp.status_code == 200

    def test_session_not_found(self, client):
        resp = client.get("/api/tripwire/sessions/nonexistent")
        assert resp.status_code == 404

    def test_list_sessions(self, client):
        client.post("/api/tripwire/sessions", json={"learner_name": "charlie"})
        resp = client.get("/api/tripwire/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
