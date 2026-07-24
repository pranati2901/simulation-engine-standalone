"""Live/cinematic replay of a Studio run's timeline over WebSocket.

The run is precomputed; this paces its events out one-by-one so the UI can animate the run (the
'live run streaming' + 'AI Maintenance Director' visualisation). Supports pause/resume/speed/stop.
"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.base import SessionLocal

from . import service

router = APIRouter(tags=["studio-stream"])

BASE_DELAY = 1.4  # seconds between events at 1x


def _load(run_id: str) -> dict | None:
    with SessionLocal() as db:
        result = service.get_run(db, run_id)
        return result.model_dump() if result else None


@router.websocket("/ws/studio/runs/{run_id}")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    result = _load(run_id)
    if result is None:
        await websocket.send_json({"type": "error", "message": "run not found"})
        await websocket.close()
        return

    events = result.get("events", [])
    state = {"paused": False, "speed": 1.0, "stopped": False}
    await websocket.send_json({
        "type": "init", "run_id": run_id, "name": result.get("name"),
        "domain": result.get("domain"), "system": result.get("system"),
        "outcome_band": result.get("outcome_band"), "headline": result.get("headline"),
        "kpis": result.get("kpis"), "total_events": len(events),
    })

    async def receiver() -> None:
        try:
            while True:
                msg = await websocket.receive_json()
                a = msg.get("action")
                if a == "pause":
                    state["paused"] = True
                elif a == "resume":
                    state["paused"] = False
                elif a == "speed":
                    state["speed"] = max(0.25, min(8.0, float(msg.get("value", 1))))
                elif a == "stop":
                    state["stopped"] = True
        except (WebSocketDisconnect, RuntimeError, ValueError):
            pass

    recv = asyncio.create_task(receiver())
    try:
        for i, ev in enumerate(events):
            if state["stopped"]:
                break
            while state["paused"] and not state["stopped"]:
                await asyncio.sleep(0.1)
            await websocket.send_json({"type": "event", "index": i, "event": ev})
            await asyncio.sleep(BASE_DELAY / state["speed"])
        await websocket.send_json({
            "type": "complete", "outcome_band": result.get("outcome_band"),
            "kpis": result.get("kpis"), "narrative": result.get("narrative"),
            "mitigations": result.get("mitigations"), "risks": result.get("risks"),
        })
    except WebSocketDisconnect:
        pass
    finally:
        recv.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await recv
        with contextlib.suppress(RuntimeError):
            await websocket.close()
