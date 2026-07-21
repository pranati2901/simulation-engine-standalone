"""App entrypoint. Loads all domain plugins and scenario definitions, then wires up
the API and WS routers.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import analyst, catalog, dashboard, ev, guided, jilla, runs, scenarios, studio, tripwire
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
    # runtime-authored fault actions ride on each Scenario's custom_actions field and
    # are re-registered by scenarios/loader.py::_materialise() as scenarios load above.


app.include_router(catalog.router, dependencies=[Depends(verify_api_key)])
app.include_router(scenarios.router, dependencies=[Depends(verify_api_key)])
app.include_router(runs.router, dependencies=[Depends(verify_api_key)])
app.include_router(dashboard.router, dependencies=[Depends(verify_api_key)])
app.include_router(guided.router, dependencies=[Depends(verify_api_key)])
app.include_router(tripwire.router, dependencies=[Depends(verify_api_key)])
app.include_router(studio.router, dependencies=[Depends(verify_api_key)])
app.include_router(jilla.router, dependencies=[Depends(verify_api_key)])
app.include_router(analyst.router, dependencies=[Depends(verify_api_key)])
app.include_router(ev.router, dependencies=[Depends(verify_api_key)])
app.include_router(ws_runs.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


# ── Serving the frontend ────────────────────────────────────────────────────────
#
# One process serves the API AND the built React frontend, mirroring NextXR. That also
# makes this the origin the hub loads the federated remote from:
#   {ENGINE}/assets/remoteEntry.js  +  {ENGINE}/assets/style.css
#
# Cross-origin, so the hub can only fetch remoteEntry.js if this engine sends CORS headers
# for the hub's origin — set GOALCERT_CORS_ORIGINS. `cors_origins` defaults to an EMPTY
# list, and note allow_credentials=True with "*" is rejected by browsers, so the hub origin
# must be listed explicitly.
#
# The dist/ mount is conditional: `npm run build` may not have run yet (fresh clone, CI
# backend-only job). StaticFiles raises at import time if the directory is missing, which
# would take the whole API down over a missing frontend build — so fall back to the old
# static placeholder instead of refusing to start.
DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"
_HAS_DIST = (DIST_DIR / "index.html").is_file()

if _HAS_DIST:
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


@app.get("/")
def index():
    """The built Scenario Engine SPA, or the legacy placeholder if it isn't built yet.

    The placeholder (app/static/index.html) is a single static page that calls the API
    routes above with fetch() — enough to prove the engine end-to-end in a browser, but
    not the real UI.
    """
    if _HAS_DIST:
        return FileResponse(DIST_DIR / "index.html")
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── SPA history fallback ────────────────────────────────────────────────────────
#
# The standalone frontend is a client-routed SPA: /dashboard, /builder, /simulation
# exist only in the browser's router. Without this, loading or refreshing any of them
# hits FastAPI, matches no route, and 404s — the app only worked at "/".
#
# Registered LAST on purpose. FastAPI matches in declaration order, so every API router
# above still wins; this only ever sees paths nothing else claimed. Unknown /api-ish
# paths therefore return index.html rather than a JSON 404 — the standard SPA trade-off,
# and harmless here because the hub never routes through this fallback (it mounts the
# federated remote and calls the API through its own gateway).
if _HAS_DIST:
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Let genuinely missing assets 404 as assets. Returning index.html for a missing
        # .js/.css makes the browser report a confusing MIME-type error instead of the
        # plain 404 that tells you the build is stale.
        candidate = (DIST_DIR / full_path).resolve()
        if candidate.is_file() and candidate.is_relative_to(DIST_DIR.resolve()):
            return FileResponse(candidate)
        if "." in Path(full_path).name:
            raise HTTPException(status_code=404, detail=f"Not found: {full_path}")
        return FileResponse(DIST_DIR / "index.html")