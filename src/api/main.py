"""FastAPI application entrypoint for WTNPS Trade.

Provides:
- Health check endpoint (GET /health)
- WebSocket endpoint (/ws) for receiving client messages

This module is the initial API layer that will later integrate with the
trading engines (simulation/live). It focuses on low latency handling and
clean separation of concerns. All new code uses type hints and structured
logging via the existing logger utility.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from src.utils.logger import logger

app: FastAPI = FastAPI(title="WTNPS Trade API", version="0.1.0")
api_router: APIRouter = APIRouter()

class HealthStatus(BaseModel):
    """Represents health check response payload."""
    status: str = Field(default="ok")
    service: str = Field(default="wtnps-trade")
    version: str = Field(default=app.version)

class ClientMessage(BaseModel):
    """Generic message model received over WebSocket.

    Attributes:
        type: Semantic type/category of the message (e.g., 'tick', 'command').
        payload: Arbitrary JSON content associated with the message.
        timestamp: Optional ISO timestamp supplied by the client.
    """
    type: str = Field(..., min_length=1)
    payload: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = Field(default=None, description="Client-sent ISO timestamp")

class ConnectionManager:
    """Manages active WebSocket connections and broadcasting.

    Future expansion: authentication, per-client context, throttling, etc.
    """
    def __init__(self) -> None:
        self._active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active={len(self._active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Active={len(self._active_connections)}")

    async def send_ack(self, websocket: WebSocket, message: str) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        for connection in list(self._active_connections):
            try:
                await connection.send_text(message)
            except Exception as exc:  # pragma: no cover (network errors)
                logger.warning(f"Broadcast failed to a connection: {exc}")

manager: ConnectionManager = ConnectionManager()

@api_router.get("/health", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """Return service health status for monitoring and orchestration systems."""
    logger.debug("Health check invoked")
    return HealthStatus()

@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for receiving client-sent trading data or control messages.

    Echoes an ACK for each valid message. Invalid JSON is logged and a generic
    error notice is returned. Disconnections are handled gracefully.
    """
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            logger.debug(f"Raw WS message: {raw}")
            try:
                parsed: Dict[str, Any] = json.loads(raw)
                msg = ClientMessage(**parsed)
                logger.info(f"WS message received type={msg.type} payload_keys={list(msg.payload.keys()) if msg.payload else 'none'}")
                # Placeholder: integrate with processing pipeline (e.g., enqueue)
                await manager.send_ack(websocket, "ACK")
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received over WebSocket")
                await manager.send_ack(websocket, "ERROR: invalid JSON")
            except ValidationError as ve:
                logger.warning(f"Validation error: {ve}")
                await manager.send_ack(websocket, "ERROR: invalid schema")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:  # pragma: no cover
        logger.error(f"Unexpected WS error: {exc}")
        manager.disconnect(websocket)

# Register router
app.include_router(api_router)

@app.get("/", response_class=JSONResponse)
async def root() -> Dict[str, str]:
    """Root endpoint simple description."""
    return {"message": "WTNPS Trade API running", "version": app.version}

# Application lifecycle events
@app.on_event("startup")
async def on_startup() -> None:
    logger.info("FastAPI application startup complete")

@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("FastAPI application shutdown complete")

if __name__ == "__main__":  # Manual launch convenience
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
