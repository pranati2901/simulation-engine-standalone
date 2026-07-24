"""Live run streaming over WebSocket.

The run is precomputed; this endpoint replays its timeline at a controllable pace and
handles operator controls (pause/resume/speed/seek/inject/stop).
"""
from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.base import SessionLocal
from app.db.models import Report, Run, Scenario as ScenarioRow
from app.engine.config import RunConfig
from app.engine.environment import EnvironmentSpec
from app.engine.scenario import Scenario
from app.reports.generator import generate_report
from app.services.run_manager import RunSession, close_session, open_session
from app.services.runner import run_payload

router = APIRouter(tags=["stream"])

TICK = 0.1  # seconds


def _load_session(run_id: str) -> tuple[RunSession, dict, str] | None:
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            return None
        srow = db.get(ScenarioRow, run.scenario_id)
        if srow is None:
            return None
        scenario = Scenario.model_validate(srow.definition)
        env = EnvironmentSpec.model_validate(run.environment_spec)
        cfg = RunConfig.model_validate(run.config)
        session = open_session(run, scenario, env, cfg)
        init = {
            "type": "init",
            "run_id": run.id,
            "focus_role": run.focus_role,
            "scenario": {
                "name": scenario.name, "phases": scenario.phases,
                "objectives": scenario.objectives.model_dump(),
                "type": scenario.type, "label": scenario.label,
            },
            "duration_s": run.duration_s,
            "environment": run.environment,
            "workflows": run.workflows,
            "role_tasks": run.role_tasks,
            "scores": run.scores,
            "speed": session.speed,
            "total_events": len(session.events),
        }
        return session, init, scenario.industry


def _persist_inject(run_id: str, session: RunSession, industry: str) -> None:
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            return
        run.events = session.events
        run.scores, run.kpis = session.scores, session.kpis
        run.summary, run.objectives = session.summary, session.objectives
        run.final_assets = session.final_assets
        run.role_tasks = session.role_tasks
        report = db.query(Report).filter_by(run_id=run_id).first()
        if report is not None:
            report.content = generate_report(run_payload(run, industry))
        db.commit()


@router.websocket("/ws/runs/{run_id}")
async def stream_run(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    loaded = _load_session(run_id)
    if loaded is None:
        await websocket.send_json({"type": "error", "message": "run not found"})
        await websocket.close()
        return
    session, init, industry = loaded
    await websocket.send_json(init)

    async def receiver() -> None:
        try:
            while True:
                msg = await websocket.receive_json()
                action = msg.get("action")
                if action == "pause":
                    session.pause()
                elif action == "resume":
                    session.resume()
                elif action == "speed":
                    session.set_speed(msg.get("value", 30))
                elif action == "seek":
                    session.seek(msg.get("t", 0))
                elif action == "inject":
                    session.inject(msg.get("technique"), msg.get("target_by"),
                                   msg.get("target_value"), msg.get("label"))
                    await asyncio.to_thread(_persist_inject, run_id, session, industry)
                elif action == "stop":
                    session.seek(session.duration_s)
        except (WebSocketDisconnect, RuntimeError):
            pass

    recv_task = asyncio.create_task(receiver())
    try:
        while not session.finished:
            await asyncio.sleep(TICK)
            session.advance(TICK)
            for ev in session.due_events():
                await websocket.send_json({"type": "event", "event": ev})
            await websocket.send_json({
                "type": "tick", "sim_t": round(session.sim_t),
                "paused": session.paused, "speed": session.speed,
            })
            if session.at_end():
                await websocket.send_json({"type": "complete", **session.complete_payload()})
                session.finished = True
    except WebSocketDisconnect:
        pass
    finally:
        recv_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await recv_task
        close_session(run_id)
        with contextlib.suppress(RuntimeError):
            await websocket.close()
