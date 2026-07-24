"""In-memory live-session registry + a WebSocket broadcast hub.

Sessions live in process memory (single-server POC). The Hub tracks the WebSockets connected to
each session so any state change can be broadcast to every participant. All session mutation is
serialised through a per-session lock so REST joins and WS actions don't race.
"""
from __future__ import annotations

import asyncio
import threading
import uuid

from fastapi import WebSocket

from app.engine.environment import EnvironmentSpec
from app.engine.scenario import Scenario
from app.db.base import SessionLocal
from app.db.models import Report as ReportRow, Run as RunRow

from . import auto
from .session import LiveSession, Player

AUTO_TICK = 3.0  # seconds between auto-driver actions (paced so humans can react)


class LiveManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._conns: dict[str, set[WebSocket]] = {}
        self._tickers: dict[str, asyncio.Task] = {}

    # ---- registry ------------------------------------------------------------
    def create(self, scenario: Scenario, env: EnvironmentSpec, host_name: str) -> tuple[LiveSession, Player]:
        host = Player(id=uuid.uuid4().hex[:12],
                      name=(host_name or "host").strip()[:40] or "host", is_host=True)
        session = LiveSession(scenario, env, host)
        self._sessions[session.id] = session
        self._locks[session.id] = threading.Lock()
        self._conns[session.id] = set()
        return session, host

    def get(self, session_id: str) -> LiveSession | None:
        return self._sessions.get(session_id)

    def lock(self, session_id: str) -> threading.Lock:
        return self._locks.setdefault(session_id, threading.Lock())

    def list_open(self) -> list[dict]:
        """Joinable / running sessions, newest first (completed ones drop off)."""
        rows = [s.list_summary() for s in self._sessions.values() if s.status in ("lobby", "active")]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def persist_report(self, session: LiveSession) -> str | None:
        """Save the live match report to the DB as a Run + Report row so it shows in Reports page."""
        if session.report is None:
            return None
        try:
            db = SessionLocal()
            run_id = session.id
            report = session.report
            duration_s = report.get("duration_s", 0)
            teams = report.get("teams", {})
            scores = {role: t.get("score", 0) for role, t in teams.items()}
            kpis = {}
            for role, t in teams.items():
                for k, v in t.get("kpis", {}).items():
                    kpis[f"{role}_{k}"] = v
            outcome = report.get("outcome", {})
            summary = {
                "result": report.get("result", ""),
                "verdict": report.get("verdict", ""),
                "mission": report.get("mission", {}).get("name", ""),
                "profile": report.get("profile", ""),
                "objective_met": outcome.get("objective_met", False),
                "assets_compromised": outcome.get("assets_compromised", 0),
                "assets_contained": outcome.get("assets_contained", 0),
                "assets_down": outcome.get("assets_down", 0),
                "eviction_complete": outcome.get("eviction_complete", False),
                "live_session": True,
            }
            run_row = RunRow(
                id=run_id,
                scenario_id=session.scenario.id if session.scenario else "live",
                scenario_name=f"[LIVE] {session.scenario_name}",
                operator=session.host.name if session.host else "live",
                status="completed",
                focus_role="blue",
                config={},
                environment_spec={},
                duration_s=duration_s,
                scores=scores,
                kpis=kpis,
                summary=summary,
                objectives={},
                events=session.events[-100:],  # last 100 events to avoid huge rows
                final_assets=[],
            )
            report_row = ReportRow(run_id=run_id, content=report)
            existing = db.get(RunRow, run_id)
            if existing is None:
                db.add(run_row)
                db.add(report_row)
                db.commit()
            db.close()
            return run_id
        except Exception:
            return None

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._locks.pop(session_id, None)
        self._conns.pop(session_id, None)

    # ---- connections ---------------------------------------------------------
    def register(self, session_id: str, ws: WebSocket) -> None:
        self._conns.setdefault(session_id, set()).add(ws)

    def unregister(self, session_id: str, ws: WebSocket) -> None:
        self._conns.get(session_id, set()).discard(ws)

    async def broadcast(self, session_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._conns.get(session_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister(session_id, ws)

    async def broadcast_snapshot(self, session_id: str) -> None:
        session = self.get(session_id)
        if session is not None:
            await self.broadcast(session_id, session.snapshot())

    # ---- live-fire (real tools) ----------------------------------------------
    async def run_live_fire(self, session_id: str) -> None:
        """Execute any queued real-tool jobs off the event loop, streaming each result back.

        The subprocess work (`docker exec` into Kali) runs in a worker thread so the WS loop and
        the auto-driver ticker stay responsive. Each finished job is attached to its action event
        and broadcast immediately, so the operator watches real output land step by step.
        """
        session = self.get(session_id)
        if session is None or not session.live_fire:
            return
        with self.lock(session_id):
            jobs = session.drain_pending_fire()
        if not jobs:
            return
        from app.lab import live_fire as lf
        from app.lab.manager import get_lab
        from app.lab.pool import get_pool
        try:
            # prefer this session's own isolated range (Phase 3); fall back to the shared lab
            lab = get_pool().get(session_id) or get_lab()
        except Exception:
            return
        if lab is None:
            return
        for job in jobs:
            try:
                result = await asyncio.to_thread(lf.run_job, lab, job["action_id"])
            except Exception as exc:  # a tool failure must never break the match
                result = {"status": "error", "success": False, "output": str(exc)[:500]}
            with self.lock(session_id):
                session.apply_fire_result(job["seq"], result)
            await self.broadcast_snapshot(session_id)

    # ---- auto-driver ticker --------------------------------------------------
    def ensure_ticker(self, session_id: str) -> None:
        """Start the auto-driver loop for a session if one isn't already running."""
        t = self._tickers.get(session_id)
        if t is not None and not t.done():
            return
        self._tickers[session_id] = asyncio.create_task(self._ticker_loop(session_id))

    async def _ticker_loop(self, session_id: str) -> None:
        try:
            while True:
                await asyncio.sleep(AUTO_TICK)
                session = self.get(session_id)
                if session is None or not self._conns.get(session_id):
                    break  # gone, or nobody watching
                if session.status == "completed":
                    self._try_persist(session)
                    break
                if session.status != "active":
                    continue  # lobby — wait for start
                with self.lock(session_id):
                    if getattr(session, "sim", None) is not None:
                        changed = session.sim.tick()
                    elif session.guided is not None:
                        from . import guided_runtime
                        changed = guided_runtime.auto_step(session)
                    else:
                        changed = auto.tick(session)
                if changed:
                    await self.broadcast_snapshot(session_id)
                    if session.live_fire and session.pending_fire:
                        await self.run_live_fire(session_id)
                    if session.status == "completed":
                        self._try_persist(session)
                        break
        finally:
            self._tickers.pop(session_id, None)

    def _try_persist(self, session: LiveSession) -> None:
        """Try to persist the report, log failures instead of crashing."""
        try:
            result = self.persist_report(session)
            if result:
                import sys
                print(f"[live] Report persisted for session {session.id} as run {result}", file=sys.stderr)
        except Exception as exc:
            import sys, traceback
            print(f"[live] Failed to persist report for {session.id}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


manager = LiveManager()
