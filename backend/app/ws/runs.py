from fastapi import APIRouter, WebSocket

from ..core.auth import verify_ws_api_key

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def stream_run(websocket: WebSocket, run_id: str):
    if not verify_ws_api_key(websocket):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    await websocket.send_json({
        "type": "system",
        "message": f"Live streaming for run '{run_id}' not yet implemented — "
                   "runner.execute() is currently synchronous.",
    })
    await websocket.close()