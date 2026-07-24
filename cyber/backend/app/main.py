"""FastAPI application entrypoint."""
from __future__ import annotations

import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import app.engine  # noqa: F401  (populate asset/control/technique registries)
from app.api import auth, catalog, dashboard, jilla, lab, live, runs, scenarios
from app.tripwire.api import router as tripwire_router
from app.studio.routes import router as studio_router
from app.studio.ws import router as studio_ws
from app.core.settings import settings
from app.db.base import init_db
from app.ws import live as ws_live
from app.ws import runs as ws_runs
from app.ws import tripwire as ws_tripwire

# Frontend dist/ directory (built by Vite, copied here during Render build)
STATIC_DIR = pathlib.Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="GoalCert Simulation Engine", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(jilla.router)
app.include_router(tripwire_router)
app.include_router(lab.router)
app.include_router(catalog.router)
app.include_router(scenarios.router)
app.include_router(runs.router)
app.include_router(dashboard.router)
app.include_router(live.router)
app.include_router(studio_router)
app.include_router(ws_runs.router)
app.include_router(ws_live.router)
app.include_router(ws_tripwire.router)
app.include_router(studio_ws)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "goalcert-engine"}


# --- Serve frontend SPA (only when static/ exists, i.e. production) ----------
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for all non-API routes (SPA client-side routing)."""
        file = STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
