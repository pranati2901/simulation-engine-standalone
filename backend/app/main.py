"""App entrypoint. Loads all domain plugins and scenario definitions, then wires up
the API and WS routers.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import catalog, dashboard, guided, jilla, runs, scenarios, studio, tripwire
from .core.auth import verify_api_key
from .core.settings import settings
from .db.base import Base, engine
from .plugins.registry import load_all as load_plugins
from .scenarios.loader import load_all as load_scenarios
from .ws import runs as ws_runs

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)  # auto-create tables (no Alembic yet)
    load_plugins()      # registers actor/resource types, actions, roles per domain
    load_scenarios()    # imports scenarios/definitions/** so they self-register
    from .services.custom_actions import load_custom_actions
    load_custom_actions()  # re-register runtime-authored fault actions (AI authoring)


app.include_router(catalog.router, dependencies=[Depends(verify_api_key)])
app.include_router(scenarios.router, dependencies=[Depends(verify_api_key)])
app.include_router(runs.router, dependencies=[Depends(verify_api_key)])
app.include_router(dashboard.router, dependencies=[Depends(verify_api_key)])
app.include_router(guided.router, dependencies=[Depends(verify_api_key)])
app.include_router(tripwire.router, dependencies=[Depends(verify_api_key)])
app.include_router(studio.router, dependencies=[Depends(verify_api_key)])
app.include_router(jilla.router, dependencies=[Depends(verify_api_key)])
app.include_router(ws_runs.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/")
def index():
    """Serves the minimal frontend at http://127.0.0.1:8000/ — a single static HTML
    page (app/static/index.html) that calls the API routes above with fetch(). This is
    a placeholder to prove the engine end-to-end in a browser, not the real Hub UI —
    the real UI (digital twin -> agents -> scenario engine flow) will live elsewhere
    once the three repos are merged.
    """
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")