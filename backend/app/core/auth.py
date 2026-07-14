"""Shared-secret auth. The Hub sends SCENARIO_API_KEY as the X-API-Key header."""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, WebSocket

from .settings import settings


def verify_api_key(request: Request, x_api_key: str = Header(default="")) -> None:
    if request.method == "GET" and request.url.path == "/health":
        return
    if not settings.scenario_api_key:
        return  # no key configured -> local dev, allow through
    if not secrets.compare_digest(x_api_key, settings.scenario_api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")


def verify_ws_api_key(websocket: WebSocket) -> bool:
    """WS equivalent of verify_api_key. Browsers can't set headers on a WebSocket
    handshake, so the key may also arrive as an ?x_api_key= query param.
    """
    if not settings.scenario_api_key:
        return True  # no key configured -> local dev, allow through
    key = websocket.query_params.get("x_api_key") or websocket.headers.get("X-Api-Key") or ""
    return secrets.compare_digest(key, settings.scenario_api_key)