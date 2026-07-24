"""Tripwire WebSocket — real-time scene streaming for the WannaCry simulation."""
from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.tripwire.engine import TripwireSession, Phase
from app.tripwire.scenarios import get_scenario

router = APIRouter()

# Share session store with REST API
from app.tripwire.api import _sessions, _get as _api_get


@router.websocket("/ws/tripwire/{session_id}")
async def tripwire_ws(websocket: WebSocket, session_id: str):
    """WebSocket for a Tripwire session. Handles the full student flow."""
    await websocket.accept()

    session = _sessions.get(session_id)
    if session is None:
        await websocket.send_json({"type": "error", "message": "Session not found"})
        await websocket.close()
        return

    # Load scenario for this session
    scn = get_scenario(session.scenario_id)
    scenes = scn["scenes"]

    # Send initial state
    await websocket.send_json({
        "type": "init",
        "scenario": {**scn["meta"], "segments": scn.get("segments", [])},
        "session": session.snapshot(),
        "scenes_meta": [{"index": s["index"], "title": s["title"], "mitre": s["mitre"]} for s in scenes],
    })

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            action = msg.get("action", "")

            try:
                if action == "start_scene":
                    idx = msg.get("scene_index", 0)
                    session.start_scene(idx)
                    scene_def = scn["get_scene"](idx)
                    session.advance_sub("observe")
                    session.advance_sub("identify")

                    # Strip correct answers before sending to client
                    safe_identify = {
                        "prompt": scene_def["identify"]["prompt"],
                        "options": [{"id": o["id"], "text": o["text"]}
                                    for o in scene_def["identify"]["options"]],
                    }
                    # Branching story text based on containment
                    ci = session.network.containment_index
                    if ci >= 70 and "story_strong" in scene_def:
                        story = scene_def["story_strong"]
                    elif ci < 40 and "story_weak" in scene_def:
                        story = scene_def["story_weak"]
                    else:
                        story = scene_def["story"]

                    await websocket.send_json({
                        "type": "scene",
                        "session": session.snapshot(),
                        "scene": {
                            "index": scene_def["index"],
                            "title": scene_def["title"],
                            "mitre": scene_def["mitre"],
                            "story": story,
                            "telemetry": scene_def["telemetry"],
                            "identify": safe_identify,
                            "micro_teach": scene_def.get("micro_teach", ""),
                        },
                    })

                elif action == "submit_identify":
                    session.advance_sub("respond")
                    scene_def = scn["get_scene"](session.scene_index)
                    await websocket.send_json({
                        "type": "respond_ready",
                        "session": session.snapshot(),
                        "respond": scene_def["respond"],
                    })

                elif action == "submit_decision":
                    scene_def = scn["get_scene"](session.scene_index)
                    result = session.submit_decision(
                        scene_def,
                        msg.get("identify_choice", ""),
                        msg.get("actions", []),
                        msg.get("latency_ms", 0),
                        msg.get("hints_used", 0),
                    )
                    await websocket.send_json({
                        "type": "decision_result",
                        "session": session.snapshot(),
                        "result": result,
                        "micro_teach": scene_def.get("micro_teach", ""),
                    })

                elif action == "finish_scene":
                    session.finish_scene()
                    await websocket.send_json({
                        "type": "scene_finished",
                        "session": session.snapshot(),
                    })

                elif action == "start_assessment":
                    session.start_assessment()
                    quiz = scn["get_quiz_subset"](10)
                    client_quiz = [{
                        "id": q["id"],
                        "question": q["question"],
                        "options": [{"id": o["id"], "text": o["text"]} for o in q["options"]],
                    } for q in quiz]

                    await websocket.send_json({
                        "type": "assessment",
                        "session": session.snapshot(),
                        "quiz": client_quiz,
                    })

                elif action == "submit_quiz":
                    answers = msg.get("answers", [])
                    result = session.submit_quiz(scn["quiz_bank"], answers)
                    await websocket.send_json({
                        "type": "results",
                        "session": session.snapshot(),
                        "result": result,
                    })

                elif action == "get_debrief":
                    timeline = []
                    for d in session.decisions:
                        sd = scn["get_scene"](d.scene_index)
                        timeline.append({
                            "scene_index": d.scene_index,
                            "title": sd["title"],
                            "mitre": sd["mitre"],
                            "identify_correct": d.identify_correct,
                            "response_quality": d.response_quality,
                            "score_delta": d.score_delta,
                        })
                    await websocket.send_json({
                        "type": "debrief",
                        "session": session.snapshot(),
                        "timeline": timeline,
                    })

                else:
                    await websocket.send_json({"type": "error", "message": f"Unknown action: {action}"})

            except ValueError as e:
                await websocket.send_json({"type": "error", "message": str(e)})

    except (WebSocketDisconnect, RuntimeError):
        pass
