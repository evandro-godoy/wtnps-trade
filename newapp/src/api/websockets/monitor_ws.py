from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from newapp.src.api.dependencies import get_state_from_websocket

router = APIRouter()


def _normalize_ws_action(message: dict[str, Any]) -> str:
    """Extract and normalize websocket action from client message."""
    return str(message.get("action", "ping")).strip().lower()


@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    state = get_state_from_websocket(websocket)
    active_mode = await state.monitor_runtime.register_websocket(websocket)
    try:
        while True:
            frame = await websocket.receive()
            if frame.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()

            message: dict[str, Any]
            text_payload = frame.get("text")
            if text_payload is not None:
                try:
                    message_data = json.loads(text_payload)
                    message = message_data if isinstance(message_data, dict) else {}
                except json.JSONDecodeError:
                    # Backward compatibility for legacy text ping flow.
                    message = {"action": text_payload}
            else:
                message = {}

            action = _normalize_ws_action(message)

            if action == "set_frequency":
                active_mode = state.monitor_runtime.set_websocket_frequency(
                    websocket=websocket,
                    mode=str(message.get("mode", "tick")),
                )
                await websocket.send_json(
                    {
                        "type": "frequency_ack",
                        "mode": active_mode,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                continue

            await websocket.send_json(
                {
                    "type": "pong",
                    "mode": active_mode,
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except WebSocketDisconnect:
        pass
    finally:
        state.monitor_runtime.unregister_websocket(websocket)
