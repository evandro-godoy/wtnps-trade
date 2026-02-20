from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from newapp.src.api.dependencies import get_state_from_websocket

router = APIRouter()


@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    state = get_state_from_websocket(websocket)
    await state.monitor_runtime.register_websocket(websocket)
    try:
        while True:
            await websocket.receive_text()
            await websocket.send_json(
                {"type": "pong", "timestamp": datetime.now().isoformat()}
            )
    except WebSocketDisconnect:
        pass
    finally:
        state.monitor_runtime.unregister_websocket(websocket)
